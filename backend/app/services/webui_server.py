"""Loopback Web UI transport; all game and Qt work belongs to injected callbacks.

HTTP workers consume frozen state and submit commands through the application's
main-thread dispatcher. They never read memory or touch widgets directly.
"""

import json
import logging
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

_LOG = logging.getLogger(__name__)


class _BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler):
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        # Slow/malformed local callers must not create unlimited HTTP threads.
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class WebUiServer:
    """Serve bundled assets and validated JSON API on an ephemeral loopback port.

    ``policy_commit(fields, expected_generation)`` must validate and persist one
    atomic transaction. ``command(action, params)`` must dispatch to the main
    thread and return a real result, or raise when it cannot complete.
    """

    def __init__(self, state_provider, policy_provider, policy_commit, command,
                 docs, asset_dir=None, port=0, download=None, streams=None):
        self._state = state_provider
        self._policy = policy_provider
        self._commit = policy_commit
        self._command = command
        self._docs = docs
        self._download = download
        self._assets = Path(asset_dir or Path(__file__).resolve().parents[3] / "webui").resolve()
        self._port = port
        self._server = None
        self._thread = None
        self._commit_lock = threading.Lock()
        self._streams = streams or {}
        # At most four tabs (two channels each), leaving HTTP slots for commands.
        self._stream_slots = {key: threading.BoundedSemaphore(4) for key in self._streams}

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_port}/" if self._server else None

    def start(self):
        if self._server:
            return self.url
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, format, *args):
                _LOG.debug("Web UI: " + format, *args)

            def _send(self, status, data, content_type="application/json; charset=utf-8"):
                if not isinstance(data, bytes):
                    data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(data)

            def _validate_caller(self):
                allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                if self.headers.get("Host") not in allowed:
                    self._send(403, {"error": "仅允许本机地址访问"})
                    return False
                origin = self.headers.get("Origin")
                if origin and origin != "http://" + self.headers.get("Host", ""):
                    self._send(403, {"error": "拒绝跨来源访问"})
                    return False
                if self.headers.get("Sec-Fetch-Site") == "cross-site":
                    self._send(403, {"error": "拒绝跨站访问"})
                    return False
                return True

            def do_GET(self):
                if not self._validate_caller():
                    return
                path = unquote(urlsplit(self.path).path)
                try:
                    if path.startswith('/api/stream/'):
                        channel = path.rsplit('/', 1)[1]
                        stream = owner._streams.get(channel)
                        if stream is None:
                            self._send(404, {'error': '未知推送通道'})
                            return
                        slots = owner._stream_slots[channel]
                        if not slots.acquire(blocking=False):
                            self._send(503, {'error': '本地实时连接数量已达上限'})
                            return
                        try:
                            self.send_response(200)
                            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                            self.send_header('Cache-Control', 'no-store')
                            self.send_header('X-Content-Type-Options', 'nosniff')
                            self.send_header('Connection', 'close')
                            self.end_headers()
                            cursor = {}
                            while not stream.closed:
                                packets = stream.read_after(cursor)
                                # Heartbeats detect abandoned sockets and keep
                                # reconnects alive; writes have a 5s timeout.
                                if not packets:
                                    self.wfile.write(b': heartbeat\n\n')
                                for sequence, topic, packet in packets:
                                    self.wfile.write(b'data: ' + packet + b'\n\n')
                                    cursor[topic] = sequence
                                self.wfile.flush()
                        except (OSError, TimeoutError):
                            pass  # Ordinary tab close / slow socket timeout.
                        finally:
                            slots.release()
                        return
                    elif path == "/api/state":
                        self._send(200, owner._state())
                    elif path == "/api/policy":
                        self._send(200, owner._policy())
                    elif path == '/api/logs/download' and owner._download is not None:
                        job_id = parse_qs(urlsplit(self.path).query).get('id', [''])[0]
                        try:
                            file = owner._download(job_id)
                        except ValueError as error:
                            self._send(404, {'error': str(error)})
                            return
                        # Stream session artifacts so a large test log/ZIP is
                        # neither copied into a Qt snapshot nor base64-encoded.
                        with file.open('rb') as source:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/zip' if file.suffix == '.zip' else 'text/plain; charset=utf-8')
                            self.send_header('Content-Disposition', f'attachment; filename="{file.name}"')
                            self.send_header('Content-Length', str(os.fstat(source.fileno()).st_size))
                            self.send_header('Cache-Control', 'no-store')
                            self.send_header('X-Content-Type-Options', 'nosniff')
                            self.end_headers()
                            while chunk := source.read(65536):
                                self.wfile.write(chunk)
                    elif path in ("/api/docs/guide", "/api/docs/api"):
                        self._send(200, {"markdown": owner._docs(path.rsplit("/", 1)[1])})
                    elif path.startswith("/api/"):
                        self._send(404, {"error": "未知接口"})
                    else:
                        parts = Path(path.lstrip("/")).parts
                        if "\\" in path or any(p.startswith(".") for p in parts):
                            self._send(404, {"error": "资源不存在"})
                            return
                        file = (owner._assets / (path.lstrip("/") or "index.html")).resolve()
                        if not file.is_relative_to(owner._assets) or not file.is_file():
                            self._send(404, {"error": "资源不存在"})
                            return
                        mime = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
                        if file.suffix in (".mjs", ".js"):
                            mime = "text/javascript"
                        self._send(200, file.read_bytes(), mime + "; charset=utf-8")
                except (TimeoutError, RuntimeError) as error:
                    self._send(503, {"error": str(error)})
                except Exception:
                    _LOG.exception("Web UI GET failed")
                    self._send(500, {"error": "后端读取失败，请查看诊断日志"})

            def do_POST(self):
                if not self._validate_caller():
                    return
                try:
                    if self.headers.get("Transfer-Encoding"):
                        raise ValueError("不支持分块请求")
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                        raise ValueError("请求必须使用 application/json")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 262144:
                        self._send(413, {"error": "请求长度必须介于 1 和 262144 字节"})
                        return
                    body = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("JSON 数字无效")))
                    if not isinstance(body, dict):
                        raise ValueError("请求内容必须为对象")
                    path = urlsplit(self.path).path
                    if path == "/api/policy":
                        fields = body.get("fields")
                        generation = body.get("generation")
                        if not isinstance(fields, dict) or type(generation) is not int:
                            raise ValueError("策略需要 fields 对象和 generation 整数")
                        with owner._commit_lock:
                            if generation != owner._policy().get("generation"):
                                self._send(409, {"error": "策略已更新，请刷新后重试", "policy": owner._policy()})
                                return
                            self._send(200, owner._commit(fields, generation))
                    elif path == "/api/command":
                        action, params = body.get("action"), body.get("params", {})
                        if not isinstance(action, str) or not 0 < len(action) <= 64 or not isinstance(params, dict):
                            raise ValueError("命令需要 action 字符串和 params 对象")
                        self._send(200, owner._command(action, params))
                    else:
                        self._send(404, {"error": "未知接口"})
                except (ValueError, UnicodeDecodeError) as error:
                    self._send(400, {"error": str(error)})
                except (TimeoutError, RuntimeError) as error:
                    self._send(503, {"error": str(error)})
                except Exception:
                    _LOG.exception("Web UI command failed")
                    self._send(500, {"error": "后端操作失败，请查看诊断日志"})

        self._server = _BoundedServer(("127.0.0.1", self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="timeline-webui", daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        for stream in self._streams.values():
            stream.close()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=2)
            self._server = None
            self._thread = None
