"""Ticket storage.

Two implementations sharing the same interface:

- JsonStore    — local JSON file (dev / Docker). Active by default.
- UpstashStore — Upstash Redis REST API (Vercel KV and any cloud deployment).
  Auto-selected when KV_REST_API_URL and KV_REST_API_TOKEN are set
  (Vercel injects these automatically when the KV integration is enabled).

Redis layout:
  tickets_index  — list of IDs (LPUSH → newest-first order)
  ticket:{id}    — JSON-serialised ticket
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone

import httpx

_DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
_DATA_FILE = os.path.join(_DATA_DIR, "tickets.json")
_lock = threading.Lock()


class JsonStore:
    def __init__(self, path: str = _DATA_FILE):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write([])

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def create(self, ticket: dict) -> dict:
        with _lock:
            data = self._read()
            ticket = dict(ticket)
            ticket["id"] = uuid.uuid4().hex[:12]
            ticket["created_at"] = datetime.now(timezone.utc).isoformat()
            data.insert(0, ticket)
            self._write(data)
            return ticket

    def list(self) -> list:
        with _lock:
            return self._read()

    def get(self, ticket_id: str):
        with _lock:
            for t in self._read():
                if t["id"] == ticket_id:
                    return t
            return None

    def delete(self, ticket_id: str) -> bool:
        with _lock:
            data = self._read()
            new = [t for t in data if t["id"] != ticket_id]
            if len(new) == len(data):
                return False
            self._write(new)
            return True


class UpstashStore:
    """Persistence via Upstash Redis REST API (Vercel KV-compatible).

    Set KV_REST_API_URL and KV_REST_API_TOKEN to activate.
    """

    def __init__(self):
        self._url = os.environ["KV_REST_API_URL"].rstrip("/")
        self._token = os.environ["KV_REST_API_TOKEN"]

    def _pipeline(self, *commands: list) -> list[dict]:
        r = httpx.post(
            f"{self._url}/pipeline",
            headers={"Authorization": f"Bearer {self._token}"},
            json=list(commands),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    def _cmd(self, *args) -> object:
        r = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._token}"},
            json=list(args),
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()["result"]

    def create(self, ticket: dict) -> dict:
        ticket = dict(ticket)
        ticket["id"] = uuid.uuid4().hex[:12]
        ticket["created_at"] = datetime.now(timezone.utc).isoformat()
        self._pipeline(
            ["SET", f"ticket:{ticket['id']}", json.dumps(ticket, ensure_ascii=False)],
            ["LPUSH", "tickets_index", ticket["id"]],
        )
        return ticket

    def list(self) -> list:
        ids = self._cmd("LRANGE", "tickets_index", "0", "-1") or []
        if not ids:
            return []
        results = self._pipeline(*[["GET", f"ticket:{tid}"] for tid in ids])
        out = []
        for item in results:
            raw = item.get("result")
            if raw:
                out.append(json.loads(raw))
        return out

    def get(self, ticket_id: str):
        raw = self._cmd("GET", f"ticket:{ticket_id}")
        return json.loads(raw) if raw else None

    def delete(self, ticket_id: str) -> bool:
        if not self._cmd("EXISTS", f"ticket:{ticket_id}"):
            return False
        self._pipeline(
            ["DEL", f"ticket:{ticket_id}"],
            ["LREM", "tickets_index", "0", ticket_id],
        )
        return True


def _make_store() -> JsonStore | UpstashStore:
    if os.getenv("KV_REST_API_URL") and os.getenv("KV_REST_API_TOKEN"):
        return UpstashStore()
    return JsonStore()


store = _make_store()
