"""End-to-end over real sockets: the API running on the Upstash store, and the Ollama paths.

These replace "mocked at the function level" confidence for the cloud store and the model
client with genuine HTTP round trips. The servers are fakes (see fakes.py), not the real
services, so they prove our client code, not the vendors' behaviour.
"""

import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from app import proposers, storage
from app.config import settings
from app.main import app
from tests import fakes
from tests.conftest import PROCESS_SCORES

REAL_ASYNC_CLIENT = httpx.AsyncClient  # conftest swaps it for an always-failing stub; captured at import


@pytest.fixture
def real_http(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", REAL_ASYNC_CLIENT)


@pytest.fixture
def upstash_api(monkeypatch):
    """The whole API wired to the Upstash store backed by a real local HTTP server."""
    with fakes.upstash() as (url, redis, reqs):
        monkeypatch.setenv("KV_REST_API_URL", url)
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        storage.set_store(storage.UpstashDocStore())
        yield TestClient(app), redis, reqs


def _eval(client, subject="t"):
    r = client.post("/api/v1/evaluations", json={
        "template_id": "process", "subject": subject, "scores": PROCESS_SCORES})
    assert r.status_code == 200, r.text
    return r.json()


# ── Upstash store through the whole API ──────────────────────────────────────

def test_api_on_upstash_store_end_to_end(upstash_api):
    client, redis, reqs = upstash_api
    a, b = _eval(client, "a"), _eval(client, "b")
    assert b["prev_hash"] == a["hash"]
    assert [t["subject"] for t in client.get("/api/v1/tickets").json()] == ["b", "a"]
    assert client.get("/api/v1/tickets/verify").json()["ok"] is True
    assert client.delete(f"/api/v1/tickets/{a['id']}").status_code == 200
    assert [t["subject"] for t in client.get("/api/v1/tickets").json()] == ["b"]
    assert client.get("/api/v1/audit/verify").json()["ok"] is True
    assert any(k.startswith("doc:ticket:default:") for k in redis.kv)
    assert "/pipeline" in reqs  # list() uses a pipelined fan-out


def test_tender_workflow_on_upstash_store(upstash_api):
    client, _r, _q = upstash_api
    tpl = {"id": "vendor", "name": "Vendor", "criteria": [
        {"id": "sec", "label": "Security", "weight": 2, "max": 10},
        {"id": "price", "label": "Price", "weight": 1, "max": 10}]}
    assert client.post("/api/v1/templates", json=tpl).status_code == 201
    tid = client.post("/api/v1/tenders", json={
        "name": "T", "template_id": "vendor", "bidders": ["A", "B"], "evaluators": ["e"]}).json()["id"]
    for b, (s, p) in {"b1": (8, 5), "b2": (6, 9)}.items():
        for c, v in (("sec", s), ("price", p)):
            assert client.post(f"/api/v1/tenders/{tid}/scores", json={
                "bidder_id": b, "evaluator": "e", "criterion_id": c, "value": v,
                "justification": "justified at length"}).status_code == 200
    assert client.post(f"/api/v1/tenders/{tid}/close-scoring").status_code == 200
    assert client.post(f"/api/v1/tenders/{tid}/award").status_code == 200
    assert client.get("/api/v1/tickets/verify").json()["count"] == 2


@pytest.mark.parametrize("backend", ["sqlite", "upstash"])
def test_concurrent_appends_never_fork_the_chain(backend, tmp_path, monkeypatch):
    """Many writers at once: compare-and-set plus retry must leave one linear, valid chain."""
    ctx = fakes.upstash() if backend == "upstash" else None
    if ctx:
        url, _r, _q = ctx.__enter__()
        monkeypatch.setenv("KV_REST_API_URL", url)
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        storage.set_store(storage.UpstashDocStore())
    try:
        client = TestClient(app)
        errors = []

        def worker(i):
            try:
                _eval(client, f"w{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert not errors
        v = client.get("/api/v1/tickets/verify").json()
        assert v["ok"] is True and v["count"] == 10, v
    finally:
        if ctx:
            ctx.__exit__(None, None, None)


def test_append_gives_up_with_a_clear_error_under_permanent_contention(tmp_path, monkeypatch):
    from app import repo
    store = storage.get_store()
    monkeypatch.setattr(store, "compare_and_set", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="contention"):
        repo.tickets.append("default", {"subject": "x"})
    assert store.list("ticket", "default") == []  # every withdrawn attempt cleaned up after itself


# ── Ollama over real HTTP ────────────────────────────────────────────────────

def test_chat_uses_the_model_over_http(client, real_http, monkeypatch):
    with fakes.ollama() as (url, fake):
        monkeypatch.setattr(settings, "OLLAMA_URL", url)
        _eval(client, "Subject-X")
        r = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]}).json()
    assert r["reply"] == "hello from ollama" and r["model"] == settings.OLLAMA_MODEL
    path, body = fake.requests[0]
    assert path == "/api/chat" and body["stream"] is False
    assert any("Subject-X" in m["content"] for m in body["messages"])   # ticket context was sent
    assert body["messages"][-1] == {"role": "user", "content": "hi"}


def test_chat_falls_back_when_ollama_errors(client, real_http, monkeypatch):
    fake = fakes.FakeOllama()
    fake.status = 500
    fake.reply = {"error": "model not found"}
    with fakes.ollama(fake) as (url, _):
        monkeypatch.setattr(settings, "OLLAMA_URL", url)
        r = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "list"}]}).json()
    assert r["model"] == "fallback"


def test_chat_falls_back_on_timeout(client, real_http, monkeypatch):
    fake = fakes.FakeOllama()
    fake.delay = 1.5
    with fakes.ollama(fake) as (url, _):
        monkeypatch.setattr(settings, "OLLAMA_URL", url)
        monkeypatch.setattr(settings, "OLLAMA_TIMEOUT", 0.3)
        r = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "list"}]}).json()
    assert r["model"] == "fallback"


def _tender_with(client, tid_name="T"):
    tpl = {"id": "vendor", "name": "Vendor", "criteria": [
        {"id": "sec", "label": "Security", "detail": "encryption and access control", "weight": 1, "max": 10}]}
    client.post("/api/v1/templates", json=tpl)
    return client.post("/api/v1/tenders", json={
        "name": tid_name, "template_id": "vendor", "bidders": ["A", "B"], "evaluators": ["e"]}).json()["id"]


def test_ollama_proposer_over_http_through_the_endpoint(client, real_http, monkeypatch):
    import json as j
    doc = "We encrypt all data at rest. Access control uses SSO."
    fake = fakes.FakeOllama()
    fake.reply = {"message": {"content": j.dumps({
        "proposed_score": 8, "confidence": 0.85,
        "evidence_quote": "We encrypt all data at rest.", "rationale": "Encryption stated."})}}
    with fakes.ollama(fake) as (url, _):
        monkeypatch.setattr(settings, "OLLAMA_URL", url)
        monkeypatch.setattr(settings, "PROPOSER", "ollama")
        tid = _tender_with(client)
        r = client.post(f"/api/v1/tenders/{tid}/propose", json={"bidder_id": "b1", "document_text": doc}).json()
    p = r["proposals"][0]
    assert p["proposed_score"] == 8 and p["quote_verified"] is True and p["provider"] == settings.OLLAMA_MODEL
    _, body = fake.requests[0]
    assert body["format"]["required"] and body["options"]["temperature"] == 0


def test_ollama_proposer_discards_a_fabricated_quote_over_http(client, real_http, monkeypatch):
    import json as j
    fake = fakes.FakeOllama()
    fake.reply = {"message": {"content": j.dumps({
        "proposed_score": 10, "confidence": 0.99,
        "evidence_quote": "Certified to ISO 27001 and SOC 2.", "rationale": "Certified."})}}
    with fakes.ollama(fake) as (url, _):
        monkeypatch.setattr(settings, "OLLAMA_URL", url)
        monkeypatch.setattr(settings, "PROPOSER", "ollama")
        tid = _tender_with(client)
        p = client.post(f"/api/v1/tenders/{tid}/propose", json={
            "bidder_id": "b1", "document_text": "Nothing about certifications here."}).json()["proposals"][0]
    assert p["evidence_quote"] == "" and p["quote_verified"] is False and p["confidence"] <= 0.2


def test_ollama_proposer_falls_back_when_the_model_is_down(client, real_http, monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://127.0.0.1:1")   # nothing listens here
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT", 1.0)
    monkeypatch.setattr(settings, "PROPOSER", "ollama")
    tid = _tender_with(client)
    p = client.post(f"/api/v1/tenders/{tid}/propose", json={
        "bidder_id": "b1", "document_text": "We encrypt data."}).json()["proposals"][0]
    assert p["provider"] == "rules-fallback"
    assert isinstance(proposers.get_proposer(), proposers.OllamaProposer)


@pytest.mark.parametrize("backend", ["sqlite", "upstash"])
def test_stale_head_is_detected_and_the_append_retried(backend, monkeypatch):
    """A writer in another process advances the head between our read and our CAS.

    The in-process lock cannot see that writer, so only compare-and-set stands between us and a
    forked chain. We simulate it by appending from inside the first CAS call."""
    from app import repo
    ctx = fakes.upstash() if backend == "upstash" else None
    if ctx:
        url, _r, _q = ctx.__enter__()
        monkeypatch.setenv("KV_REST_API_URL", url)
        monkeypatch.setenv("KV_REST_API_TOKEN", "tok")
        storage.set_store(storage.UpstashDocStore())
    try:
        store = storage.get_store()
        real_cas, raced = store.compare_and_set, []

        def racing_cas(*args, **kw):
            if not raced:
                raced.append(True)
                repo.tickets.append("default", {"subject": "competitor"})   # advances the head
            return real_cas(*args, **kw)

        monkeypatch.setattr(store, "compare_and_set", racing_cas)
        mine = repo.tickets.append("default", {"subject": "mine"})
        v = repo.tickets.verify("default")
        assert v["ok"] is True and v["count"] == 2, v
        subjects = [t["subject"] for t in store.list("ticket", "default", oldest_first=True)]
        assert subjects == ["competitor", "mine"] and mine["prev_hash"] != "0" * 64
    finally:
        if ctx:
            ctx.__exit__(None, None, None)
