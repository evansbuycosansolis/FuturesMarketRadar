"""Loopback HTTP journeys and OpenAI tool-boundary contracts; no external requests."""

import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from . import engine
from .server import DeskServer, Store


class LocalJourneys(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "desk.sqlite3")
        self.server = DeskServer(("127.0.0.1", 0), self.store)
        self.server.api_key = ""
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        default = {"Content-Type": "application/json", "X-Desk-Token": self.server.csrf_token}
        default.update(headers or {})
        req = urllib.request.Request(self.url + path, headers=default,
            data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_settings_and_cross_site_boundaries(self):
        self.assertEqual(self.request('/api/settings', {"api_key": "secret", "model": "gpt-5.4"},
                                      {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request('/api/conversations', {}, {"X-Desk-Token": "wrong"})[0], 403)
        self.assertEqual(self.request('/api/status', headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request('/api/settings', {"api_key": "test-session-secret", "model": "gpt-5.4"})[0], 200)
        _, status = self.request('/api/status')
        self.assertTrue(status['configured'])
        self.assertNotIn('test-session-secret', json.dumps(status))
        self.assertFalse(status['exchange_writes'])
        self.assertEqual(self.request('/api/settings', {"clear_key": True, "model": "gpt-5.4"})[0], 200)
        self.assertFalse(self.request('/api/status')[1]['configured'])

    def test_missing_key_failed_turn_and_busy_do_not_persist(self):
        identity = self.request('/api/conversations', {})[1]['id']
        body = {"conversation_id": identity, "role": "desk-lead", "message": "Explain the desk."}
        code, result = self.request('/api/chat', body)
        self.assertEqual(code, 400)
        self.assertIn('Settings', result['error'])
        self.assertEqual(self.store.messages(identity), [])
        with patch('local_app.server.run_agent', side_effect=engine.DeskError('quota exhausted')):
            self.assertEqual(self.request('/api/chat', body)[0], 400)
        self.assertEqual(self.store.messages(identity), [])
        self.server.turn_lock.acquire()
        try:
            self.assertEqual(self.request('/api/chat', body)[0], 409)
        finally:
            self.server.turn_lock.release()
        body['message'] = 'sk-' + 'x' * 30
        self.assertEqual(self.request('/api/chat', body)[0], 400)

    def test_chat_function_loop_and_restart_persistence(self):
        self.server.api_key = 'in-memory-test-key'
        identity = self.request('/api/conversations', {})[1]['id']
        requests = []

        def provider(payload, key):
            self.assertEqual(key, 'in-memory-test-key')
            self.assertFalse(payload['store'])
            self.assertIn('RESEARCH MODE', payload['instructions'])
            requests.append(payload)
            if len(requests) == 1:
                return {"output": [{"type": "function_call", "name": "market_snapshot", "arguments": '{"coin":"ETH"}', "call_id": "call_1"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5}}
            self.assertEqual(payload['input'][-1]['call_id'], 'call_1')
            self.assertIn('fixture-observation', payload['input'][-1]['output'])
            return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Observed fixture facts; no trading signal."}]}],
                    "usage": {"input_tokens": 20, "output_tokens": 7}}

        actual = engine.run_agent
        with patch('local_app.engine.market_snapshot', return_value={"source": "fixture-observation"}), \
             patch('local_app.server.run_agent', side_effect=lambda *a: actual(*a, requester=provider)):
            code, result = self.request('/api/chat', {"conversation_id": identity, "role": "market-analyst", "message": "Read ETH."})
        self.assertEqual(code, 200)
        self.assertEqual(result['usage'], {"input_tokens": 30, "output_tokens": 12})
        self.assertEqual(result['traces'][0]['tool'], 'market_snapshot')
        reopened = Store(self.store.path)
        messages = reopened.messages(identity)
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant'])
        self.assertEqual(messages[1]['details']['traces'][0]['result']['source'], 'fixture-observation')
        self.assertNotIn('in-memory-test-key', self.store.path.read_bytes().decode('latin1'))

    def test_unknown_write_and_file_paths_have_no_routes(self):
        self.assertEqual(self.request('/exchange', {})[0], 404)
        self.assertEqual(self.request('/api/execute', {})[0], 404)
        self.assertEqual(self.request('/../LICENSE')[0], 404)
        with patch('local_app.engine.subprocess.run') as execute:
            for name, args in [('execute_order', {}), ('read_skill', {'name': '../../secret'}), ('market_snapshot', {'coin': '--api-url'})]:
                with self.assertRaises(engine.DeskError):
                    engine.invoke_tool(name, args)
            execute.assert_not_called()

    def test_specialist_cannot_delegate(self):
        results = iter([
            {"output": [{"type": "function_call", "name": "consult_role", "arguments": '{"role":"desk-lead","task":"loop"}', "call_id": "one"}]},
            {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Cannot delegate."}]}]}
        ])
        payloads = []
        def provider(payload, _key):
            payloads.append(payload)
            return next(results)
        engine.run_agent('test', 'gpt-5.4', 'market-analyst', [], 'Research.', requester=provider, specialist=True)
        self.assertNotIn('consult_role', [t['name'] for t in payloads[0]['tools']])
        self.assertIn('not in this research', payloads[1]['input'][-1]['output'])

    def test_radar_tool_refuses_external_origin_and_hip3_guess(self):
        with patch.dict(os.environ, {"AGENTIC_RADAR_URL": "https://example.com"}):
            with self.assertRaises(engine.DeskError):
                engine.invoke_tool("radar_evidence", {"symbol": "ETH_USDT_PERP"})
        with self.assertRaises(engine.DeskError):
            engine.invoke_tool("radar_evidence", {"symbol": "xyz:TSLA"})


if __name__ == '__main__':
    unittest.main()
