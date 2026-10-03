import pytest

from app.scoring import ScoringError, evaluate, score_to_grade, validate_scores
from app.templates_data import TEMPLATES

PROCESS = TEMPLATES["process"]
IDS = ["steps", "bottlenecks", "compliance", "automation", "repeatability"]


def test_grade_thresholds():
    assert score_to_grade(100) == ("A", "Excellent")
    assert score_to_grade(85) == ("A", "Excellent")
    assert score_to_grade(84.9) == ("B", "Good")
    assert score_to_grade(70) == ("B", "Good")
    assert score_to_grade(69.9) == ("C", "Watch")
    assert score_to_grade(55) == ("C", "Watch")
    assert score_to_grade(54.9) == ("D", "Poor")
    assert score_to_grade(40) == ("D", "Poor")
    assert score_to_grade(39.9) == ("E", "Critical")
    assert score_to_grade(0) == ("E", "Critical")


def test_evaluate_perfect_score():
    result = evaluate(PROCESS, {c: 10 for c in IDS})
    assert result["score"] == 100.0
    assert result["grade"] == "A"


def test_evaluate_zero_score():
    result = evaluate(PROCESS, {c: 0 for c in IDS})
    assert result["score"] == 0.0
    assert result["grade"] == "E"


def test_evaluate_weighted_mean():
    # steps weight 1.0 of total 5.0 → 20 when only steps is maxed
    scores = {c: 0 for c in IDS} | {"steps": 10}
    assert evaluate(PROCESS, scores)["score"] == pytest.approx(20.0, abs=0.1)


def test_evaluate_detail_fields():
    scores = {"steps": 8, "bottlenecks": 6, "compliance": 9, "automation": 5, "repeatability": 7}
    result = evaluate(PROCESS, scores)
    assert len(result["details"]) == 5
    d = next(x for x in result["details"] if x["id"] == "steps")
    assert (d["value"], d["max"]) == (8, 10)
    assert d["contribution"] == pytest.approx(80.0, abs=0.1)


def test_evaluate_all_builtin_templates():
    for tpl in TEMPLATES.values():
        s = {c["id"]: c["max"] / 2 for c in tpl["criteria"]}
        assert evaluate(tpl, s)["score"] == pytest.approx(50.0, abs=0.1)


@pytest.mark.parametrize("bad", [999, -1, 10.01])
def test_out_of_range_rejected_not_clamped(bad):
    with pytest.raises(ScoringError, match="outside"):
        evaluate(PROCESS, {c: 5 for c in IDS} | {"steps": bad})


def test_missing_criterion_rejected():
    scores = {c: 5 for c in IDS}
    del scores["automation"]
    with pytest.raises(ScoringError, match="Missing scores for: automation"):
        evaluate(PROCESS, scores)


def test_empty_scores_rejected():
    with pytest.raises(ScoringError, match="Missing"):
        evaluate(PROCESS, {})


def test_unknown_criterion_rejected():
    with pytest.raises(ScoringError, match="Unknown criteria: bogus"):
        evaluate(PROCESS, {c: 5 for c in IDS} | {"bogus": 1})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "7", True, None])
def test_non_numeric_or_non_finite_rejected(bad):
    with pytest.raises(ScoringError):
        validate_scores(PROCESS, {c: 5 for c in IDS} | {"steps": bad})
