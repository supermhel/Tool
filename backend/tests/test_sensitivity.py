"""Weight-sensitivity analysis: exact flip points, cross-checked by recomputation."""

import random

import pytest

from app.scoring import ScoringError
from app.sensitivity import _scores, analyze, rank_scores

CRIT = [{"id": "price", "label": "Price", "weight": 40, "max": 10},
        {"id": "quality", "label": "Quality", "weight": 60, "max": 10}]
BIDDERS = [{"name": "A", "scores": {"price": 9, "quality": 6}},
           {"name": "B", "scores": {"price": 5, "quality": 8}}]


def test_ranking_and_margin():
    r = analyze(CRIT, BIDDERS)
    assert [(x["name"], x["score"]) for x in r["ranking"]] == [("A", 72.0), ("B", 68.0)]
    assert r["winner"] == "A" and r["margin"] == 4.0


def test_exact_tie_points():
    by_id = {c["id"]: c for c in analyze(CRIT, BIDDERS)["criteria"]}
    assert by_id["price"]["tie_at_pct"] == -25.0        # price weight 40 → 30
    assert by_id["quality"]["tie_at_pct"] == pytest.approx(33.3, abs=0.05)
    assert by_id["price"]["overtaken_by"] == "B"


def test_stability_depends_on_delta():
    assert analyze(CRIT, BIDDERS, delta=0.2)["stable"] is True
    r = analyze(CRIT, BIDDERS, delta=0.3)
    assert r["stable"] is False and r["most_sensitive"]["id"] == "price"
    assert next(s for s in r["scenarios"]
                if s["criterion_id"] == "price" and s["change_pct"] == -30)["changed"] is True


def test_scenarios_cover_both_directions_per_criterion():
    r = analyze(CRIT, BIDDERS)
    assert len(r["scenarios"]) == 4
    assert {s["change_pct"] for s in r["scenarios"]} == {-20, 20}


def test_reported_tie_point_really_ties():
    """Apply the reported weight change and recompute: leader and rival must be equal."""
    rng = random.Random(7)
    for _ in range(40):
        crit = [{"id": f"c{i}", "weight": rng.uniform(0.5, 5), "max": 10} for i in range(4)]
        bidders = [{"name": n, "scores": {c["id"]: rng.randint(0, 10) for c in crit}}
                   for n in "ABC"]
        res = analyze(crit, bidders, delta=0.2)
        if res["tie_at_top"]:
            continue
        ratios = {b["name"]: {c["id"]: b["scores"][c["id"]] / 10 for c in crit} for b in bidders}
        for c in res["criteria"]:
            if c["tie_at_pct"] is None:
                continue
            w = {x["id"]: x["weight"] for x in crit}
            w[c["id"]] *= 1 + c["tie_at_pct"] / 100
            s = _scores(w, ratios)
            # tie_at_pct is rounded to 0.1%, so allow a few hundredths of a score point
            assert s[res["winner"]] == pytest.approx(s[c["overtaken_by"]], abs=0.05)


def test_no_flip_possible_reports_none():
    # A is better on every criterion: no weight change can ever let B overtake.
    b = [{"name": "A", "scores": {"price": 9, "quality": 9}},
         {"name": "B", "scores": {"price": 5, "quality": 5}}]
    r = analyze(CRIT, b)
    assert all(c["tie_at_pct"] is None for c in r["criteria"])
    assert r["stable"] is True and r["most_sensitive"] is None


def test_tie_at_top():
    b = [{"name": "A", "scores": {"price": 5, "quality": 5}},
         {"name": "B", "scores": {"price": 5, "quality": 5}}]
    r = analyze(CRIT, b)
    assert r["tie_at_top"] is True and r["winner"] is None and r["stable"] is False


def test_competition_ranking_shares_ranks():
    assert [x["rank"] for x in rank_scores({"a": 90, "b": 80, "c": 80, "d": 70})] == [1, 2, 2, 4]


def test_missing_or_out_of_range_scores_rejected():
    with pytest.raises(ScoringError):
        analyze(CRIT, [{"name": "A", "scores": {"price": 1}}, BIDDERS[1]])
    with pytest.raises(ScoringError):
        analyze(CRIT, [{"name": "A", "scores": {"price": 1, "quality": 99}}, BIDDERS[1]])


# ── endpoint ─────────────────────────────────────────────────────────────────

def _body(**kw):
    return {"criteria": CRIT, "bidders": BIDDERS} | kw


def test_endpoint(client):
    r = client.post("/api/v1/sensitivity", json=_body(delta=0.3))
    assert r.status_code == 200 and r.json()["stable"] is False


@pytest.mark.parametrize("patch", [
    {"bidders": BIDDERS[:1]},
    {"bidders": [BIDDERS[0], dict(BIDDERS[0])]},
    {"criteria": [CRIT[0], dict(CRIT[0])]},
    {"criteria": [{"id": "price", "weight": 0, "max": 10}]},
    {"delta": 0},
    {"bidders": [BIDDERS[0], {"name": "B", "scores": {"price": 1}}]},
])
def test_endpoint_validation(client, patch):
    assert client.post("/api/v1/sensitivity", json=_body(**patch)).status_code == 422
