"""Document store.

One tiny interface, two backends:

- SqliteDocStore  — default. File-backed, transactional, stdlib only.
- UpstashDocStore — Upstash Redis REST API (Vercel KV). Auto-selected when
  KV_REST_API_URL and KV_REST_API_TOKEN are set.

A document is addressed by (kind, org, id). `kind` is a namespace such as
"ticket", "template", "tender" or "audit"; `org` scopes it to one tenant.
Listing is newest-first by first insertion; overwriting keeps the position.

Domain logic (hash chains, tenders, ...) lives in repo.py, not here.
"""

import json
import os
import sqlite3
import threading

import httpx

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "tool.db")


class SqliteDocStore:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("DB_PATH") or _DEFAULT_DB
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._lock = threading.RLock()
        # One shared connection guarded by the lock: opening a connection per call is slow
        # and `with sqlite3.connect()` does not close it.
        self._c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; avoids an fsync per commit
        with self._c as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS docs (
                       seq  INTEGER PRIMARY KEY AUTOINCREMENT,
                       kind TEXT NOT NULL,
                       org  TEXT NOT NULL,
                       id   TEXT NOT NULL,
                       doc  TEXT NOT NULL,
                       UNIQUE (kind, org, id))"""
            )

    def close(self) -> None:
        with self._lock:
            self._c.close()

    def put(self, kind: str, org: str, id: str, doc: dict) -> None:
        with self._lock, self._c as c:
            c.execute(
                """INSERT INTO docs (kind, org, id, doc) VALUES (?, ?, ?, ?)
                   ON CONFLICT (kind, org, id) DO UPDATE SET doc = excluded.doc""",
                (kind, org, id, json.dumps(doc, ensure_ascii=False)),
            )

    def get(self, kind: str, org: str, id: str) -> dict | None:
        with self._lock, self._c as c:
            row = c.execute(
                "SELECT doc FROM docs WHERE kind=? AND org=? AND id=?", (kind, org, id)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind: str, org: str, limit: int = 100, offset: int = 0,
             oldest_first: bool = False) -> list[dict]:
        order = "ASC" if oldest_first else "DESC"
        with self._lock, self._c as c:
            rows = c.execute(
                f"SELECT doc FROM docs WHERE kind=? AND org=? ORDER BY seq {order} LIMIT ? OFFSET ?",
                (kind, org, limit, offset),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def count(self, kind: str, org: str) -> int:
        with self._lock, self._c as c:
            return c.execute(
                "SELECT COUNT(*) FROM docs WHERE kind=? AND org=?", (kind, org)
            ).fetchone()[0]

    def delete(self, kind: str, org: str, id: str) -> bool:
        with self._lock, self._c as c:
            cur = c.execute(
                "DELETE FROM docs WHERE kind=? AND org=? AND id=?", (kind, org, id)
            )
            return cur.rowcount > 0

    def compare_and_set(self, kind: str, org: str, id: str, expected: dict | None, new: dict) -> bool:
        """Atomically replace a document only if it still equals `expected` (None = absent)."""
        with self._lock:
            # BEGIN IMMEDIATE takes the write lock before the read, so the read-compare-write
            # is atomic across connections and processes, not just across threads here.
            self._c.execute("BEGIN IMMEDIATE")
            try:
                row = self._c.execute(
                    "SELECT doc FROM docs WHERE kind=? AND org=? AND id=?", (kind, org, id)
                ).fetchone()
                current = json.loads(row[0]) if row else None
                if current != expected:
                    self._c.rollback()
                    return False
                self._c.execute(
                    """INSERT INTO docs (kind, org, id, doc) VALUES (?, ?, ?, ?)
                       ON CONFLICT (kind, org, id) DO UPDATE SET doc = excluded.doc""",
                    (kind, org, id, json.dumps(new, ensure_ascii=False)),
                )
                self._c.commit()
                return True
            except BaseException:
                self._c.rollback()
                raise


class UpstashDocStore:
    """Same interface over the Upstash Redis REST API.

    Layout: key `doc:{kind}:{org}:{id}` holds the JSON; list `idx:{kind}:{org}`
    holds ids newest-first (LPUSH). Concurrent writers are last-write-wins.
    """

    def __init__(self):
        self._url = os.environ["KV_REST_API_URL"].rstrip("/")
        # One pooled client: building an SSL context per request costs more than the round trip.
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {os.environ['KV_REST_API_TOKEN']}"}, timeout=10.0)

    def close(self) -> None:
        self._client.close()

    def _post(self, path: str, body) -> object:
        r = self._client.post(f"{self._url}{path}", json=body)
        r.raise_for_status()
        return r.json()

    def _cmd(self, *args):
        return self._post("", list(args))["result"]

    def _pipeline(self, *commands: list) -> list[dict]:
        return self._post("/pipeline", list(commands))

    @staticmethod
    def _key(kind, org, id) -> str:
        return f"doc:{kind}:{org}:{id}"

    @staticmethod
    def _idx(kind, org) -> str:
        return f"idx:{kind}:{org}"

    def put(self, kind: str, org: str, id: str, doc: dict) -> None:
        raw = json.dumps(doc, ensure_ascii=False)
        created = self._cmd("SET", self._key(kind, org, id), raw, "NX")
        if created:
            self._cmd("LPUSH", self._idx(kind, org), id)
        else:
            self._cmd("SET", self._key(kind, org, id), raw)

    def get(self, kind: str, org: str, id: str) -> dict | None:
        raw = self._cmd("GET", self._key(kind, org, id))
        return json.loads(raw) if raw else None

    def list(self, kind: str, org: str, limit: int = 100, offset: int = 0,
             oldest_first: bool = False) -> list[dict]:
        idx = self._idx(kind, org)
        if oldest_first:
            total = int(self._cmd("LLEN", idx) or 0)
            start, stop = max(total - offset - limit, 0), total - offset - 1
            if stop < 0:
                return []
            ids = list(reversed(self._cmd("LRANGE", idx, str(start), str(stop)) or []))
        else:
            ids = self._cmd("LRANGE", idx, str(offset), str(offset + limit - 1)) or []
        if not ids:
            return []
        results = self._pipeline(*[["GET", self._key(kind, org, i)] for i in ids])
        return [json.loads(r["result"]) for r in results if r.get("result")]

    def count(self, kind: str, org: str) -> int:
        return int(self._cmd("LLEN", self._idx(kind, org)) or 0)

    def delete(self, kind: str, org: str, id: str) -> bool:
        if not self._cmd("EXISTS", self._key(kind, org, id)):
            return False
        self._pipeline(["DEL", self._key(kind, org, id)],
                       ["LREM", self._idx(kind, org), "0", id])
        return True

    # Server-side compare-and-set (atomic in Redis). Expected/new are compared as the exact
    # JSON text this store wrote, so both sides serialise with the same function.
    CAS_SCRIPT = (
        "local cur = redis.call('GET', KEYS[1]) "
        "if (not cur and ARGV[1] == '') or cur == ARGV[1] then "
        "redis.call('SET', KEYS[1], ARGV[2]) return 1 else return 0 end"
    )

    def compare_and_set(self, kind: str, org: str, id: str, expected: dict | None, new: dict) -> bool:
        exp = "" if expected is None else json.dumps(expected, ensure_ascii=False)
        ok = self._cmd("EVAL", self.CAS_SCRIPT, "1", self._key(kind, org, id), exp,
                       json.dumps(new, ensure_ascii=False))
        return bool(ok)


def make_store() -> SqliteDocStore | UpstashDocStore:
    if os.getenv("KV_REST_API_URL") and os.getenv("KV_REST_API_TOKEN"):
        return UpstashDocStore()
    return SqliteDocStore()


# Module-level store. Repos fetch it through `get_store()` so tests can swap it.
_store = None


def get_store():
    global _store
    if _store is None:
        _store = make_store()
    return _store


def set_store(store) -> None:
    global _store
    if _store is not None and _store is not store and hasattr(_store, "close"):
        _store.close()
    _store = store
