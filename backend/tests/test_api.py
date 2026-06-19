"""Integration tests for the FastAPI endpoints.

The `isolated_store` fixture (conftest.py) replaces the module-level store
with a fresh JsonStore in a temp directory for every test, so tests are fully
independent.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

PROCESS_SCORES = {
    "steps": 8, "bottlenecks": 6, "compliance": 9,
    "automation": 5, "repeatability": 7,
}


# ── health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── templates ─────────────────────────────────────────────────────────────────

def test_list_templates_returns_three():
    r = client.get("/api/v1/templates")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert {t["id"] for t in data} == {"process", "system", "sentiment"}


def test_template_has_criteria_and_scope():
    r = client.get("/api/v1/templates")
    tpl = next(t for t in r.json() if t["id"] == "process")
    assert len(tpl["criteria"]) == 5
    assert "covered" in tpl["scope"]
    assert "excluded" in tpl["scope"]


def test_excluded_items_are_dicts():
    r = client.get("/api/v1/templates")
    tpl = next(t for t in r.json() if t["id"] == "process")
    for item in tpl["scope"]["excluded"]:
        assert "label" in item
        assert "ref" in item


# ── evaluations ───────────────────────────────────────────────────────────────

def test_create_evaluation_returns_ticket():
    r = client.post("/api/v1/evaluations", json={
        "template_id": "process",
        "subject": "Onboarding",
        "scores": PROCESS_SCORES,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["grade"] in ("A", "B", "C", "D", "E")
    assert 0.0 <= data["score"] <= 100.0
    assert data["subject"] == "Onboarding"
    assert len(data["details"]) == 5


def test_create_evaluation_unknown_template():
    r = client.post("/api/v1/evaluations", json={
        "template_id": "unknown",
        "subject": "x",
        "scores": {},
    })
    assert r.status_code == 404


def test_create_evaluation_with_notes():
    r = client.post("/api/v1/evaluations", json={
        "template_id": "process",
        "subject": "x",
        "scores": PROCESS_SCORES,
        "notes": "some comment",
    })
    assert r.status_code == 200
    assert r.json()["notes"] == "some comment"


# ── tickets ───────────────────────────────────────────────────────────────────

def _create_ticket(**kwargs):
    payload = {"template_id": "process", "subject": "Test", "scores": PROCESS_SCORES}
    payload.update(kwargs)
    return client.post("/api/v1/evaluations", json=payload).json()


def test_list_tickets_empty():
    r = client.get("/api/v1/tickets")
    assert r.status_code == 200
    assert r.json() == []


def test_list_tickets_after_create():
    t = _create_ticket(subject="A")
    r = client.get("/api/v1/tickets")
    assert any(x["id"] == t["id"] for x in r.json())


def test_get_ticket():
    t = _create_ticket()
    r = client.get(f"/api/v1/tickets/{t['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == t["id"]


def test_get_missing_ticket():
    r = client.get("/api/v1/tickets/doesnotexist")
    assert r.status_code == 404


def test_delete_ticket():
    t = _create_ticket()
    r = client.delete(f"/api/v1/tickets/{t['id']}")
    assert r.status_code == 200
    assert client.get(f"/api/v1/tickets/{t['id']}").status_code == 404


def test_delete_missing_ticket():
    r = client.delete("/api/v1/tickets/doesnotexist")
    assert r.status_code == 404


# ── export ────────────────────────────────────────────────────────────────────

def test_export_json():
    t = _create_ticket(subject="ExportJSON")
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=json")
    assert r.status_code == 200
    assert r.json()["subject"] == "ExportJSON"


def test_export_html():
    t = _create_ticket()
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert t["subject"] in r.text


def test_export_pdf_returns_printable_html():
    t = _create_ticket(subject="PDFtest")
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=pdf")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "window.print" in r.text
    assert "PDFtest" in r.text


def test_export_invalid_format():
    t = _create_ticket()
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=docx")
    assert r.status_code == 422
