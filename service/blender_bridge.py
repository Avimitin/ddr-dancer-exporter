"""Local HTTP bridge hosted by Blender's own Python. No pip/system Python needed.

Run: blender --background --disable-autoexec --python service/blender_bridge.py
Only extraction jobs use Blender; all DDR conversion happens in the browser.
"""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
import argparse
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
import time
import zipfile

MAX_UPLOAD = 512 * 1024 * 1024
MAX_UNPACKED = 1024 * 1024 * 1024


def extract_zip(archive, destination):
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > 10000 or sum(i.file_size for i in entries) > MAX_UNPACKED:
            raise ValueError('ZIP exceeds 10,000 entries or 1 GiB unpacked.')
        seen = set()
        checked = []
        for item in entries:
            path = PurePosixPath(item.filename.replace('\\', '/'))
            if path.is_absolute() or not path.parts or any(
                p in ('.', '..') or ':' in p or p.endswith((' ', '.'))
                or re.search(r'[\x00-\x1f]', p)
                or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p)
                for p in path.parts
            ):
                raise ValueError('Unsafe ZIP path.')
            mode = item.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('ZIP links and special files are not supported.')
            key = str(path).casefold()
            if key in seen:
                raise ValueError('Duplicate ZIP path.')
            seen.add(key)
            checked.append((item, destination.joinpath(*path.parts)))
        for item, path in checked:
            if item.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as reader, path.open('xb') as writer:
                    shutil.copyfileobj(reader, writer)


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        import signal
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


class Bridge:
    def __init__(self, root, blender, token=None, timeout=1800):
        self.root, self.blender = Path(root), str(blender)
        self.token = token or secrets.token_urlsafe(32)
        self.timeout = timeout
        self.jobs = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1)

    def create(self, metadata):
        credits = metadata.get('credits')
        if not isinstance(credits, str) or not credits.strip() or len(credits) > 8192:
            raise ValueError('A non-empty credit / 借物表 is required (maximum 8192 characters).')
        name = metadata.get('model', '')
        if not isinstance(name, str) or len(name) > 1024:
            raise ValueError('Invalid model selection.')
        with self.lock:
            if len(self.jobs) >= 32:
                raise ValueError('Session limit reached. Restart the launcher for more jobs.')
            identity = 'web-' + secrets.token_hex(6)
            root = self.root / 'dancers' / identity
            (root / 'source').mkdir(parents=True)
            (root / 'analysis').mkdir()
            (root / 'dancer.json').write_text(json.dumps(dict(
                id=identity, label=identity, kind='import', input_type='blend',
                credits=credits.strip(), model_id=identity.replace('-', ''),
                package_name=identity, arm_retarget=True), ensure_ascii=False), encoding='utf8')
            (root / '借物表.txt').write_text(credits.strip() + '\n', encoding='utf8')
            job = dict(id=identity, root=root, model=name, status='awaiting_upload',
                       error='', cancel=threading.Event())
            self.jobs[identity] = job
            return job

    def run(self, job):
        try:
            if job['cancel'].is_set():
                raise InterruptedError('Import cancelled.')
            job['status'] = 'extracting'
            root = job['root']
            extract_zip(root / 'input.zip', root / 'source')
            candidates = [p for p in (root / 'source').rglob('*') if p.suffix.lower() == '.blend']
            selected = (root / 'source' / job['model']).resolve() if job['model'] else None
            if selected:
                if selected not in [p.resolve() for p in candidates]:
                    raise ValueError('Selected .blend must be inside the uploaded ZIP.')
            elif len(candidates) == 1:
                selected = candidates[0]
            else:
                raise ValueError('Select one .blend model from the uploaded files.')
            job['status'] = 'importing'
            command = [self.blender, '--background', '--disable-autoexec', '--factory-startup',
                       str(selected), '--python-exit-code', '1', '--python',
                       str(self.root / 'scripts/import_blend.py'), '--', '--dancer', job['id'],
                       '--workdir', str(root)]
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            with (root / 'import.log').open('wb') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, **options)
                try:
                    start = time.monotonic()
                    while process.poll() is None:
                        if job['cancel'].wait(.2):
                            raise InterruptedError('Import cancelled.')
                        if time.monotonic() - start > self.timeout:
                            raise TimeoutError('Blender import exceeded 30 minutes.')
                    if process.returncode:
                        raise RuntimeError('Blender could not import this scene. See the import log.')
                finally:
                    stop_process(process)
            report = json.loads((root / 'analysis/pmx-inspection.json').read_text(encoding='utf8'))
            geometry = json.loads((root / 'analysis/pmx-geometry.json').read_text(encoding='utf8'))
            mapping = json.loads((root / 'bone-map.json').read_text(encoding='utf8'))
            report.pop('file', None)
            report.pop('source_file', None)
            with zipfile.ZipFile(root / 'result.zip', 'w', zipfile.ZIP_DEFLATED) as output:
                output.writestr('model.json', json.dumps(dict(source=report, mapping=mapping, base='', **geometry)))
                for texture in report['textures']:
                    path = (root / 'analysis' / texture['path']).resolve()
                    if not path.is_relative_to((root / 'analysis').resolve()):
                        raise ValueError('Texture escaped the import directory.')
                    output.write(path, texture['path'])
            job['status'] = 'cancelled' if job['cancel'].is_set() else 'complete'
        except Exception as error:
            job['error'] = str(error)
            job['status'] = 'cancelled' if job['cancel'].is_set() else 'failed'

    def close(self):
        for job in self.jobs.values():
            job['cancel'].set()
        self.pool.shutdown(wait=True, cancel_futures=True)


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'DDRLocalBridge'

        def log_message(self, *args):
            pass  # URLs and session credentials are not logged.

        def respond(self, status, data, content_type='application/json'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode('utf8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            origin = self.headers.get('Origin')
            allowed = ('null', f'http://127.0.0.1:{self.server.server_port}',
                       f'http://localhost:{self.server.server_port}')
            if origin in allowed:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
                self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
                self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
            self.wfile.write(data)

        def route(self):
            port = self.server.server_port
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{port}', f'localhost:{port}'):
                return self.respond(403, {'error': 'Invalid host'})
            origin = self.headers.get('Origin')
            if origin and origin not in ('null', f'http://127.0.0.1:{port}', f'http://localhost:{port}'):
                return self.respond(403, {'error': 'Invalid origin'})
            path = urlsplit(self.path).path
            if self.command == 'OPTIONS':
                return self.respond(200, {})
            if path.startswith('/api/'):
                if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + bridge.token):
                    return self.respond(401, {'error': 'Start the launcher to connect to Blender.'})
                return self.api(path)
            return self.respond(404, {'error': 'This bridge only provides the Blender import API.'})

        def api(self, path):
            if path == '/api/capabilities' and self.command == 'GET':
                return self.respond(200, {'blender': True, 'formats': ['blend']})
            if path == '/api/shutdown' and self.command == 'POST':
                self.respond(200, {'stopped': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path == '/api/jobs' and self.command == 'POST':
                length = self.body_length(16384)
                job = bridge.create(json.loads(self.rfile.read(length)))
                return self.respond(201, {'id': job['id']})
            match = re.fullmatch(r'/api/jobs/(web-[0-9a-f]{12})(/result)?', path)
            if not match or match[1] not in bridge.jobs:
                return self.respond(404, {'error': 'Unknown job'})
            job = bridge.jobs[match[1]]
            if self.command == 'GET' and match[2]:
                if job['status'] != 'complete':
                    return self.respond(409, {'error': 'Import is not complete'})
                return self.respond(200, (job['root'] / 'result.zip').read_bytes(), 'application/zip')
            if self.command == 'GET':
                logfile = job['root'] / 'import.log'
                log = ''
                if logfile.exists():
                    with logfile.open('rb') as source:
                        source.seek(max(0, logfile.stat().st_size - 12000))
                        log = source.read().decode('utf8', errors='replace')
                return self.respond(200, {k: job[k] for k in ('id', 'status', 'error')} | {'log': log})
            if self.command == 'DELETE':
                job['cancel'].set()
                if job['status'] in ('awaiting_upload', 'queued'):
                    job['status'] = 'cancelled'
                return self.respond(200, {'cancelled': True})
            if self.command == 'PUT' and not match[2]:
                length = self.body_length(MAX_UPLOAD)
                with bridge.lock:
                    if job['status'] != 'awaiting_upload':
                        return self.respond(409, {'error': 'Job already uploaded'})
                    job['status'] = 'uploading'
                try:
                    self.connection.settimeout(60)
                    with (job['root'] / 'input.zip').open('xb') as output:
                        while length:
                            if job['cancel'].is_set():
                                raise InterruptedError('Import cancelled.')
                            chunk = self.rfile.read(min(length, 1024 * 1024))
                            if not chunk:
                                raise ValueError('Incomplete upload')
                            output.write(chunk)
                            length -= len(chunk)
                    job['status'] = 'queued'
                    bridge.pool.submit(bridge.run, job)
                except Exception:
                    job['status'] = 'failed'
                    raise
                return self.respond(202, {'id': job['id']})
            return self.respond(405, {'error': 'Method not allowed'})

        def body_length(self, maximum):
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 < length <= maximum or self.headers.get('Transfer-Encoding'):
                raise ValueError('Missing or excessive Content-Length')
            return length

        def dispatch(self):
            try:
                self.route()
            except (ValueError, KeyError, zipfile.BadZipFile) as error:
                self.respond(400, {'error': str(error)})
            except (ConnectionError, TimeoutError):
                pass
            except Exception:
                self.respond(500, {'error': 'Local service error. Restart the launcher and retry.'})

        do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = dispatch
    return Handler


def main():
    import bpy  # Available only inside Blender; no external Python dependency.
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--token-file', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    root = Path(__file__).resolve().parents[1]
    token = args.token_file.read_text(encoding='utf8').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('Invalid bridge session token.')
    bridge = Bridge(root, bpy.app.binary_path, token=token)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(bridge))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        bridge.close()


if __name__ == '__main__':
    main()
