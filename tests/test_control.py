import concurrent.futures
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from sidekick_control.store import ControlError, Store, canonical
from sidekick_control.service import Runtime, Server, AGENT_METHODS
from sidekick_control.client import call
from sidekick_control.validation import origins, prepare


class ControlFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'state'
        self.now = 1_000_000.0
        self.store = Store(self.directory, clock=lambda: self.now)
        self.runtime = Runtime(self.store, allow_loopback=True)
        self.store.configure_browser(True, ['https://example.test'])

    def inspect(self, key='read', **changes):
        return self.store.propose(key, 'browser.inspect', 'Find appointment options', {'url':'https://example.test/appointments', **changes})

    def submit(self, key='submit', **changes):
        return self.store.propose(key, 'browser.submit', 'Request the selected appointment', {'url':'https://example.test/appointments', 'fields':{'slot':'tomorrow at 10'}, **changes})

    def approve(self, task):
        return self.store.approve(task['id'], task['digest'])

    def run_task(self, task, outcome='succeeded'):
        self.store.set_paused(False)
        self.assertEqual(self.store.claim()['id'], task['id'])
        self.store.finish(task['id'], outcome, result={'confirmation':'fixture'})


class TaskTests(ControlFixture):
    def test_new_service_is_paused_and_does_not_claim(self):
        self.inspect()
        self.assertTrue(self.store.status()['paused'])
        self.assertIsNone(self.store.claim())

    def test_request_replay_and_changed_action_conflict(self):
        task = self.inspect()
        self.assertEqual(task['id'], self.inspect()['id'])
        with self.assertRaises(ControlError):
            self.inspect(url='https://example.test/other')

    def test_task_list_is_bounded_without_repeating_full_page_evidence(self):
        task = self.inspect()
        self.store.set_paused(False)
        self.store.claim()
        self.store.finish(task['id'], 'succeeded', {'text':'large page ' * 5000})
        listed = self.store.list_tasks()
        self.assertEqual(listed[0]['id'], task['id'])
        self.assertLess(len(canonical(listed)), 2000)
        self.assertIn('large page', self.store.get(task['id'])['result']['text'])

    def test_external_action_requires_exact_owner_approval(self):
        task = self.submit()
        self.store.set_paused(False)
        self.assertIsNone(self.store.claim())
        with self.assertRaises(ControlError):
            self.store.approve(task['id'], 'different-digest')
        with self.assertRaises(ControlError):
            self.runtime.dispatch('agent', {'method':'approve','params':{'id':task['id'],'digest':task['digest']}})
        self.approve(task)
        self.assertEqual(self.store.claim()['id'], task['id'])
        self.assertIsNone(self.store.claim())

    def test_expired_approval_cannot_execute(self):
        task = self.submit()
        self.approve(task)
        self.now += 901
        self.store.set_paused(False)
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.get(task['id'])['state'], 'expired')

    def test_expired_proposal_can_be_replaced_while_paused(self):
        task = self.submit()
        self.now += 901
        replacement = self.submit('fresh-request')
        self.assertNotEqual(replacement['id'], task['id'])
        self.assertEqual(replacement['state'], 'awaiting_approval')

    def test_recovered_memory_cannot_bypass_approval_expiry(self):
        task = self.store.propose('memory', 'memory.save', 'Remember preference', {'content':'Use short replies.'})
        self.approve(task)
        self.store.set_paused(False)
        self.store.claim()
        self.store.recover()
        self.now += 901
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.get(task['id'])['state'], 'expired')
        self.assertEqual(self.store.memories(), [])

    def test_pause_cycles_do_not_bypass_read_attempt_ceiling(self):
        task = self.inspect()
        for _ in range(3):
            self.store.set_paused(False)
            self.assertEqual(self.store.claim()['id'], task['id'])
            self.store.set_paused(True)
        self.store.set_paused(False)
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.get(task['id'])['state'], 'failed')

    def test_repeated_submissions_with_different_keys_share_one_task(self):
        task = self.submit()
        self.approve(task)
        self.run_task(task)
        duplicate = self.submit('different-key')
        self.assertEqual(duplicate['id'], task['id'])
        self.assertEqual(duplicate['state'], 'succeeded')
        self.assertIsNone(self.store.claim())

    def test_crash_after_claim_never_retries_external_action(self):
        task = self.submit()
        self.approve(task)
        self.store.set_paused(False)
        self.store.claim()
        restarted = Store(self.directory, clock=lambda: self.now)
        restarted.recover()
        self.assertEqual(restarted.get(task['id'])['state'], 'uncertain')
        self.assertIsNone(restarted.claim())
        self.assertEqual(restarted.propose('new-key', task['kind'], task['title'], task['action'])['id'], task['id'])
        with self.assertRaises(ControlError):
            restarted.retry_read(task['id'])

    def test_read_crash_can_resume_but_has_attempt_limit(self):
        task = self.inspect()
        self.store.set_paused(False)
        for _ in range(3):
            self.assertEqual(self.store.claim()['id'], task['id'])
            self.store.recover()
        self.assertEqual(self.store.get(task['id'])['state'], 'failed')
        self.assertIsNone(self.store.claim())
        with self.assertRaises(ControlError):
            self.store.retry_read(task['id'])

    def test_only_one_concurrent_worker_claims_task(self):
        self.inspect()
        self.store.set_paused(False)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            claimed = list(pool.map(lambda _: self.store.claim(), range(8)))
        self.assertEqual(sum(task is not None for task in claimed), 1)

    def test_pause_during_submit_preserves_uncertainty_over_late_success(self):
        task = self.submit()
        self.approve(task)
        self.store.set_paused(False)
        self.store.claim()
        self.store.set_paused(True)
        self.store.finish(task['id'], 'succeeded', {'confirmation':'late'})
        self.assertEqual(self.store.get(task['id'])['state'], 'uncertain')
        self.store.set_paused(False)
        self.assertIsNone(self.store.claim())

    def test_cancel_queued_and_inflight_are_distinct(self):
        task = self.inspect()
        self.assertEqual(self.store.cancel(task['id'])['state'], 'cancelled')
        task = self.submit()
        self.approve(task)
        self.store.set_paused(False)
        self.store.claim()
        self.assertEqual(self.store.cancel(task['id'])['state'], 'uncertain')

    def test_disconnect_removes_stored_session_and_invalidates_approval(self):
        self.store.configure_browser(True, ['https://example.test'], {'cookies':[{'name':'session','value':'fixture'}]})
        task = self.submit()
        self.approve(task)
        self.store.configure_browser(False)
        self.assertIsNone(self.store.connector()['storage'])
        self.assertEqual(self.store.get(task['id'])['state'], 'cancelled')
        self.store.configure_browser(True, ['https://example.test'])
        with self.assertRaises(ControlError):
            self.approve(task)

    def test_owner_must_verify_uncertain_outcome_before_new_attempt(self):
        task = self.submit()
        self.approve(task)
        self.run_task(task, 'uncertain')
        with self.assertRaises(ControlError):
            self.runtime.dispatch('agent', {'method':'resolve','params':{'id':task['id'],'completed':False,'note':'checked'}})
        resolved = self.store.resolve(task['id'], False, 'Checked destination; no appointment exists')
        self.assertEqual(resolved['state'], 'failed')
        replacement = self.submit('after-human-check')
        self.assertNotEqual(replacement['id'], task['id'])
        self.assertEqual(replacement['state'], 'awaiting_approval')

    def test_queue_events_and_approvals_survive_restart(self):
        task = self.submit()
        self.approve(task)
        cursor = self.store.events()['cursor']
        restarted = Store(self.directory, clock=lambda: self.now)
        self.assertEqual(restarted.get(task['id'])['state'], 'approved')
        self.assertEqual(restarted.events(cursor)['events'], [])
        restarted.set_paused(False)
        self.assertEqual(restarted.claim()['id'], task['id'])
        self.assertGreater(restarted.events(cursor)['cursor'], cursor)

    def test_failed_worker_is_visible_and_does_not_claim_success(self):
        task = self.inspect()
        def broken(_):
            raise RuntimeError('private credential or page text')
        self.runtime.executor = broken
        self.store.set_paused(False)
        self.runtime.run_once()
        result = self.store.get(task['id'])
        self.assertEqual(result['state'], 'failed')
        self.assertNotIn('private credential', canonical(result))
        self.assertIn('couldn', result['message'])

    def test_queue_failure_sets_fatal_health_instead_of_silently_losing_worker(self):
        def broken():
            raise RuntimeError('private database path')
        self.runtime.run_once = broken
        self.runtime.start()
        self.addCleanup(self.runtime.shutdown)
        self.assertTrue(self.runtime.failed.wait(2))
        status = self.runtime.dispatch('agent', {'method':'status'})
        self.assertTrue(status['worker_failed'])
        self.assertNotIn('private database', canonical(status))

    def test_memory_requires_approval_and_forget_redacts_source_task(self):
        content = 'Prefers short, direct replies.'
        task = self.store.propose('memory', 'memory.save', 'Remember a preference', {'content':content})
        self.assertEqual(self.store.memories(), [])
        self.approve(task)
        self.store.set_paused(False)
        self.runtime.run_once()
        memory = self.store.memories()[0]
        self.assertEqual(memory['content'], content)
        self.store.forget(memory['id'])
        self.assertEqual(self.store.memories(), [])
        self.assertNotIn(content, canonical(self.store.get(task['id'])))
        self.assertNotIn(content, canonical(self.store.events()))

    def test_agent_has_no_owner_control_methods(self):
        for method in ('resume','pause','approve','forget','connect_browser','disconnect_browser','resolve'):
            with self.subTest(method=method), self.assertRaises(ControlError):
                self.runtime.dispatch('agent', {'method':method,'params':{}})
        with self.assertRaises(ControlError):
            self.runtime.dispatch('agent', {'role':'owner','method':'resume','params':{}})


class ValidationTests(ControlFixture):
    def complete_inspection(self):
        task = self.inspect()
        self.store.set_paused(False)
        self.store.claim()
        form = {'index':0, 'action':'https://example.test/book', 'method':'POST', 'fingerprint':'fixture-hash',
                'fields':[{'name':'slot','type':'text','readOnly':False}],
                'buttons':[{'name':'','value':'','label':'Book','action':'https://example.test/book','method':'POST'}]}
        self.store.finish(task['id'], 'succeeded', {'url':'https://example.test/appointments','title':'Appointments','text':'10am available','forms':[form]})
        return {'inspection_id':task['id'],'form_index':0,'fields':{'slot':'10am'},'submit_index':0}

    def test_plan_is_built_from_inspection_and_carries_review_details(self):
        action = prepare(self.store, 'browser.submit', self.complete_inspection())
        self.assertEqual(action['target'], 'https://example.test/book')
        self.assertEqual(action['review']['page_text'], '10am available')
        self.assertEqual(action['form_fingerprint'], 'fixture-hash')

    def test_arbitrary_submit_code_or_uninspected_fields_are_rejected(self):
        action = self.complete_inspection()
        for change in ({'script':'steal()'}, {'fields':{'other':'value'}}, {'form_index':-1}):
            with self.subTest(change=change), self.assertRaises(ControlError):
                prepare(self.store, 'browser.submit', {**action, **change})

    def test_stale_inspection_and_disallowed_origin_fail(self):
        action = self.complete_inspection()
        self.now += 901
        with self.assertRaises(ControlError):
            prepare(self.store, 'browser.submit', action)
        for url in ('file:///etc/passwd', 'https://other.test/', 'https://user:password@example.test/'):
            with self.assertRaises(ControlError):
                prepare(self.store, 'browser.inspect', {'url':url})

    def test_exact_origins_and_loopback_only_in_fixture_mode(self):
        self.assertEqual(origins(['https://example.test/']), ['https://example.test'])
        for origin in ('http://example.test','https://example.test/path','https://user@example.test','http://127.0.0.1:1234'):
            with self.assertRaises(ControlError):
                origins([origin])
        self.assertEqual(origins(['http://127.0.0.1:1234'], True), ['http://127.0.0.1:1234'])


class SocketTests(ControlFixture):
    def test_role_is_selected_by_socket_not_request_payload(self):
        path = Path(self.temp.name) / 'agent.sock'
        server = Server(path, self.runtime, 'agent')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertEqual(path.stat().st_mode & 0o777, 0o660)
        self.assertTrue(call(path, 'status')['paused'])
        with self.assertRaisesRegex(ControlError, 'owner authority'):
            call(path, 'resume')

    def test_owner_socket_is_private_and_can_pause(self):
        path = Path(self.temp.name) / 'owner.sock'
        server = Server(path, self.runtime, 'owner')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(call(path, 'resume')['paused'])
        self.assertTrue(call(path, 'pause')['paused'])
