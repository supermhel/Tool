"""Scoring logic: weighted criteria → score (0-100) → grade.

Validation is strict on purpose: a score that silently treats a missing
criterion as 0, or clamps an out-of-range value, is a wrong number that looks
right. Anything malformed raises ScoringError and the API answers 422.
"""

import math

GRADES = [
    (85, "A", "Excellent"),
    (70, "B", "Good"),
    (55, "C", "Watch"),
    (40, "D", "Poor"),
    (0,  "E", "Critical"),
]


class ScoringError(ValueError):
    """Scores do not match the template."""


def score_to_grade(score: float):
    for threshold, letter, label in GRADES:
        if score >= threshold:
            return letter, label
    return "E", "Critical"


def check_value(value, crit: dict) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoringError(f"Criterion '{crit['id']}': value must be a number.")
    try:
        v = float(value)
    except OverflowError:  # an int too large for a float
        raise ScoringError(f"Criterion '{crit['id']}': value is out of range.") from None
    if not math.isfinite(v):
        raise ScoringError(f"Criterion '{crit['id']}': value must be finite.")
    if v < 0 or v > crit["max"]:
        raise ScoringError(
            f"Criterion '{crit['id']}': value {v:g} is outside 0..{crit['max']:g}."
        )
    return v


def validate_scores(template: dict, scores: dict) -> dict[str, float]:
    """Return {criterion_id: float}; raise ScoringError on any mismatch."""
    crits = {c["id"]: c for c in template["criteria"]}
    unknown = sorted(set(scores) - set(crits))
    if unknown:
        raise ScoringError(f"Unknown criteria: {', '.join(unknown)}.")
    missing = sorted(set(crits) - set(scores))
    if missing:
        raise ScoringError(f"Missing scores for: {', '.join(missing)}.")
    return {cid: check_value(scores[cid], crits[cid]) for cid in crits}


def weighted_score(criteria: list[dict], values: dict[str, float]) -> float:
    """Weighted average of attainment (value/max), 0..100, unrounded."""
    total = sum(c["weight"] for c in criteria)
    if not total:
        return 0.0
    acc = sum((values[c["id"]] / c["max"]) * c["weight"] for c in criteria if c["max"])
    return acc / total * 100


def evaluate(template: dict, scores: dict):
    """Compute the normalised score (0-100) and per-criterion breakdown.

    `template` is a template dict (built-in or custom); `scores` is
    {criterion_id: value}. Raises ScoringError if scores don't fit it.
    """
    values = validate_scores(template, scores)
    details = []
    for crit in template["criteria"]:
        raw = values[crit["id"]]
        ratio = raw / crit["max"] if crit["max"] else 0.0
        details.append({
            "id": crit["id"],
            "label": crit["label"],
            "detail": crit.get("detail", ""),
            "value": round(raw, 2),
            "max": crit["max"],
            "weight": crit["weight"],
            "contribution": round(ratio * 100, 1),
        })

    score = round(weighted_score(template["criteria"], values), 1)
    letter, label = score_to_grade(score)
    return {"score": score, "grade": letter, "grade_label": label, "details": details}
