"""Scoring logic: weighted criteria → score (0-100) → grade."""

from .templates_data import get_template

GRADES = [
    (85, "A", "Excellent"),
    (70, "B", "Good"),
    (55, "C", "Watch"),
    (40, "D", "Poor"),
    (0,  "E", "Critical"),
]


def score_to_grade(score: float):
    for threshold, letter, label in GRADES:
        if score >= threshold:
            return letter, label
    return "E", "Critical"


def evaluate(template_id: str, scores: dict):
    """Compute the normalised score (0-100) and per-criterion breakdown.

    `scores` is a dict {criterion_id: value}.
    Raises ValueError if the template is unknown.
    """
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Unknown template: {template_id}")

    total_weight = 0.0
    weighted = 0.0
    details = []

    for crit in template["criteria"]:
        cid = crit["id"]
        raw = float(scores.get(cid, 0))
        raw = max(0.0, min(raw, crit["max"]))
        ratio = raw / crit["max"] if crit["max"] else 0.0
        weighted += ratio * crit["weight"]
        total_weight += crit["weight"]
        details.append({
            "id": cid,
            "label": crit["label"],
            "detail": crit["detail"],
            "value": raw,
            "max": crit["max"],
            "weight": crit["weight"],
            "contribution": round(ratio * 100, 1),
        })

    score = round((weighted / total_weight) * 100, 1) if total_weight else 0.0
    letter, label = score_to_grade(score)

    return {
        "score": score,
        "grade": letter,
        "grade_label": label,
        "details": details,
    }
