"""Domain repositories on top of the document store.

- ChainedLog   : append-only, hash-chained records (tickets, audit log).
- templates    : built-in templates + versioned, org-scoped custom templates.
- tenders      : tender workbench documents.

Tamper evidence: every chained record stores `prev_hash` and `hash`
(sha256 over prev_hash + canonical JSON of the record). Editing a stored
record, deleting one, or re-ordering them makes `verify()` fail. This detects
tampering; it does not prevent someone with database access from rewriting
the whole chain, so anchor the head hash externally if you need that.
"""

from __future__ import annotations  # methods named `list` shadow the builtin inside classes

import copy
import hashlib
import json
import random
import threading
import time
import uuid
from datetime import datetime, timezone

from .storage import get_store
from .templates_data import BUILTIN_IDS, TEMPLATES

GENESIS = "0" * 64
_lock = threading.RLock()
_PAGE = 200
_APPEND_RETRIES = 8
_UPDATE_RETRIES = 25


def _backoff(attempt: int) -> None:
    """Jittered pause so contending writers (other processes) stop colliding in lockstep."""
    time.sleep(random.uniform(0, 0.01 * (attempt + 1)))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, payload: dict) -> str:
    return hashlib.sha256((prev_hash + canonical(payload)).encode("utf-8")).hexdigest()


# `deleted` is mutable metadata (soft delete); everything else is sealed.
_UNSEALED = ("hash", "deleted", "deleted_at")


def _sealed(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in _UNSEALED}


class ChainedLog:
    def __init__(self, kind: str):
        self.kind = kind
        self._head_kind = f"{kind}_head"
        self._lock = threading.RLock()  # per chain: verifying the audit log must not stall ticket writes

    def head(self, org: str) -> str:
        doc = get_store().get(self._head_kind, org, "head")
        return doc["hash"] if doc else GENESIS

    def append(self, org: str, entry: dict, id: str | None = None) -> dict:
        """Seal and store `entry` at the head of the chain.

        The head pointer is advanced with compare-and-set. If another writer got there first
        (possible across processes or serverless instances), our entry is withdrawn and the
        append is retried on top of the new head, so the chain never forks.

        With an explicit `id` the call is idempotent: if that entry already exists it is returned
        unchanged. Callers use this to resume an interrupted multi-step operation safely.
        """
        store = get_store()
        if id is not None:
            existing = store.get(self.kind, org, id)
            if existing is not None:
                return existing
        for attempt in range(_APPEND_RETRIES):
            with self._lock:
                prev_doc = store.get(self._head_kind, org, "head")
                prev = prev_doc["hash"] if prev_doc else GENESIS
                sealed = dict(entry, id=id or new_id(), org=org, created_at=now_iso(), prev_hash=prev)
                sealed["hash"] = compute_hash(prev, _sealed(sealed))
                store.put(self.kind, org, sealed["id"], sealed)
                try:
                    won = store.compare_and_set(self._head_kind, org, "head", prev_doc,
                                                {"hash": sealed["hash"]})
                except BaseException:
                    # The write may have been applied before the error surfaced (a timeout after
                    # the server ran it). If the head already points at us, we did commit.
                    try:
                        head = store.get(self._head_kind, org, "head")
                    except Exception:  # noqa: BLE001
                        head = None
                    if head and head.get("hash") == sealed["hash"]:
                        return sealed
                    store.delete(self.kind, org, sealed["id"])  # not committed: leave no orphan
                    raise
                if won:
                    return sealed
                store.delete(self.kind, org, sealed["id"])
            _backoff(attempt)
        raise RuntimeError(f"Could not append to the {self.kind} chain: too much write contention.")

    def get(self, org: str, id: str, include_deleted: bool = False) -> dict | None:
        e = get_store().get(self.kind, org, id)
        if e is None or (e.get("deleted") and not include_deleted):
            return None
        return e

    def list(self, org: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """Newest first, soft-deleted entries skipped."""
        out, skipped, page = [], 0, 0
        while len(out) < limit:
            batch = get_store().list(self.kind, org, limit=_PAGE, offset=page * _PAGE)
            if not batch:
                break
            for e in batch:
                if e.get("deleted"):
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                out.append(e)
                if len(out) >= limit:
                    break
            page += 1
        return out

    def soft_delete(self, org: str, id: str) -> bool:
        with self._lock:
            e = get_store().get(self.kind, org, id)
            if e is None or e.get("deleted"):
                return False
            e["deleted"] = True
            e["deleted_at"] = now_iso()
            get_store().put(self.kind, org, id, e)
            return True

    def verify(self, org: str) -> dict:
        """Walk the chain oldest-first and recompute every hash."""
        with self._lock:  # keeps this chain's in-process appends out of the walk
            return self._verify(org)

    def _verify(self, org: str) -> dict:
        expected_prev, count, page = GENESIS, 0, 0
        store = get_store()
        while True:
            batch = store.list(self.kind, org, limit=_PAGE, offset=page * _PAGE, oldest_first=True)
            if not batch:
                break
            for e in batch:
                if e.get("prev_hash") != expected_prev:
                    return self._bad(count, e, "chain link broken (entry missing, reordered or forked)")
                if compute_hash(e["prev_hash"], _sealed(e)) != e.get("hash"):
                    return self._bad(count, e, "entry content does not match its hash")
                expected_prev = e["hash"]
                count += 1
            page += 1
        head = self.head(org)
        if head != expected_prev:
            return {"ok": False, "count": count, "broken_at": None,
                    "reason": "head hash does not match the last entry (entries removed?)",
                    "head": head}
        return {"ok": True, "count": count, "broken_at": None, "reason": None, "head": head}

    @staticmethod
    def _bad(count: int, e: dict, reason: str) -> dict:
        return {"ok": False, "count": count, "broken_at": e.get("id"), "reason": reason,
                "head": None}


tickets = ChainedLog("ticket")
audit_log = ChainedLog("audit")


def record(caller, action: str, entity: str, entity_id: str, detail: dict | None = None) -> dict:
    """Append an audit entry. `caller` is an auth.Caller."""
    return audit_log.append(caller.org, {
        "actor": caller.label, "action": action, "entity": entity,
        "entity_id": entity_id, "detail": detail or {},
    })


# ── templates ────────────────────────────────────────────────────────────────

class TemplateConflict(ValueError):
    pass


class Templates:
    kind = "template"

    def get(self, org: str, template_id: str, version: int | None = None) -> dict | None:
        if template_id in TEMPLATES:
            return TEMPLATES[template_id] if version in (None, 1) else None
        doc = get_store().get(self.kind, org, template_id)
        if not doc:
            return None
        v = str(version if version is not None else doc["latest"])
        return doc["versions"].get(v)

    def list(self, org: str) -> list[dict]:
        out = [TEMPLATES[i] for i in BUILTIN_IDS]
        for doc in reversed(get_store().list(self.kind, org, limit=500)):
            out.append(doc["versions"][str(doc["latest"])])
        return out

    def versions(self, org: str, template_id: str) -> list[dict]:
        if template_id in TEMPLATES:
            return [TEMPLATES[template_id]]
        doc = get_store().get(self.kind, org, template_id)
        return [doc["versions"][k] for k in sorted(doc["versions"], key=int)] if doc else []

    def save(self, org: str, data: dict) -> dict:
        """Create a custom template, or add a new version when the id exists."""
        tid = data["id"]
        if tid in TEMPLATES:
            raise TemplateConflict(f"'{tid}' is a built-in template id.")
        with _lock:
            doc = get_store().get(self.kind, org, tid) or {"id": tid, "latest": 0, "versions": {}}
            version = doc["latest"] + 1
            tpl = dict(data, version=version, builtin=False, created_at=now_iso())
            doc["latest"] = version
            doc["versions"][str(version)] = tpl
            get_store().put(self.kind, org, tid, doc)
            return tpl

    def delete(self, org: str, template_id: str) -> bool:
        if template_id in TEMPLATES:
            raise TemplateConflict("Built-in templates cannot be deleted.")
        return get_store().delete(self.kind, org, template_id)


templates = Templates()


# ── tenders ──────────────────────────────────────────────────────────────────

_tender_locks: dict[tuple[str, str], threading.RLock] = {}
_tender_locks_guard = threading.Lock()


def tender_lock(org: str, tender_id: str) -> threading.RLock:
    """Per-tender lock for multi-step operations (award) inside one process."""
    with _tender_locks_guard:
        return _tender_locks.setdefault((org, tender_id), threading.RLock())


class Tenders:
    kind = "tender"

    def update(self, org: str, id: str, mutate):
        """Optimistic read-modify-write: `mutate(doc)` edits a copy; the result is stored only if
        nobody changed the tender meanwhile, otherwise it is re-run on the fresh document.

        Returns (new_doc, mutate's return value), or None if the tender does not exist. If
        `mutate` raises, nothing is written. `mutate` must be free of side effects, since it may run again."""
        store = get_store()
        with tender_lock(org, id):  # threads in this process queue here instead of colliding in CAS
            for attempt in range(_UPDATE_RETRIES):
                current = store.get(self.kind, org, id)
                if current is None:
                    return None
                new = copy.deepcopy(current)
                result = mutate(new)
                if store.compare_and_set(self.kind, org, id, current, new):
                    return new, result
                _backoff(attempt)  # only another process can make us lose; back off with jitter
        raise RuntimeError("Could not update the tender: too much write contention.")

    def create(self, org: str, doc: dict) -> dict:
        doc = dict(doc, id=new_id(), org=org, created_at=now_iso())
        get_store().put(self.kind, org, doc["id"], doc)
        return doc

    def get(self, org: str, id: str) -> dict | None:
        return get_store().get(self.kind, org, id)

    def save(self, org: str, doc: dict) -> None:
        get_store().put(self.kind, org, doc["id"], doc)

    def list(self, org: str, limit: int = 100, offset: int = 0) -> list[dict]:
        return get_store().list(self.kind, org, limit=limit, offset=offset)


tenders = Tenders()
