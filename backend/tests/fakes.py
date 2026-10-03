"""Real HTTP servers standing in for external services (Upstash Redis REST, Ollama).

They listen on 127.0.0.1 on an ephemeral port, so the code under test makes genuine
httpx calls over real sockets: serialisation, headers, status handling and timeouts are
exercised for real. They are still fakes: neither is the real service.
"""

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.storage import UpstashDocStore


class FakeRedis:
    """The subset of Redis the Upstash store uses, including its compare-and-set script."""

    def __init__(self):
        self.kv, self.lists = {}, {}
        self._lock = threading.Lock()

    def run(self, cmd):
        with self._lock:
            op, *a = cmd
            if op == "SET":
                if "NX" in a and a[0] in self.kv:
                    return None
                self.kv[a[0]] = a[1]
                return "OK"
            if op == "GET":
                return self.kv.get(a[0])
            if op == "EXISTS":
                return int(a[0] in self.kv)
            if op == "DEL":
                return int(self.kv.pop(a[0], None) is not None)
            if op == "LPUSH":
                self.lists.setdefault(a[0], []).insert(0, a[1])
                return len(self.lists[a[0]])
            if op == "LLEN":
                return len(self.lists.get(a[0], []))
            if op == "LRANGE":
                lst = self.lists.get(a[0], [])
                start, stop = int(a[1]), int(a[2])
                return lst[start:] if stop == -1 else lst[start:stop + 1]
            if op == "LREM":
                self.lists[a[0]] = [x for x in self.lists.get(a[0], []) if x != a[2]]
                return 1
            if op == "EVAL":
                script, _numkeys, key, expected, new = a[0], a[1], a[2], a[3], a[4]
                assert script == UpstashDocStore.CAS_SCRIPT, "unexpected Lua script"
                cur = self.kv.get(key)
                if (cur is None and expected == "") or cur == expected:
                    self.kv[key] = new
                    return 1
                return 0
            raise AssertionError(f"unsupported command {op}")


def _json_server(handler_body):
    class Handler(BaseHTTPRequestHandler):
        # Send headers and body in one segment: separate writes trip Nagle + delayed-ACK
        # on Windows and add ~200 ms to every request.
        wbufsize = 65536
        disable_nagle_algorithm = True

        def log_message(self, *a):  # keep test output quiet
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
            status, payload = handler_body(self.path, dict(self.headers), body)
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


@contextmanager
def serve(handler_body):
    server = _json_server(handler_body)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@contextmanager
def upstash(redis: FakeRedis | None = None, token="tok"):
    redis = redis or FakeRedis()
    requests = []

    def handle(path, headers, body):
        requests.append(path)
        if headers.get("Authorization") != f"Bearer {token}":
            return 401, {"error": "Unauthorized"}
        if path.startswith("/pipeline"):
            return 200, [{"result": redis.run(c)} for c in body]
        return 200, {"result": redis.run(body)}

    with serve(handle) as url:
        yield url, redis, requests


class FakeOllama:
    """Scriptable /api/chat endpoint: set `reply`, `status` or `delay` between calls."""

    def __init__(self):
        self.reply = {"message": {"content": "hello from ollama"}}
        self.status = 200
        self.delay = 0.0
        self.requests = []

    def handle(self, path, headers, body):
        self.requests.append((path, body))
        if self.delay:
            time.sleep(self.delay)
        return self.status, self.reply


@contextmanager
def ollama(fake: FakeOllama | None = None):
    fake = fake or FakeOllama()
    with serve(fake.handle) as url:
        yield url, fake
