"""Tender workbench: blind scoring → close → consensus → award → reports."""

import pytest

TPL = {"id": "vendor", "name": "Vendor selection",
       "criteria": [{"id": "security", "label": "Security", "weight": 2, "max": 10,
                     "detail": "encryption, authentication and access control"},
                    {"id": "price", "label": "Price", "weight": 1, "max": 10}]}
WHY = "Reasoned justification for this score."


@pytest.fixture
def tender(client):
    client.post("/api/v1/templates", json=TPL)
    r = client.post("/api/v1/tenders", json={
        "name": "Cloud hosting 2026", "template_id": "vendor",
        "bidders": ["Acme", "Globex"], "evaluators": ["alice", "bob"]})
    assert r.status_code == 201, r.text
    return r.json()


def _score(client, tid, bidder, evaluator, crit, value, why=WHY):
    return client.post(f"/api/v1/tenders/{tid}/scores", json={
        "bidder_id": bidder, "evaluator": evaluator, "criterion_id": crit,
        "value": value, "justification": why})


def _fill(client, tid, diverge=True):
    """b1=Acme, b2=Globex. alice/bob disagree only on Globex security (5 vs 9)."""
    table = {("alice", "b1"): (8, 6), ("bob", "b1"): (8, 6),
             ("alice", "b2"): (5, 9), ("bob", "b2"): (9 if diverge else 5, 9)}
    for (ev, b), (sec, price) in table.items():
        assert _score(client, tid, b, ev, "security", sec).status_code == 200
        assert _score(client, tid, b, ev, "price", price).status_code == 200


# ── creation & blindness ─────────────────────────────────────────────────────

def test_create_snapshots_template_and_hides_scores(client, tender):
    assert tender["status"] == "scoring"
    assert tender["template"]["version"] == 1 and len(tender["template"]["criteria"]) == 2
    assert [b["id"] for b in tender["bidders"]] == ["b1", "b2"]
    assert "scores" not in tender and "consensus" not in tender
    assert tender["progress"]["expected_per_evaluator"] == 4


def test_template_changes_do_not_affect_existing_tender(client, tender):
    client.post("/api/v1/templates", json=TPL | {"criteria": [
        {"id": "security", "label": "Security", "weight": 9, "max": 10},
        {"id": "price", "label": "Price", "weight": 1, "max": 10}]})
    got = client.get(f"/api/v1/tenders/{tender['id']}").json()
    assert got["template"]["version"] == 1 and got["template"]["criteria"][0]["weight"] == 2


def test_scores_stay_blind_until_closed(client, tender):
    tid = tender["id"]
    _score(client, tid, "b1", "alice", "security", 7)
    view = client.get(f"/api/v1/tenders/{tid}").json()
    assert "scores" not in view
    assert view["progress"]["submitted"] == {"alice": 1, "bob": 0}
    assert client.get(f"/api/v1/tenders/{tid}/results").status_code == 409
    assert client.get(f"/api/v1/tenders/{tid}/sensitivity").status_code == 409


def test_score_validation(client, tender):
    tid = tender["id"]
    assert _score(client, tid, "b1", "mallory", "security", 5).status_code == 403
    assert _score(client, tid, "b9", "alice", "security", 5).status_code == 404
    assert _score(client, tid, "b1", "alice", "nope", 5).status_code == 404
    assert _score(client, tid, "b1", "alice", "security", 11).status_code == 422
    assert _score(client, tid, "b1", "alice", "security", -1).status_code == 422
    assert _score(client, tid, "b1", "alice", "security", 5, why="short").status_code == 422
    assert _score(client, tid, "b1", "alice", "security", True).status_code == 422


def test_resubmission_replaces_not_duplicates(client, tender):
    tid = tender["id"]
    _score(client, tid, "b1", "alice", "security", 3)
    r = _score(client, tid, "b1", "alice", "security", 7)
    assert r.json()["submitted"]["alice"] == 1


def test_cannot_close_with_missing_scores(client, tender):
    tid = tender["id"]
    _score(client, tid, "b1", "alice", "security", 5)
    r = client.post(f"/api/v1/tenders/{tid}/close-scoring")
    assert r.status_code == 409 and "incomplete" in r.json()["detail"].lower()


def test_validation_of_tender_input(client):
    client.post("/api/v1/templates", json=TPL)
    base = {"name": "T", "template_id": "vendor", "bidders": ["a", "b"], "evaluators": ["e"]}
    assert client.post("/api/v1/tenders", json=base | {"bidders": ["a"]}).status_code == 422
    assert client.post("/api/v1/tenders", json=base | {"bidders": ["a", "A"]}).status_code == 422
    assert client.post("/api/v1/tenders", json=base | {"evaluators": []}).status_code == 422
    assert client.post("/api/v1/tenders", json=base | {"evaluators": ["e", "E"]}).status_code == 422
    assert client.post("/api/v1/tenders", json=base | {"template_id": "nope"}).status_code == 404
    assert client.post("/api/v1/tenders", json=base | {"divergence_threshold": 0}).status_code == 422
    assert client.get("/api/v1/tenders/zzz").status_code == 404


# ── consensus & award ────────────────────────────────────────────────────────

def test_close_reveals_scores_and_flags_divergence(client, tender):
    tid = tender["id"]
    _fill(client, tid)
    res = client.post(f"/api/v1/tenders/{tid}/close-scoring").json()
    assert res["status"] == "consensus"
    assert res["pending_consensus"] == [{"bidder_id": "b2", "criterion_id": "security"}]
    globex = next(b for b in res["bidders"] if b["name"] == "Globex")
    sec = next(c for c in globex["criteria"] if c["criterion_id"] == "security")
    assert sec["mean"] == 7.0 and sec["spread"] == 0.4 and sec["flagged"] is True
    acme_sec = next(c for c in res["bidders"][0]["criteria"] if c["criterion_id"] == "security")
    assert acme_sec["flagged"] is False
    view = client.get(f"/api/v1/tenders/{tid}").json()
    assert view["scores"]["b2"]["security"]["alice"]["value"] == 5


def test_scoring_is_locked_after_close(client, tender):
    tid = tender["id"]
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    assert _score(client, tid, "b1", "alice", "security", 1).status_code == 409
    assert client.post(f"/api/v1/tenders/{tid}/close-scoring").status_code == 409


def test_award_blocked_until_flagged_criteria_have_consensus(client, tender):
    tid = tender["id"]
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    r = client.post(f"/api/v1/tenders/{tid}/award")
    assert r.status_code == 409 and "consensus" in r.json()["detail"]


def test_consensus_rules(client, tender):
    tid = tender["id"]
    body = {"bidder_id": "b2", "criterion_id": "security", "value": 7, "justification": WHY}
    assert client.put(f"/api/v1/tenders/{tid}/consensus", json=body).status_code == 409  # still scoring
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    assert client.put(f"/api/v1/tenders/{tid}/consensus", json=body | {"value": 11}).status_code == 422
    assert client.put(f"/api/v1/tenders/{tid}/consensus",
                      json=body | {"justification": "x"}).status_code == 422
    assert client.put(f"/api/v1/tenders/{tid}/consensus", json=body | {"bidder_id": "b9"}).status_code == 404
    r = client.put(f"/api/v1/tenders/{tid}/consensus", json=body)
    assert r.status_code == 200 and r.json()["pending_consensus"] == []


def _award(client, tid):
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    client.put(f"/api/v1/tenders/{tid}/consensus", json={
        "bidder_id": "b2", "criterion_id": "security", "value": 7, "justification": WHY})
    r = client.post(f"/api/v1/tenders/{tid}/award")
    assert r.status_code == 200, r.text
    return r.json()


def test_award_ranks_and_seals_one_ticket_per_bidder(client, tender):
    tid = tender["id"]
    res = _award(client, tid)
    # Acme: (0.8*2+0.6)/3 = 73.3 ; Globex: security consensus 7, price mean 9 → (1.4+0.9)/3 = 76.7
    assert [(r["name"], r["rank"], r["score"]) for r in res["ranking"]] == [
        ("Globex", 1, 76.67), ("Acme", 2, 73.33)]
    tickets = client.get("/api/v1/tickets").json()
    assert len(tickets) == 2 and all(t["tender_id"] == tid for t in tickets)
    assert {t["subject"]: t["score"] for t in tickets} == {"Globex": 76.7, "Acme": 73.3}
    assert "rank 1 of 2" in next(t for t in tickets if t["subject"] == "Globex")["notes"]
    assert client.get("/api/v1/tickets/verify").json()["ok"] is True
    assert client.get(f"/api/v1/tenders/{tid}").json()["status"] == "awarded"
    assert set(res["ticket_ids"]) == {"b1", "b2"}


def test_awarded_tender_is_read_only(client, tender):
    tid = tender["id"]
    _award(client, tid)
    assert client.post(f"/api/v1/tenders/{tid}/award").status_code == 409
    assert _score(client, tid, "b1", "alice", "security", 1).status_code == 409
    assert client.put(f"/api/v1/tenders/{tid}/consensus", json={
        "bidder_id": "b1", "criterion_id": "price", "value": 1, "justification": WHY}).status_code == 409


def test_unflagged_tender_awards_on_means_without_consensus(client, tender):
    tid = tender["id"]
    _fill(client, tid, diverge=False)
    assert client.post(f"/api/v1/tenders/{tid}/close-scoring").json()["pending_consensus"] == []
    assert client.post(f"/api/v1/tenders/{tid}/award").status_code == 200


def test_custom_divergence_threshold(client):
    client.post("/api/v1/templates", json=TPL)
    tid = client.post("/api/v1/tenders", json={
        "name": "Strict", "template_id": "vendor", "bidders": ["a", "b"],
        "evaluators": ["alice", "bob"], "divergence_threshold": 0.05}).json()["id"]
    _fill(client, tid)  # Globex security 5/9 flagged, but also nothing else differs
    res = client.post(f"/api/v1/tenders/{tid}/close-scoring").json()
    assert len(res["pending_consensus"]) == 1


def test_sensitivity_on_awarded_tender(client, tender):
    tid = tender["id"]
    _award(client, tid)
    s = client.get(f"/api/v1/tenders/{tid}/sensitivity?delta=0.5").json()
    assert s["winner"] == "Globex"
    assert {c["id"] for c in s["criteria"]} == {"security", "price"}


# ── reports ──────────────────────────────────────────────────────────────────

def test_reports_require_award(client, tender):
    tid = tender["id"]
    assert client.get(f"/api/v1/tenders/{tid}/report").status_code == 409
    assert client.get(f"/api/v1/tenders/{tid}/debrief/b1").status_code == 409


def test_award_report_content_and_pdf_mode(client, tender):
    tid = tender["id"]
    _award(client, tid)
    html = client.get(f"/api/v1/tenders/{tid}/report").text
    assert "Cloud hosting 2026" in html and "Globex" in html and "Acme" in html
    assert "divergent" in html and "alice" in html and WHY in html
    assert "window.print" not in html
    assert "window.print" in client.get(f"/api/v1/tenders/{tid}/report?format=pdf").text


def test_debrief_is_per_bidder_and_confidential(client, tender):
    tid = tender["id"]
    _award(client, tid)
    html = client.get(f"/api/v1/tenders/{tid}/debrief/b1").text
    assert "ranked 2 of 2" in html and "73.3" in html and "76.7" in html  # own score + top score
    assert "Globex" not in html                                           # rival stays anonymous
    assert client.get(f"/api/v1/tenders/{tid}/debrief/b9").status_code == 404


def test_report_escapes_user_text(client):
    client.post("/api/v1/templates", json=TPL)
    tid = client.post("/api/v1/tenders", json={
        "name": "<b>bold</b>", "template_id": "vendor",
        "bidders": ["<i>x</i>", "y"], "evaluators": ["e"]}).json()["id"]
    for b in ("b1", "b2"):
        for c in ("security", "price"):
            _score(client, tid, b, "e", c, 5, why="<script>alert(1)</script> padding")
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    client.post(f"/api/v1/tenders/{tid}/award")
    html = client.get(f"/api/v1/tenders/{tid}/report").text
    assert "<script>alert(1)" not in html and "<b>bold</b>" not in html and "<i>x</i>" not in html


# ── proposals & audit ────────────────────────────────────────────────────────

DOC = ("Our platform encrypts all data at rest and in transit. Authentication uses SSO with MFA. "
       "We offer free lunches to staff.")


def test_propose_returns_advice_and_saves_nothing(client, tender):
    tid = tender["id"]
    r = client.post(f"/api/v1/tenders/{tid}/propose", json={"bidder_id": "b1", "document_text": DOC})
    assert r.status_code == 200
    props = {p["criterion_id"]: p for p in r.json()["proposals"]}
    assert set(props) == {"security", "price"}
    assert props["security"]["evidence_quote"] in DOC and props["security"]["confidence"] > 0
    assert props["security"]["proposed_score"] is None and props["security"]["provider"] == "rules"
    assert client.get(f"/api/v1/tenders/{tid}").json()["progress"]["submitted"] == {"alice": 0, "bob": 0}


def test_propose_rules(client, tender):
    tid = tender["id"]
    assert client.post(f"/api/v1/tenders/{tid}/propose",
                       json={"bidder_id": "b9", "document_text": DOC}).status_code == 404
    assert client.post(f"/api/v1/tenders/{tid}/propose",
                       json={"bidder_id": "b1", "document_text": ""}).status_code == 422
    assert client.post(f"/api/v1/tenders/{tid}/propose",
                       json={"bidder_id": "b1", "document_text": "x" * 50_001}).status_code == 422
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    assert client.post(f"/api/v1/tenders/{tid}/propose",
                       json={"bidder_id": "b1", "document_text": DOC}).status_code == 409


def test_audit_trail_of_a_tender_never_leaks_blind_scores(client, tender):
    tid = tender["id"]
    _score(client, tid, "b1", "alice", "security", 7)
    log = client.get("/api/v1/audit").json()
    entry = next(e for e in log if e["action"] == "tender.score")
    assert entry["detail"] == {"evaluator": "alice", "bidder_id": "b1", "criterion_id": "security"}
    assert "value" not in str(entry)
    _fill(client, tid)
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    actions = [e["action"] for e in client.get("/api/v1/audit?limit=500").json()]
    assert {"tender.create", "tender.score", "tender.close_scoring"} <= set(actions)
    assert client.get("/api/v1/audit/verify").json()["ok"] is True


def test_list_tenders(client, tender):
    rows = client.get("/api/v1/tenders").json()
    assert rows == [{"id": tender["id"], "name": "Cloud hosting 2026", "status": "scoring",
                     "bidders": 2, "evaluators": 2, "created_at": tender["created_at"]}]
