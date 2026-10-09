"""Real loopback HTTP regression tests; no Qt or simulator dependency."""

import concurrent.futures
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.app.services.webui_server import WebUiServer
from backend.app.services.webui_stream import LatestStream


class WebUiServerTests(unittest.TestCase):
    def setUp(self):
        self.generation = 0
        self.commands = []

        def commit(fields, generation):
            self.generation += 1
            return {'generation': self.generation, 'fields': fields}

        def command(action, params):
            if action == 'invalid':
                raise ValueError('未知命令')
            if action == 'timeout':
                raise TimeoutError('主线程未响应')
            self.commands.append((action, params))
            return {'ok': True, 'message': action}

        self.stream = LatestStream()
        self.stream.publish('clock', {'gameTime': 0, 'fixedFrame': 0})
        self.server = WebUiServer(lambda: {'clock': {'gameTime': 0}},
                                  lambda: {'generation': self.generation, 'fields': {}},
                                  commit, command, lambda name: '# ' + name,
                                  streams={'clock': self.stream})
        self.url = self.server.start()

    def tearDown(self):
        self.server.stop()

    def request(self, path, body=None, headers=None, raw=None):
        request_headers = headers or {}
        data = None
        if body is not None or raw is not None:
            data = raw if raw is not None else json.dumps(body).encode()
            request_headers = {'Content-Type': 'application/json', **request_headers}
        request = Request(self.url + path.lstrip('/'), data=data, headers=request_headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_assets_and_state_have_same_origin_and_no_mock_clock(self):
        status, body, headers = self.request('/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['clock']['gameTime'], 0)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        status, body, headers = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn('明日方舟 Timeline', body.decode())
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        status, body, _ = self.request('/app.mjs')
        self.assertEqual(status, 200)
        self.assertIn(b'/api/state', body)
        status, body, headers = self.request('/tableLayout.mjs')
        self.assertEqual(status, 200)
        self.assertIn(b'createTableLayout', body)
        self.assertIn('text/javascript', headers['Content-Type'])

    def test_policy_generation_serializes_two_competing_commits(self):
        payload = {'generation': 0, 'fields': {'enemy.hp': {'collect': False}}}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.request('/api/policy', payload)[0], range(2)))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(self.generation, 1)

    def test_origin_host_and_path_traversal_rejected(self):
        self.assertEqual(self.request('/api/state', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/command', {'action': 'enemy-scan'}, {'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/state', headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request('/%2e%2e/backend/desktop_app.py')[0], 404)
        self.assertEqual(self.request('/..%5cbackend%5cdesktop_app.py')[0], 404)
        self.assertEqual(self.request('/.git/config')[0], 404)
        self.assertEqual(self.request('/api/docs/../state')[0], 404)

    def test_json_validation_and_command_failures_are_real(self):
        self.assertEqual(self.request('/api/command', raw=b'null')[0], 400)
        self.assertEqual(self.request('/api/command', raw=b'{broken')[0], 400)
        self.assertEqual(self.request('/api/command', {'action': 'enemy-scan'}, {'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.request('/api/command', {'action': 'invalid'})[0], 400)
        self.assertEqual(self.request('/api/command', {'action': 'timeout'})[0], 503)
        self.assertEqual(self.request('/api/command', {'action': 'enemy-scan', 'params': []})[0], 400)
        self.assertEqual(self.request('/api/command', {'action': 'enemy-scan', 'params': {'force': True}})[0], 200)
        self.assertEqual(self.commands, [('enemy-scan', {'force': True})])
        self.assertEqual(self.request('/api/command', raw=b'x' * 262145)[0], 413)
        self.assertEqual(self.request('/api/policy', {'generation': True, 'fields': {}})[0], 400)

    def test_docs_are_returned_as_text_for_safe_markdown_rendering(self):
        status, data, _ = self.request('/api/docs/guide')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {'markdown': '# guide'})

    def test_stream_admission_preserves_command_slots_and_reconnect_gets_latest(self):
        connections = []
        try:
            for _ in range(4):
                response = urlopen(self.url + 'api/stream/clock', timeout=2)
                connections.append(response)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                packet = json.loads(response.readline()[6:])
                self.assertEqual(packet['data']['fixedFrame'], 0)
            self.assertEqual(self.request('/api/stream/clock')[0], 503)
            self.assertEqual(self.request('/api/command', {'action': 'still-responsive'})[0], 200)
            self.assertEqual(self.request('/api/stream/unknown')[0], 404)
            self.assertEqual(self.request('/api/stream/clock', headers={'Origin': 'https://evil.example'})[0], 403)
            self.stream.publish('clock', {'fixedFrame': 200})
            while line := connections[0].readline():
                if line.startswith(b'data: '):
                    packet = json.loads(line[6:])
                    break
            self.assertEqual(packet['data']['fixedFrame'], 200)
        finally:
            for response in connections:
                response.close()


if __name__ == '__main__':
    unittest.main()
