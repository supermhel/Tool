"""Tamper evidence: hash-chained tickets and audit log."""

from app.storage import get_store
from tests.conftest import PROCESS_SCORES

ORG = "default"


def _ticket(client, subject="t"):
    return client.post("/api/v1/evaluations", json={
        "template_id": "process", "subject": subject, "scores": PROCESS_SCORES}).json()


def test_empty_chain_verifies(client):
    r = client.get("/api/v1/tickets/verify").json()
    assert r["ok"] is True and r["count"] == 0


def test_tickets_are_linked(client):
    a, b = _ticket(client, "a"), _ticket(client, "b")
    assert a["prev_hash"] == "0" * 64
    assert b["prev_hash"] == a["hash"]
    r = client.get("/api/v1/tickets/verify").json()
    assert r["ok"] and r["count"] == 2 and r["head"] == b["hash"]


def test_edited_ticket_detected(client):
    _ticket(client, "a")
    victim = _ticket(client, "b")
    _ticket(client, "c")
    doc = get_store().get("ticket", ORG, victim["id"])
    doc["score"] = 99.9
    get_store().put("ticket", ORG, victim["id"], doc)
    r = client.get("/api/v1/tickets/verify").json()
    assert r["ok"] is False and r["broken_at"] == victim["id"]
    assert "hash" in r["reason"]


def test_removed_middle_ticket_detected(client):
    _ticket(client, "a")
    mid = _ticket(client, "b")
    _ticket(client, "c")
    get_store().delete("ticket", ORG, mid["id"])
    r = client.get("/api/v1/tickets/verify").json()
    assert r["ok"] is False and "link" in r["reason"]


def test_removed_last_ticket_detected_via_head(client):
    _ticket(client, "a")
    last = _ticket(client, "b")
    get_store().delete("ticket", ORG, last["id"])
    r = client.get("/api/v1/tickets/verify").json()
    assert r["ok"] is False and "head" in r["reason"]


def test_sealed_fields_cover_template_version_and_details(client):
    t = _ticket(client)
    doc = get_store().get("ticket", ORG, t["id"])
    doc["details"][0]["value"] = 0.0
    get_store().put("ticket", ORG, t["id"], doc)
    assert client.get("/api/v1/tickets/verify").json()["ok"] is False


# ── audit log ────────────────────────────────────────────────────────────────

def test_audit_records_actions_and_verifies(client):
    t = _ticket(client)
    client.delete(f"/api/v1/tickets/{t['id']}")
    log = client.get("/api/v1/audit").json()
    assert [e["action"] for e in log] == ["ticket.delete", "ticket.create"]
    assert log[1]["entity_id"] == t["id"]
    assert client.get("/api/v1/audit/verify").json()["ok"] is True


def test_audit_tamper_detected(client):
    _ticket(client)
    entry = get_store().list("audit", ORG)[0]
    entry["actor"] = "someone-else"
    get_store().put("audit", ORG, entry["id"], entry)
    assert client.get("/api/v1/audit/verify").json()["ok"] is False


def test_audit_export_is_oldest_first_with_verification(client):
    _ticket(client, "a")
    _ticket(client, "b")
    r = client.get("/api/v1/audit/export")
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["verification"]["ok"] is True
    assert [e["action"] for e in body["entries"]] == ["ticket.create"] * 2
    assert body["entries"][0]["created_at"] <= body["entries"][1]["created_at"]
    assert "org" not in body["entries"][0]
