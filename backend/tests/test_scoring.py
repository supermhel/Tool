import pytest
from app.scoring import evaluate, score_to_grade


def test_grade_thresholds():
    assert score_to_grade(100) == ("A", "Excellent")
    assert score_to_grade(85)  == ("A", "Excellent")
    assert score_to_grade(84.9) == ("B", "Bon")
    assert score_to_grade(70)  == ("B", "Bon")
    assert score_to_grade(69.9) == ("C", "À surveiller")
    assert score_to_grade(55)  == ("C", "À surveiller")
    assert score_to_grade(54.9) == ("D", "Insuffisant")
    assert score_to_grade(40)  == ("D", "Insuffisant")
    assert score_to_grade(39.9) == ("E", "Critique")
    assert score_to_grade(0)   == ("E", "Critique")


def test_evaluate_perfect_score():
    scores = {c: 10 for c in ["steps", "bottlenecks", "compliance", "automation", "repeatability"]}
    result = evaluate("process", scores)
    assert result["score"] == 100.0
    assert result["grade"] == "A"
    assert result["grade_label"] == "Excellent"


def test_evaluate_zero_score():
    scores = {c: 0 for c in ["steps", "bottlenecks", "compliance", "automation", "repeatability"]}
    result = evaluate("process", scores)
    assert result["score"] == 0.0
    assert result["grade"] == "E"


def test_evaluate_clamps_above_max():
    scores = {"steps": 999, "bottlenecks": 0, "compliance": 0, "automation": 0, "repeatability": 0}
    result = evaluate("process", scores)
    # steps weight=1.0 out of total 5.0 → 1/5 = 20%
    assert result["score"] == pytest.approx(20.0, abs=0.2)


def test_evaluate_detail_count():
    scores = {c: 5 for c in ["steps", "bottlenecks", "compliance", "automation", "repeatability"]}
    result = evaluate("process", scores)
    assert len(result["details"]) == 5


def test_evaluate_detail_fields():
    scores = {"steps": 8, "bottlenecks": 6, "compliance": 9, "automation": 5, "repeatability": 7}
    result = evaluate("process", scores)
    detail = next(d for d in result["details"] if d["id"] == "steps")
    assert detail["value"] == 8
    assert detail["max"] == 10
    assert detail["contribution"] == pytest.approx(80.0, abs=0.1)


def test_evaluate_all_templates():
    system_scores = {c: 5 for c in ["reliability", "performance", "security", "maintainability", "scalability"]}
    assert 0 < evaluate("system", system_scores)["score"] < 100

    sentiment_scores = {c: 5 for c in ["satisfaction", "tone", "friction", "loyalty", "responsiveness"]}
    assert 0 < evaluate("sentiment", sentiment_scores)["score"] < 100


def test_evaluate_unknown_template():
    with pytest.raises(ValueError, match="inconnu"):
        evaluate("nonexistent", {})
