"""Regression tests for findings from the independent backend review.

Each test was written to FAIL on the code as reviewed and pass after the fix.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from app import repo, storage, tenders as svc
from app.main import app
from app.storage import SqliteDocStore
from tests.conftest import PROCESS_SCORES

WHY = "A sufficiently long justification."
TPL = {"id": "vendor", "name": "Vendor", "criteria": [
    {"id": "sec", "label": "Security", "weight": 2, "max": 10},
    {"id": "price", "label": "Price", "weight": 1, "max": 10}]}


def _tender(client, evaluators=("alice", "bob"), bidders=("Acme", "Globex"), tpl=TPL):
    client.post("/api/v1/templates", json=tpl)
    return client.post("/api/v1/tenders", json={
        "name": "T", "template_id": tpl["id"], "bidders": list(bidders),
        "evaluators": list(evaluators)}).json()["id"]


def _score(client, tid, bidder, ev, crit, value):
    return client.post(f"/api/v1/tenders/{tid}/scores", json={
        "bidder_id": bidder, "evaluator": ev, "criterion_id": crit, "value": value,
        "justification": WHY})


def _fill(client, tid, evaluators=("alice", "bob")):
    for ev in evaluators:
        for b in ("b1", "b2"):
            for c, v in (("sec", 7), ("price", 6)):
                assert _score(client, tid, b, ev, c, v).status_code == 200


# ── 1. tender writes must not lose updates ───────────────────────────────────

def test_concurrent_tender_writes_are_not_lost(client, monkeypatch):
    """Two writers load the same tender; the slower one must not overwrite the faster one."""
    tid = _tender(client)
    store = storage.get_store()
    real_cas, raced = store.compare_and_set, []

    def racing_cas(kind, org, id, expected, new):
        if kind == "tender" and not raced:
            raced.append(True)
            # another request (bob) commits between our read and our write
            assert _score(TestClient(app), tid, "b1", "bob", "sec", 4).status_code == 200
        return real_cas(kind, org, id, expected, new)

    monkeypatch.setattr(store, "compare_and_set", racing_cas)
    assert _score(client, tid, "b1", "alice", "sec", 9).status_code == 200
    got = client.get(f"/api/v1/tenders/{tid}").json()["progress"]["submitted"]
    assert got == {"alice": 1, "bob": 1}, got


def test_a_stale_score_cannot_reopen_a_closed_tender(client, monkeypatch):
    tid = _tender(client, evaluators=("alice",))
    for b in ("b1", "b2"):
        for c, v in (("sec", 7), ("price", 6)):
            _score(client, tid, b, "alice", c, v)
    store = storage.get_store()
    real_cas, raced = store.compare_and_set, []

    def racing_cas(kind, org, id, expected, new):
        if kind == "tender" and not raced:
            raced.append(True)
            assert TestClient(app).post(f"/api/v1/tenders/{tid}/close-scoring").status_code == 200
        return real_cas(kind, org, id, expected, new)

    monkeypatch.setattr(store, "compare_and_set", racing_cas)
    r = _score(client, tid, "b1", "alice", "sec", 1)
    assert r.status_code == 409                      # retried against the closed tender, refused
    assert client.get(f"/api/v1/tenders/{tid}").json()["status"] == "consensus"


def test_concurrent_awards_create_exactly_one_ticket_per_bidder(client):
    tid = _tender(client, evaluators=("alice",))
    _fill(client, tid, ("alice",))
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    codes = []

    def go():
        codes.append(TestClient(app).post(f"/api/v1/tenders/{tid}/award").status_code)

    threads = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [200, 409, 409, 409], codes
    assert len(client.get("/api/v1/tickets").json()) == 2
    assert client.get("/api/v1/tickets/verify").json()["ok"] is True


def test_interrupted_award_resumes_without_duplicates(client, monkeypatch):
    tid = _tender(client, evaluators=("alice",))
    _fill(client, tid, ("alice",))
    client.post(f"/api/v1/tenders/{tid}/close-scoring")
    real_append, calls = repo.tickets.append, []

    def flaky(org, entry):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("disk full")
        return real_append(org, entry)

    monkeypatch.setattr(repo.tickets, "append", flaky)
    with pytest.raises(RuntimeError):
        TestClient(app, raise_server_exceptions=True).post(f"/api/v1/tenders/{tid}/award")
    assert client.get(f"/api/v1/tenders/{tid}").json()["status"] == "awarding"
    assert len(client.get("/api/v1/tickets").json()) == 1

    monkeypatch.setattr(repo.tickets, "append", real_append)
    assert client.post(f"/api/v1/tenders/{tid}/award").status_code == 200
    assert len(client.get("/api/v1/tickets").json()) == 2          # resumed, not duplicated
    assert client.get(f"/api/v1/tenders/{tid}").json()["status"] == "awarded"
    assert client.get("/api/v1/tickets/verify").json()["ok"] is True


# ── 2. a failure inside append must not corrupt the chain ────────────────────

def test_failed_head_update_leaves_no_phantom_entry(monkeypatch):
    store = storage.get_store()
    real_cas, n = store.compare_and_set, []

    def boom(*a, **k):
        n.append(1)
        if len(n) == 1:
            raise RuntimeError("database is locked")
        return real_cas(*a, **k)

    monkeypatch.setattr(store, "compare_and_set", boom)
    with pytest.raises(RuntimeError):
        repo.tickets.append("default", {"subject": "one"})
    repo.tickets.append("default", {"subject": "two"})
    v = repo.tickets.verify("default")
    assert v["ok"] is True and v["count"] == 1, v
    assert [t["subject"] for t in store.list("ticket", "default")] == ["two"]


# ── 3. SQLite compare-and-set must be atomic across connections ──────────────

def test_sqlite_cas_is_atomic_across_connections(tmp_path):
    path = str(tmp_path / "shared.db")
    a, b = SqliteDocStore(path), SqliteDocStore(path)
    for round_ in range(150):
        key, results = f"k{round_}", {}
        barrier = threading.Barrier(2)

        def run(name, store):
            barrier.wait()
            results[name] = store.compare_and_set("h", "o", key, None, {"w": name})

        ts = [threading.Thread(target=run, args=("a", a)), threading.Thread(target=run, args=("b", b))]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert sorted(results.values()) == [False, True], (round_, results)
    a.close()
    b.close()


# ── 4. ranking on unrounded totals ───────────────────────────────────────────

def test_ranking_uses_unrounded_totals(client):
    tpl = {"id": "fine", "name": "Fine", "criteria": [{"id": "x", "label": "X", "weight": 1, "max": 1000}]}
    tid = _tender(client, evaluators=("e",), bidders=("Zeta", "Alpha"), tpl=tpl)
    _score(client, tid, "b1", "e", "x", 800.4)       # Zeta  80.04
    _score(client, tid, "b2", "e", "x", 800.1)       # Alpha 80.01 (both display as 80.0)
    res = client.post(f"/api/v1/tenders/{tid}/close-scoring").json()
    assert [(r["name"], r["rank"]) for r in res["ranking"]] == [("Zeta", 1), ("Alpha", 2)]
    s = client.get(f"/api/v1/tenders/{tid}/sensitivity").json()
    assert s["winner"] == "Zeta" and s["tie_at_top"] is False


# ── 5. huge numbers → 422, never 500 ─────────────────────────────────────────

def test_huge_integers_are_rejected_cleanly(client):
    huge = 10 ** 400
    r = client.post("/api/v1/evaluations", json={
        "template_id": "process", "subject": "x", "scores": PROCESS_SCORES | {"steps": huge}})
    assert r.status_code == 422
    r = client.post("/api/v1/sensitivity", json={
        "criteria": [{"id": "a", "weight": 1, "max": 10}],
        "bidders": [{"name": "x", "scores": {"a": huge}}, {"name": "y", "scores": {"a": 1}}]})
    assert r.status_code == 422


def test_huge_integer_weight_is_rejected_cleanly(client):
    r = client.post("/api/v1/sensitivity", content=(
        '{"criteria":[{"id":"a","weight":' + "9" * 400 + ',"max":10}],'
        '"bidders":[{"name":"x","scores":{"a":1}},{"name":"y","scores":{"a":2}}]}'),
        headers={"content-type": "application/json"})
    assert r.status_code == 422


# ── 6. odd-but-valid import files → 422, never 500 ───────────────────────────

@pytest.mark.parametrize("filename,content", [
    pytest.param("t.yaml", "1: 2\nid: x\nname: X\ncriteria:\n  - {id: a, label: A, weight: 1, max: 5}\n",
                 id="yaml-non-string-key"),
    pytest.param("t.yaml", "[" * 20000, id="yaml-deep-nesting"),
    pytest.param("t.json", "[" * 50000, id="json-deep-nesting"),
    pytest.param("t.json", '{"id":"x","name":"X","criteria":[{"id":"a","label":"A","weight":1e999,"max":5}]}',
                 id="json-infinite-weight"),
])
def test_odd_imports_are_422(client, filename, content):
    r = client.post("/api/v1/templates/import", json={"filename": filename, "content": content})
    assert r.status_code == 422, (r.status_code, r.text[:200])


# ── 7. bounded tender size ───────────────────────────────────────────────────

def test_tender_size_is_capped(client):
    client.post("/api/v1/templates", json=TPL | {"id": "big", "criteria": [
        {"id": f"c{i}", "label": f"C{i}", "weight": 1, "max": 10} for i in range(5)]})
    r = client.post("/api/v1/tenders", json={
        "name": "huge", "template_id": "big",
        "bidders": [f"b{i}" for i in range(50)], "evaluators": [f"e{i}" for i in range(20)]})
    assert r.status_code == 422 and "too large" in str(r.json()["detail"]).lower()
    ok = client.post("/api/v1/tenders", json={
        "name": "ok", "template_id": "big",
        "bidders": [f"b{i}" for i in range(10)], "evaluators": ["e1", "e2"]})
    assert ok.status_code == 201


# ── 8. sensitivity at exactly ±delta ─────────────────────────────────────────

def test_scenario_at_exact_tie_counts_as_a_change_regardless_of_names():
    from app.sensitivity import analyze
    crit = [{"id": "price", "label": "Price", "weight": 40, "max": 10},
            {"id": "quality", "label": "Quality", "weight": 60, "max": 10}]
    bidders = [{"name": "Amy", "scores": {"price": 9, "quality": 6}},     # leader, alphabetically FIRST:
               {"name": "Zed", "scores": {"price": 5, "quality": 8}}]     # an exact tie used to resolve to Amy
    r = analyze(crit, bidders, delta=0.25)                                # price tips at exactly -25%
    price = next(c for c in r["criteria"] if c["id"] == "price")
    assert price["tie_at_pct"] == -25.0 and price["flips_within_delta"] is True
    scen = next(s for s in r["scenarios"] if s["criterion_id"] == "price" and s["change_pct"] == -25)
    assert scen["changed"] is True
    assert r["stable"] is False
