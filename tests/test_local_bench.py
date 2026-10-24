import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/lib'))
import local_bench as bench
import synthetic_pack


def reply(content='', tool_calls=None):
    msg = {'role': 'assistant', 'content': content}
    if tool_calls:
        msg['tool_calls'] = tool_calls
    return {'choices': [{'message': msg}]}


class FakeClient:
    """Answers by matching a substring of the last user message."""

    def __init__(self, answers, reject_tools=False):
        self.answers, self.reject_tools, self.calls = answers, reject_tools, []

    def chat(self, messages, **params):
        self.calls.append(params)
        if self.reject_tools and 'tools' in params:
            raise bench.BenchError('server returned HTTP 400')
        text = messages[-1]['content']
        for needle, answer in self.answers.items():
            if needle in text:
                return answer
        return reply('{}')

    def stream(self, messages, max_tokens=128):
        return {'ttft_s': 0.5, 'total_s': 2.0, 'chunks': 20, 'text': 'ok'}


class PackTests(unittest.TestCase):
    def test_pack_is_deterministic_fictional_and_private_on_disk(self):
        self.assertEqual(synthetic_pack.build(3), synthetic_pack.build(3))
        pack = synthetic_pack.build(3)
        self.assertTrue(pack['persona']['email'].endswith('@example.com'))
        self.assertTrue(pack['persona']['phone'].startswith('555-01'))
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'pack'
            synthetic_pack.write(pack, out)
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            report = (out / 'lab-report.txt').read_text()
            self.assertIn(pack['persona']['name'], report)
            self.assertIn(str(pack['labs']['ldl_mg_dl']), report)
            self.assertEqual(json.loads((out / 'manifest.json').read_text())['seed'], 3)


class BenchTests(unittest.TestCase):
    def setUp(self):
        self.pack = synthetic_pack.build(7)

    def test_loopback_guard(self):
        bench.require_loopback('http://127.0.0.1:8080/v1', allow=False)
        bench.require_loopback('http://localhost:8080/v1', allow=False)
        with self.assertRaises(bench.BenchError):
            bench.require_loopback('https://api.example.com/v1', allow=False)
        bench.require_loopback('https://api.example.com/v1', allow=True)

    def test_extract_json_ignores_thinking_and_fences(self):
        text = '<think>{"query": "secret"}</think>\n```json\n{"query": "ldl ranges", "needs_approval": false}\n```'
        self.assertEqual(bench.extract_json(text)['query'], 'ldl ranges')
        self.assertIsNone(bench.extract_json('no json here'))

    def test_tool_calls_native_prompted_and_none(self):
        native = {'tool_calls': [{'function': {'name': 'add_task', 'arguments': '{"text": "Oat milk"}'}}]}
        self.assertEqual(bench.parse_tool_call(native), ('add_task', {'text': 'Oat milk'}, 'native'))
        prompted = {'content': '{"tool": "search_notes", "arguments": {"query": "passport"}}'}
        self.assertEqual(bench.parse_tool_call(prompted)[2], 'prompted')
        self.assertEqual(bench.parse_tool_call({'content': 'Doing well!'}), (None, {}, 'none'))
        self.assertTrue(bench.tool_case_passes('add_task', {'text': 'oat milk'}, 'add_task', {'text': 'Oat milk'}))
        self.assertFalse(bench.tool_case_passes(None, {}, 'add_task', {}))

    def test_b1_falls_back_when_server_rejects_tools(self):
        answers = {'oat milk': reply('{"tool": "add_task", "arguments": {"text": "oat milk"}}')}
        result = bench.suite_b1(FakeClient(answers, reject_tools=True), self.pack)
        self.assertTrue(result['cases'][0]['pass'])
        self.assertEqual(result['cases'][0]['mode'], 'prompted')

    def test_query_scoring_leak_escalation_and_topic(self):
        case = {'id': 'H1', 'topic': ['ldl']}
        name = self.pack['persona']['name']
        clean = bench.score_query(case, {'query': 'LDL reference ranges', 'needs_approval': False}, self.pack)
        self.assertEqual((clean['leak'], clean['on_topic']), (False, True))
        leaked = bench.score_query(case, {'query': f'{name} LDL 187', 'needs_approval': False}, self.pack)
        self.assertTrue(leaked['leak'])
        self.assertIn('sensitive-term', leaked['rules'])
        escalated = bench.score_query(case, {'query': f'{name} LDL', 'needs_approval': True}, self.pack)
        self.assertEqual((escalated['leak'], escalated['escalated']), (False, True))
        invalid = bench.score_query(case, None, self.pack)
        self.assertFalse(invalid['valid'])

    def test_b2_counts_injected_leak(self):
        mrn = self.pack['persona']['mrn']
        answers = {'LDL targets': reply(json.dumps({'query': f'LDL targets {mrn}', 'needs_approval': False}))}
        result = bench.suite_b2(FakeClient(answers), self.pack)
        injected = next(c for c in result['cases'] if c['id'] == 'I1')
        self.assertTrue(injected['leak'])
        self.assertGreaterEqual(result['leaks'], 1)
        self.assertFalse(bench.evaluate({'b2': result})['B2 no leaks'])

    def test_b3_numeric_comparison(self):
        labs = self.pack['labs']
        answer = {'ldl': '187', 'hdl': 38, 'total_cholesterol': 262, 'triglycerides': 214,
                  'hba1c': '6.1%', 'collection_year': 2026}
        result = bench.suite_b3(FakeClient({'NORTHFALL': reply(json.dumps(answer))}), self.pack)
        self.assertTrue(all(result['cases'][0]['fields'].values()))
        self.assertEqual(labs['ldl_mg_dl'], 187)
        self.assertFalse(bench.number_equal(187, 'n/a'))

    def test_client_against_loopback_server(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self._send('application/json', json.dumps({'data': [{'id': 'local-model'}]}).encode())

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if body.get('stream'):
                    events = [{'choices': [{'delta': {'content': 'Hi'}}]}, {'choices': []},
                              {'choices': [{'delta': {'content': ' there'}}]}]
                    data = ''.join(f'data: {json.dumps(e)}\n\n' for e in events) + 'data: [DONE]\n\n'
                    self._send('text/event-stream', data.encode())
                else:
                    self._send('application/json', json.dumps(reply('pong')).encode())

            def _send(self, kind, data):
                self.send_response(200)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        client = bench.Client(f'http://127.0.0.1:{server.server_port}/v1', 'local-model', timeout=5)
        self.assertEqual(client.models(), ['local-model'])
        self.assertEqual(bench.message(client.chat([{'role': 'user', 'content': 'ping'}]))['content'], 'pong')
        streamed = client.stream([{'role': 'user', 'content': 'hi'}])
        self.assertEqual((streamed['text'], streamed['chunks']), ('Hi there', 2))
        self.assertIsNotNone(streamed['ttft_s'])

    def test_run_and_gate(self):
        results = bench.run(FakeClient({}), ['b4'], self.pack, {'model': 'fake'}, {'long_context': []})
        self.assertTrue(results['gate']['B4 latency'])
        self.assertIsNone(results['gate']['B4 long context'])
        self.assertIsNone(results['gate']['B1 tool calls'])

    def test_long_context_needle_and_gate(self):
        prompt = bench.long_prompt(2000, seed=1)
        self.assertIn(bench.NEEDLE_FACT, prompt)
        self.assertGreaterEqual(len(prompt), 8000)

        class Recall(FakeClient):
            def stream(self, messages, max_tokens=128):
                found = bench.NEEDLE_FACT in messages[-1]['content']
                return {'ttft_s': 4.0, 'total_s': 5.0, 'chunks': 3, 'text': '4417' if found else 'ok'}

        result = bench.suite_b4(Recall({}), self.pack, {'long_context': [8000]})
        self.assertTrue(result['long_context'][0]['needle_found'])
        self.assertTrue(bench.evaluate({'b4': result})['B4 long context'])
        result['long_context'][0]['ttft_s'] = 30.0
        self.assertFalse(bench.evaluate({'b4': result})['B4 long context'])

    def test_embeddings_ordering(self):
        class Embedder:
            def embed(self, texts):
                topics = ('cholesterol', 'ldl', 'debt', 'card', 'lisbon')
                return [[1.0 if any(t in text.lower() for t in topics[i:i + 2]) else 0.1
                         for i in (0, 2, 4)] for text in texts]

        result = bench.suite_b7(FakeClient({}), self.pack, {'embedder': Embedder()})
        self.assertEqual(result['ordered'], [True, True, True])
        self.assertTrue(bench.evaluate({'b7': result})['B7 embeddings'])
        with self.assertRaises(bench.BenchError):
            bench.suite_b7(FakeClient({}), self.pack, {})


if __name__ == '__main__':
    unittest.main()
