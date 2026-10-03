"""API-key auth and organisation isolation."""

import pytest

from app.config import settings
from tests.conftest import PROCESS_SCORES

KEYS = "ka:orgA:alice,kb:orgB"
A, B = {"X-API-Key": "ka"}, {"X-API-Key": "kb"}


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", KEYS)


def _ticket(client, headers, subject="t"):
    r = client.post("/api/v1/evaluations", headers=headers, json={
        "template_id": "process", "subject": subject, "scores": PROCESS_SCORES})
    assert r.status_code == 200, r.text
    return r.json()


def test_missing_and_wrong_key_rejected(client, keyed):
    assert client.get("/api/v1/tickets").status_code == 401
    assert client.get("/api/v1/tickets", headers={"X-API-Key": "nope"}).status_code == 401
    assert client.get("/api/v1/tickets", headers=A).status_code == 200


def test_legacy_single_api_key_still_works(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "legacy")
    assert client.get("/api/v1/tickets").status_code == 401
    assert client.get("/api/v1/tickets", headers={"X-API-Key": "legacy"}).status_code == 200


def test_health_and_sensitivity_stay_open(client, keyed):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["auth"] is True
    body = {"criteria": [{"id": "a", "weight": 1}],
            "bidders": [{"name": "x", "scores": {"a": 1}}, {"name": "y", "scores": {"a": 2}}]}
    assert client.post("/api/v1/sensitivity", json=body).status_code == 200


def test_tickets_isolated_between_orgs(client, keyed):
    t = _ticket(client, A, "secret-a")
    assert client.get("/api/v1/tickets", headers=B).json() == []
    assert client.get(f"/api/v1/tickets/{t['id']}", headers=B).status_code == 404
    assert client.get(f"/api/v1/tickets/{t['id']}/export", headers=B).status_code == 404
    assert client.delete(f"/api/v1/tickets/{t['id']}", headers=B).status_code == 404
    assert client.get(f"/api/v1/tickets/{t['id']}", headers=A).status_code == 200


def test_chains_are_per_org(client, keyed):
    _ticket(client, A)
    _ticket(client, A)
    _ticket(client, B)
    assert client.get("/api/v1/tickets/verify", headers=A).json()["count"] == 2
    assert client.get("/api/v1/tickets/verify", headers=B).json()["count"] == 1


def test_templates_and_tenders_isolated(client, keyed):
    tpl = {"id": "mine", "name": "Mine", "criteria": [{"id": "c", "label": "C", "weight": 1, "max": 5}]}
    assert client.post("/api/v1/templates", headers=A, json=tpl).status_code == 201
    assert "mine" not in [t["id"] for t in client.get("/api/v1/templates", headers=B).json()]
    assert client.get("/api/v1/templates/mine", headers=B).status_code == 404
    r = client.post("/api/v1/tenders", headers=A, json={
        "name": "T", "template_id": "mine", "bidders": ["x", "y"], "evaluators": ["e"]})
    tid = r.json()["id"]
    assert client.get(f"/api/v1/tenders/{tid}", headers=B).status_code == 404
    assert client.get("/api/v1/tenders", headers=B).json() == []


def test_audit_actor_is_key_label_and_isolated(client, keyed):
    _ticket(client, A)
    _ticket(client, B)
    assert [e["actor"] for e in client.get("/api/v1/audit", headers=A).json()] == ["alice"]
    assert [e["actor"] for e in client.get("/api/v1/audit", headers=B).json()] == ["orgB"]


def test_chat_context_never_crosses_orgs(client, keyed, monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT", 1.0)
    t = _ticket(client, A, "only-in-a")
    r = client.post("/api/v1/chat", headers=B,
                    json={"messages": [{"role": "user", "content": "list tickets"}]}).json()
    assert r["grounded_on"] == [] and "only-in-a" not in r["reply"]
    r = client.post("/api/v1/chat", headers=A,
                    json={"messages": [{"role": "user", "content": "list tickets"}]}).json()
    assert r["grounded_on"] == [t["id"]]


def test_cors_does_not_allow_credentials(client):
    r = client.options("/api/v1/tickets", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-credentials" not in r.headers


# ── evaluator identity: with auth on, a key's label is who it may score as ───

EV_KEYS = "k-alice:org:alice,k-bob:org:bob,k-admin:org:organiser"
ALICE, BOB, ADMIN = ({"X-API-Key": k} for k in ("k-alice", "k-bob", "k-admin"))


def _tender(client):
    tpl = {"id": "t", "name": "T", "criteria": [{"id": "c", "label": "C", "weight": 1, "max": 10}]}
    client.post("/api/v1/templates", headers=ADMIN, json=tpl)
    return client.post("/api/v1/tenders", headers=ADMIN, json={
        "name": "X", "template_id": "t", "bidders": ["a", "b"], "evaluators": ["alice", "bob"]}).json()["id"]


def _score(client, tid, headers, evaluator, bidder="b1", value=5):
    return client.post(f"/api/v1/tenders/{tid}/scores", headers=headers, json={
        "bidder_id": bidder, "evaluator": evaluator, "criterion_id": "c", "value": value,
        "justification": "a justification of sufficient length"})


def test_each_key_scores_only_as_itself(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", EV_KEYS)
    tid = _tender(client)
    assert _score(client, tid, ALICE, "alice").status_code == 200
    assert _score(client, tid, BOB, "bob").status_code == 200
    r = _score(client, tid, ALICE, "bob")
    assert r.status_code == 403 and "alice" in r.json()["detail"]
    assert _score(client, tid, BOB, "alice").status_code == 403


def test_an_organiser_key_cannot_score_for_anyone(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", EV_KEYS)
    tid = _tender(client)
    assert _score(client, tid, ADMIN, "alice").status_code == 403
    assert _score(client, tid, ADMIN, "organiser").status_code == 403      # not an evaluator of this tender


def test_blocked_attempts_do_not_change_progress(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", EV_KEYS)
    tid = _tender(client)
    _score(client, tid, ALICE, "bob")
    assert client.get(f"/api/v1/tenders/{tid}", headers=ADMIN).json()["progress"]["submitted"] == {"alice": 0, "bob": 0}


def test_open_mode_keeps_free_choice_of_evaluator(client):
    tpl = {"id": "t", "name": "T", "criteria": [{"id": "c", "label": "C", "weight": 1, "max": 10}]}
    client.post("/api/v1/templates", json=tpl)
    tid = client.post("/api/v1/tenders", json={
        "name": "X", "template_id": "t", "bidders": ["a", "b"], "evaluators": ["alice", "bob"]}).json()["id"]
    assert _score(client, tid, {}, "alice").status_code == 200
    assert _score(client, tid, {}, "bob").status_code == 200


def test_me_reports_org_and_label(client, monkeypatch):
    assert client.get("/api/v1/me").json() == {"org": "default", "label": "anonymous", "auth": False}
    monkeypatch.setattr(settings, "API_KEYS", EV_KEYS)
    assert client.get("/api/v1/me", headers=ALICE).json() == {"org": "org", "label": "alice", "auth": True}
    assert client.get("/api/v1/me").status_code == 401
