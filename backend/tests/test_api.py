"""Integration tests for the core endpoints: templates, evaluations, tickets, export."""

from tests.conftest import PROCESS_SCORES


def _ticket(client, **kw):
    payload = {"template_id": "process", "subject": "Test", "scores": PROCESS_SCORES} | kw
    r = client.post("/api/v1/evaluations", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ── health ───────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["auth"] is False


# ── templates ────────────────────────────────────────────────────────────────

def test_list_templates_returns_builtins(client):
    data = client.get("/api/v1/templates").json()
    assert [t["id"] for t in data] == ["process", "system", "sentiment"]
    assert all(t["version"] == 1 and t["builtin"] for t in data)


def test_template_has_criteria_and_scope(client):
    tpl = next(t for t in client.get("/api/v1/templates").json() if t["id"] == "process")
    assert len(tpl["criteria"]) == 5
    assert set(tpl["scope"]) == {"covered", "excluded"}
    assert all({"label", "ref"} <= set(x) for x in tpl["scope"]["excluded"])


def test_get_single_template_and_404(client):
    assert client.get("/api/v1/templates/system").json()["id"] == "system"
    assert client.get("/api/v1/templates/nope").status_code == 404


# ── evaluations ──────────────────────────────────────────────────────────────

def test_create_evaluation_returns_sealed_ticket(client):
    t = _ticket(client, subject="Onboarding")
    assert t["grade"] in "ABCDE" and 0 <= t["score"] <= 100
    assert t["subject"] == "Onboarding" and len(t["details"]) == 5
    assert t["template_version"] == 1
    assert len(t["hash"]) == 64 and t["prev_hash"] == "0" * 64


def test_unknown_template_404(client):
    r = client.post("/api/v1/evaluations",
                    json={"template_id": "unknown", "subject": "x", "scores": {"a": 1}})
    assert r.status_code == 404


def test_notes_roundtrip(client):
    assert _ticket(client, notes="some comment")["notes"] == "some comment"


def test_empty_scores_is_422_not_a_silent_zero(client):
    r = client.post("/api/v1/evaluations",
                    json={"template_id": "process", "subject": "x", "scores": {}})
    assert r.status_code == 422
    assert "Missing" in r.json()["detail"]


def test_out_of_range_and_unknown_criteria_422(client):
    base = {"template_id": "process", "subject": "x"}
    assert client.post("/api/v1/evaluations",
                       json=base | {"scores": PROCESS_SCORES | {"steps": 99}}).status_code == 422
    assert client.post("/api/v1/evaluations",
                       json=base | {"scores": PROCESS_SCORES | {"bogus": 1}}).status_code == 422


def test_non_number_score_422(client):
    r = client.post("/api/v1/evaluations", json={
        "template_id": "process", "subject": "x", "scores": PROCESS_SCORES | {"steps": True}})
    assert r.status_code == 422


def test_nan_score_rejected(client):
    body = ('{"template_id":"process","subject":"x","scores":'
            '{"steps":NaN,"bottlenecks":1,"compliance":1,"automation":1,"repeatability":1}}')
    r = client.post("/api/v1/evaluations", content=body,
                    headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_length_limits(client):
    base = {"template_id": "process", "scores": PROCESS_SCORES}
    assert client.post("/api/v1/evaluations", json=base | {"subject": "A" * 201}).status_code == 422
    assert client.post("/api/v1/evaluations", json=base | {"subject": "   "}).status_code == 422
    assert client.post("/api/v1/evaluations",
                       json=base | {"subject": "x", "notes": "n" * 2001}).status_code == 422


# ── tickets ──────────────────────────────────────────────────────────────────

def test_list_get_and_missing(client):
    assert client.get("/api/v1/tickets").json() == []
    t = _ticket(client, subject="A")
    assert [x["id"] for x in client.get("/api/v1/tickets").json()] == [t["id"]]
    assert client.get(f"/api/v1/tickets/{t['id']}").json()["id"] == t["id"]
    assert client.get("/api/v1/tickets/doesnotexist").status_code == 404


def test_list_pagination(client):
    ids = [_ticket(client, subject=f"s{i}")["id"] for i in range(4)]
    page = client.get("/api/v1/tickets?limit=2&offset=1").json()
    assert [t["id"] for t in page] == [ids[2], ids[1]]
    assert client.get("/api/v1/tickets?limit=0").status_code == 422


def test_delete_is_soft_and_keeps_chain_valid(client):
    a, b = _ticket(client, subject="a"), _ticket(client, subject="b")
    assert client.delete(f"/api/v1/tickets/{a['id']}").status_code == 200
    assert client.get(f"/api/v1/tickets/{a['id']}").status_code == 404
    assert [t["id"] for t in client.get("/api/v1/tickets").json()] == [b["id"]]
    assert client.delete(f"/api/v1/tickets/{a['id']}").status_code == 404
    assert client.get("/api/v1/tickets/verify").json()["ok"] is True


def test_pagination_skips_deleted(client):
    ids = [_ticket(client, subject=f"s{i}")["id"] for i in range(3)]
    client.delete(f"/api/v1/tickets/{ids[2]}")
    assert [t["id"] for t in client.get("/api/v1/tickets?limit=1").json()] == [ids[1]]


# ── export ───────────────────────────────────────────────────────────────────

def test_export_json(client):
    t = _ticket(client, subject="ExportJSON")
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=json")
    assert r.status_code == 200 and r.json()["subject"] == "ExportJSON"
    assert "org" not in r.json() and "deleted" not in r.json()


def test_export_html_escapes_markup(client):
    t = _ticket(client, subject="<script>alert(1)</script>", notes="<img src=x>")
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=html")
    assert "text/html" in r.headers["content-type"]
    assert "<script>alert(1)</script>" not in r.text and "&lt;script&gt;" in r.text
    assert "<img src=x>" not in r.text
    assert t["hash"] in r.text


def test_export_pdf_is_printable_html(client):
    t = _ticket(client, subject="PDFtest")
    r = client.get(f"/api/v1/tickets/{t['id']}/export?format=pdf")
    assert "window.print" in r.text and "PDFtest" in r.text


def test_export_invalid_format_and_missing(client):
    t = _ticket(client)
    assert client.get(f"/api/v1/tickets/{t['id']}/export?format=docx").status_code == 422
    assert client.get("/api/v1/tickets/nope/export").status_code == 404
