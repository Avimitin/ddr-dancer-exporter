"""HTTP and archive boundaries; no Blender/system installation required to test."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('blender_bridge', ROOT / 'service/blender_bridge.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = module.Bridge(self.temp.name, 'not-a-blender', token='test-session')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), module.handler_for(self.bridge))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.bridge.close()
        self.temp.cleanup()

    def request(self, path, method='GET', data=None, headers=None):
        common = {'Authorization': 'Bearer test-session', 'Origin': 'null'}
        common.update(headers or {})
        return urlopen(Request(self.url + path, data=data, headers=common, method=method))

    def test_static_file_origin_and_preflight(self):
        with self.request('/api/capabilities') as response:
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'null')
            self.assertTrue(json.load(response)['blender'])
        with self.request('/api/jobs', 'OPTIONS', headers={'Authorization': ''}) as response:
            self.assertEqual(response.status, 200)

    def test_authentication_origin_and_host(self):
        for headers in ({'Authorization': ''}, {'Origin': 'https://evil.example'}, {'Host': 'evil.example'}):
            with self.assertRaises(HTTPError) as error:
                self.request('/api/capabilities', headers=headers)
            self.assertIn(error.exception.code, (401, 403))
        with self.assertRaises(HTTPError) as error:
            self.request('/.github-token')
        self.assertEqual(error.exception.code, 404)

    def test_credits_and_job_cancellation(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/jobs', 'POST', b'{"credits":" "}')
        self.assertEqual(error.exception.code, 400)
        with self.request('/api/jobs', 'POST', json.dumps({'credits': 'Creator / AIGC'}).encode()) as response:
            job = json.load(response)['id']
        self.assertEqual((self.bridge.jobs[job]['root'] / '借物表.txt').read_text(encoding='utf8').strip(), 'Creator / AIGC')
        with self.request('/api/jobs/' + job, 'DELETE') as response:
            self.assertEqual(response.status, 200)
        with self.request('/api/jobs/' + job) as response:
            self.assertEqual(json.load(response)['status'], 'cancelled')

    def test_zip_traversal_and_duplicates(self):
        for names in (['../escape'], ['C:/escape'], ['A.png', 'a.png'], ['NUL.txt']):
            archive = Path(self.temp.name) / 'test.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                for name in names:
                    output.writestr(name, 'bad')
            with self.assertRaises(ValueError):
                module.extract_zip(archive, Path(self.temp.name) / 'source')
        self.assertFalse((Path(self.temp.name) / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
