"""Logique de notation : critères pondérés -> score (0-100) -> grade."""

from .templates_data import get_template

# Grille de grades. Seuils paramétrables par template si besoin.
GRADES = [
    (85, "A", "Excellent"),
    (70, "B", "Bon"),
    (55, "C", "À surveiller"),
    (40, "D", "Insuffisant"),
    (0,  "E", "Critique"),
]


def score_to_grade(score: float):
    for threshold, letter, label in GRADES:
        if score >= threshold:
            return letter, label
    return "E", "Critique"


def evaluate(template_id: str, scores: dict):
    """Calcule le score normalisé sur 100 et le détail par critère.

    `scores` est un dict {criterion_id: note}.
    Lève ValueError si le template est inconnu.
    """
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"Template inconnu : {template_id}")

    total_weight = 0.0
    weighted = 0.0
    details = []

    for crit in template["criteria"]:
        cid = crit["id"]
        raw = float(scores.get(cid, 0))
        raw = max(0.0, min(raw, crit["max"]))  # borne dans [0, max]
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
