import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import sync_engine as sync


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'repo'
        self.home = self.base / '.hermes'
        self.home.mkdir()
        shutil.copytree(ROOT / 'plugins', self.root / 'plugins')
        shutil.copytree(ROOT / 'config', self.root / 'config')
        self.profile = yaml.safe_load((ROOT / 'profile.example.yaml').read_text())
        for directory in sync.CATEGORIES:
            for block in self.profile[directory].values():
                block['enabled'] = False
        self.config = {'model': {'provider': 'anthropic'}, 'mcp_servers': {
            'gmail': {'enabled': False, 'command': 'workspace-mcp', 'env': {'TEST_VALUE': 'private-placeholder'}},
            'calendar': {'enabled': False, 'command': 'workspace-mcp'},
            'contacts': {'enabled': False, 'command': 'workspace-mcp'},
            'unrelated': {'enabled': True, 'command': 'example'},
        }}
        self.save_profile()
        self.save_config()
        self.write('cron/jobs.json', '{"jobs": []}')
        self.calls = []

    def write(self, name, content):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def save_profile(self):
        self.write('sidekick/profile.yaml', yaml.safe_dump(self.profile))

    def save_config(self):
        self.write('config.yaml', yaml.safe_dump(self.config))

    def enable(self, pid='morning-brief'):
        self.profile['channels']['signal']['enabled'] = True
        for cid in ('gmail', 'calendar'):
            self.profile['connectors'][cid]['enabled'] = True
            self.config['mcp_servers'][cid]['enabled'] = True
        self.profile['automations'][pid]['enabled'] = True
        self.save_profile()
        self.save_config()

    def job(self, name='morning-brief', **changes):
        job = {'id': 'job-fixture', 'name': name, 'enabled': True, 'paused_at': None,
               'prompt': (self.root / 'plugins/automations' / name / 'prompt.md').read_text(),
               'schedule': {'expr': '0 8 * * *'}, 'deliver': 'signal'}
        job.update(changes)
        self.write('cron/jobs.json', json.dumps({'jobs': [job]}))
        return job

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}

    def run_sync(self, apply=False, runner=None):
        with contextlib.redirect_stdout(io.StringIO()):
            sync.sync(self.root, self.home, apply, runner or self.record,
                      gateway=lambda: ['reload-gateway'])

    def record(self, args):
        """Fake Hermes CLI persists its state, allowing read-after-write verification."""
        self.calls.append(args)
        if args[:2] != ['hermes', 'cron']:
            return
        jobs = list(sync.load_jobs(self.home / 'cron/jobs.json').values())
        action = args[2]
        if action == 'create':
            jobs.append({'id': 'created-' + args[6], 'name': args[6], 'prompt': args[4],
                         'schedule': {'expr': args[3]}, 'deliver': args[8], 'enabled': True})
        else:
            job = next(j for j in jobs if j['id'] == args[3])
            if action == 'edit':
                field = args[4][2:]
                job[field] = {'expr': args[5]} if field == 'schedule' else args[5]
            else:
                job.update(enabled=action == 'resume', paused_at=None,
                           state='active' if action == 'resume' else 'paused')
        self.write('cron/jobs.json', json.dumps({'jobs': jobs}))

    def assert_rejected_without_changes(self):
        before = self.snapshot()
        with self.assertRaises(sync.SyncError):
            self.run_sync(True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls, [])


class SyncTests(Fixture):
    def test_invalid_or_missing_profile_never_pauses_jobs(self):
        self.job()
        for content in ('core: [unterminated', '[]', '{}', 'null'):
            with self.subTest(content=content):
                self.write('sidekick/profile.yaml', content)
                self.assert_rejected_without_changes()
        (self.home / 'sidekick/profile.yaml').unlink()
        self.assert_rejected_without_changes()

    def test_wrong_types_aliases_and_unknown_ids_fail_closed(self):
        original = copy.deepcopy(self.profile)
        for directory, value in [('connectors', []), ('channels', {'signal': True}),
                                 ('automations', {'morning-brief': {'enabled': 'false'}}),
                                 ('connectors', {'typo': {'enabled': True}}),
                                 ('connectors', {'read-url': {'enabled': False}, 'read_url': {'enabled': False}})]:
            with self.subTest(directory=directory, value=value):
                self.profile = copy.deepcopy(original)
                self.profile[directory] = value
                self.save_profile()
                self.assert_rejected_without_changes()

    def test_invalid_time_timezone_and_dependency_fail_before_writes(self):
        for value in ('25:00', '08:60', '8am', 800):
            self.profile['automations']['morning-brief']['time'] = value
            self.save_profile()
            self.assert_rejected_without_changes()
        self.profile['automations']['morning-brief']['time'] = '08:00'
        self.profile['core']['timezone'] = 'Unknown/Zone'
        self.save_profile()
        self.assert_rejected_without_changes()
        self.profile['core']['timezone'] = 'UTC'
        self.profile['automations']['morning-brief']['enabled'] = True
        self.save_profile()
        self.assert_rejected_without_changes()

    def test_catalog_is_validated_before_soul_or_prompt_writes(self):
        for content in ('[]', 'id: broken', 'security: [vm]'):
            (self.root / 'plugins/automations/morning-brief/plugin.yaml').write_text(content)
            self.assert_rejected_without_changes()

    def test_missing_prompt_or_soul_fails_before_changes(self):
        (self.root / 'plugins/automations/morning-brief/prompt.md').unlink()
        self.assert_rejected_without_changes()

    def test_bad_cron_state_and_duplicates_fail_closed(self):
        for content in ('[', 'false', '{"jobs": "bad"}', '{"jobs": [{}]}'):
            self.write('cron/jobs.json', content)
            self.assert_rejected_without_changes()
        job = self.job()
        self.write('cron/jobs.json', json.dumps([job, dict(job, id='other')]))
        self.assert_rejected_without_changes()

    def test_empty_quoted_key_is_not_present(self):
        self.write('.env', 'ANTHROPIC_API_KEY=""\n')
        self.assertEqual(sync.env_values(self.home / '.env')['ANTHROPIC_API_KEY'], '')

    def test_duplicate_yaml_keys_are_rejected(self):
        self.write('sidekick/profile.yaml', 'version: 1\nversion: 1\n')
        self.assert_rejected_without_changes()

    def test_profile_timezone_is_deployed_and_conflicting_override_rejected(self):
        self.profile['core']['timezone'] = 'Europe/London'
        self.save_profile()
        self.run_sync(True)
        self.assertEqual(sync.read_yaml(self.home / 'config.yaml')['timezone'], 'Europe/London')
        self.calls.clear()
        self.write('.env', 'HERMES_TIMEZONE=America/Los_Angeles\n')
        self.assert_rejected_without_changes()

    def test_check_is_read_only_and_does_not_run_commands(self):
        self.enable()
        before = self.snapshot()
        self.run_sync()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls, [])

    def test_create_and_second_apply_are_idempotent(self):
        self.enable()
        self.run_sync(True)
        self.assertEqual(len([c for c in self.calls if c[:3] == ['hermes', 'cron', 'create']]), 1)
        before = self.snapshot()
        self.calls.clear()
        self.run_sync(True)
        self.assertEqual(self.calls, [])
        self.assertEqual(before, self.snapshot())
        self.assertEqual((self.home / 'SOUL.md').stat().st_mode & 0o777, 0o600)

    def test_failed_cron_create_edit_pause_and_resume_stop_processing(self):
        self.enable()
        for action in ('create', 'edit', 'pause', 'resume'):
            with self.subTest(action=action):
                self.calls.clear()
                self.profile['automations']['morning-brief']['enabled'] = action != 'pause'
                self.save_profile()
                self.write('cron/jobs.json', '[]')
                if action != 'create':
                    changes = {'prompt': 'old prompt'} if action == 'edit' else {}
                    if action == 'resume':
                        changes['enabled'] = False
                    self.job(**changes)
                def fail(args):
                    if args[:3] == ['hermes', 'cron', action]:
                        self.calls.append(args)
                        raise sync.SyncError('injected command failure')
                    self.record(args)
                with self.assertRaisesRegex(sync.SyncError, 'failed'):
                    self.run_sync(True, fail)
                self.assertEqual(self.calls[-1][:3], ['hermes', 'cron', action])

    def test_command_success_without_persisted_change_is_not_success(self):
        self.enable()
        with self.assertRaisesRegex(sync.SyncError, 'post-apply verification'):
            self.run_sync(True, self.calls.append)

    def test_failed_reload_is_retried_even_when_files_match(self):
        def fail(args):
            raise sync.SyncError('service unavailable')
        with self.assertRaises(sync.SyncError):
            self.run_sync(True, fail)
        self.assertTrue((self.home / 'sidekick/reload-required').exists())
        self.run_sync(True)
        self.assertIn(['reload-gateway'], self.calls)
        self.assertFalse((self.home / 'sidekick/reload-required').exists())

    def test_mcp_toggle_preserves_credentials_and_unrelated_servers(self):
        self.config['mcp_servers']['gmail']['enabled'] = True
        self.save_config()
        self.run_sync(True)
        result = sync.read_yaml(self.home / 'config.yaml')
        self.assertFalse(result['mcp_servers']['gmail']['enabled'])
        self.assertEqual(result['mcp_servers']['gmail']['env'], self.config['mcp_servers']['gmail']['env'])
        self.assertEqual(result['mcp_servers']['unrelated'], self.config['mcp_servers']['unrelated'])
        self.assertIn(['reload-gateway'], self.calls)
        self.profile['connectors']['gmail']['enabled'] = True
        self.save_profile()
        self.run_sync(True)
        self.assertTrue(sync.read_yaml(self.home / 'config.yaml')['mcp_servers']['gmail']['enabled'])

    def test_enabled_mcp_missing_registration_fails_before_writes(self):
        self.enable()
        del self.config['mcp_servers']['gmail']
        self.save_config()
        self.assert_rejected_without_changes()

    def test_schedule_removal_pauses_existing_standalone_job(self):
        self.enable('email-triage')
        self.job('email-triage')
        self.run_sync(True)
        self.assertIn(['hermes', 'cron', 'pause', 'job-fixture'], self.calls)

    def test_delivery_drift_is_reconciled_and_channel_is_required(self):
        self.enable()
        self.job(deliver='local')
        self.run_sync(True)
        self.assertIn(['hermes', 'cron', 'edit', 'job-fixture', '--deliver', 'signal'], self.calls)
        self.calls.clear()
        self.profile['channels']['signal']['enabled'] = False
        self.save_profile()
        self.assert_rejected_without_changes()

    def test_numeric_cron_validation(self):
        self.assertEqual(sync.cron_expr('*/15 8-17 * * 1-5'), '*/15 8-17 * * 1-5')
        self.assertEqual(sync.cron_expr('0 8 * * 0', '09:30'), '30 9 * * 0')
        for expression in ('61 * * * *', '* 24 * * *', '* * 0 * *', '* * * 13 *', '* * * * 9', '*/0 * * * *', 'bad'):
            with self.subTest(expression=expression), self.assertRaises(sync.SyncError):
                sync.cron_expr(expression)

    def test_command_output_is_not_leaked(self):
        result = subprocess.CompletedProcess([], 7, 'private output', 'credential value')
        with patch.object(sync.subprocess, 'run', return_value=result):
            with self.assertRaises(sync.SyncError) as caught:
                sync.run_command(['hermes', 'cron', 'pause', 'fixture'])
        self.assertNotIn('private output', str(caught.exception))
        self.assertNotIn('credential value', str(caught.exception))

    def test_cli_invalid_profile_returns_nonzero_without_changes(self):
        self.write('sidekick/profile.yaml', '[]')
        before = self.snapshot()
        with patch.object(sys, 'argv', ['sync_engine.py', 'apply', str(self.root)]), patch.object(Path, 'home', return_value=self.base), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(), 2)
        self.assertEqual(before, self.snapshot())

    def test_concurrent_apply_is_rejected_before_writes(self):
        before = self.snapshot()
        lock = os.open(self.home, os.O_RDONLY)
        try:
            sync.fcntl.flock(lock, sync.fcntl.LOCK_EX | sync.fcntl.LOCK_NB)
            with patch.object(sys, 'argv', ['sync_engine.py', 'apply', str(self.root)]), patch.object(Path, 'home', return_value=self.base), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sync.main(), 2)
        finally:
            os.close(lock)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
