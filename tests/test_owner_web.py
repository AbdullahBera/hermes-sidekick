import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from sidekick_control.client import call
from sidekick_control.owner_web import OwnerServer, access_token
from sidekick_control.service import Runtime, Server, LOGIN_METHODS
from sidekick_control.store import Store, ControlError


class OwnerWebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sk-owner-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.store=Store(self.base/'state')
        self.runtime=Runtime(self.store,allow_loopback=True)
        self.socket=Server(self.base/'owner.sock',self.runtime,'owner')
        threading.Thread(target=self.socket.serve_forever,daemon=True).start()
        self.addCleanup(self.socket.server_close)
        self.addCleanup(self.socket.shutdown)
        self.token=access_token(self.base/'private'/'token')
        self.web=OwnerServer(0,self.base/'owner.sock',self.token)
        threading.Thread(target=self.web.serve_forever,daemon=True).start()
        self.addCleanup(self.web.server_close)
        self.addCleanup(self.web.shutdown)

    def post(self, method, params=None, **overrides):
        headers={'Content-Type':'application/json','Origin':self.web.origin,'Authorization':'Bearer '+self.token}
        headers.update(overrides)
        connection=http.client.HTTPConnection('127.0.0.1',self.web.server_port,timeout=5)
        try:
            connection.request('POST','/api',json.dumps({'method':method,'params':params or {}}),headers)
            response=connection.getresponse()
            return response.status,json.loads(response.read()),dict(response.getheaders())
        finally: connection.close()

    def test_owner_can_review_and_approve_exact_action(self):
        task=self.store.propose('fixture-memory','memory.save','Remember a preference',{'content':'Use concise replies.'})
        status,data,headers=self.post('task',{'id':task['id']})
        self.assertEqual(status,200)
        self.assertEqual(data['result']['action']['content'],'Use concise replies.')
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(headers['X-Frame-Options'],'DENY')
        self.assertEqual(self.post('approve',{'id':task['id'],'digest':'wrong'})[0],400)
        self.assertEqual(self.post('approve',{'id':task['id'],'digest':task['digest']})[0],200)
        self.assertEqual(self.store.get(task['id'])['state'],'approved')

    def test_token_origin_host_and_csrf_rejections_do_not_resume_work(self):
        bad=[{'Authorization':'Bearer wrong'},{'Authorization':''},{'Origin':'https://evil.example'},
             {'Origin':''},{'Host':'evil.example'},{'Sec-Fetch-Site':'cross-site'}]
        for headers in bad:
            with self.subTest(headers=headers):
                self.assertEqual(self.post('resume',**headers)[0],403)
                self.assertTrue(self.store.status()['paused'])
        self.assertEqual(self.post('resume')[0],200)
        self.assertFalse(self.store.status()['paused'])

    def test_web_surface_cannot_import_or_export_raw_credentials(self):
        for method in ('connect_browser','propose','read_storage','exec'):
            self.assertEqual(self.post(method)[0],400)

    def test_agent_socket_rejects_all_login_methods(self):
        for method in LOGIN_METHODS:
            with self.subTest(method=method),self.assertRaises(ControlError):
                self.runtime.dispatch('agent',{'method':method,'params':{}})

    def test_token_is_private_and_rotation_invalidates_previous_value(self):
        path=self.base/'private'/'token'
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
        self.assertNotEqual(access_token(path,rotate=True),self.token)
        path.chmod(0o644)
        with self.assertRaises(ControlError):access_token(path,rotate=True)

    def test_static_assets_have_no_token_and_block_untrusted_host(self):
        connection=http.client.HTTPConnection('127.0.0.1',self.web.server_port)
        connection.request('GET','/')
        response=connection.getresponse();html=response.read().decode()
        self.assertEqual(response.status,200)
        self.assertNotIn(self.token,html)
        connection.close()
        connection=http.client.HTTPConnection('127.0.0.1',self.web.server_port)
        connection.request('GET','/',headers={'Host':'attacker.example'})
        response=connection.getresponse();response.read()
        self.assertEqual(response.status,403)
        connection.close()


class LoginSafetyTests(unittest.TestCase):
    def test_pause_can_interrupt_login_without_waiting_for_navigation(self):
        import concurrent.futures
        from types import SimpleNamespace
        entered, release = threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'state')
            runtime=Runtime(store)
            state={'active':True}
            def command(*args,**kwargs):
                entered.set()
                if not release.wait(3): raise RuntimeError('fixture timed out')
                return {'storage':{'cookies':[{'name':'fixture','value':'private-session'}],'origins':[]}}
            def close():
                state['active']=False
                release.set()
            runtime.handoff=SimpleNamespace(active=lambda:state['active'],session_id='fixture',
                origins=['https://example.test'],command=command,close=close)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                finishing=pool.submit(runtime.dispatch,'owner',{'method':'finish_login','params':{'session_id':'fixture','confirmed':True}})
                self.assertTrue(entered.wait(2))
                runtime.dispatch('owner',{'method':'pause'})
                with self.assertRaises(ControlError):finishing.result(timeout=2)
            self.assertIsNone(store.connector()['storage'])
            self.assertFalse(store.connector()['enabled'])
            self.assertTrue(store.status()['paused'])

    def test_expired_handoff_is_destroyed_while_worker_is_paused(self):
        import io
        from types import SimpleNamespace
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            runtime=Runtime(Store(Path(directory)/'state'))
            runtime.handoff.clock=lambda:1000
            runtime.handoff.expires=999
            runtime.handoff.session_id='expired'
            runtime.handoff.process=SimpleNamespace(pid=123456,poll=lambda:None,wait=lambda **_:None,stdin=io.StringIO())
            with patch('sidekick_control.handoff.os.killpg') as kill:
                self.assertFalse(runtime.run_once())
                kill.assert_called_once()
            self.assertIsNone(runtime.handoff.session_id)
            self.assertIsNone(runtime.handoff.process)
