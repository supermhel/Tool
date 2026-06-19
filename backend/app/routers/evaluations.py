from fastapi import APIRouter, HTTPException

from ..models import EvaluationRequest, Ticket
from ..scoring import evaluate
from ..templates_data import get_template
from ..storage import store

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("", response_model=Ticket, summary="Run an evaluation and create a ticket")
def create_evaluation(req: EvaluationRequest):
    """Compute the score (weighted average of criteria, normalised to 100) and grade,
    then persist the result as a ticket."""
    tpl = get_template(req.template_id)
    if tpl is None:
        raise HTTPException(404, f"Unknown template: {req.template_id}")
    try:
        result = evaluate(req.template_id, req.scores)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    ticket = store.create({
        "template_id": req.template_id,
        "template_name": tpl["name"],
        "subject": req.subject,
        "score": result["score"],
        "grade": result["grade"],
        "grade_label": result["grade_label"],
        "details": result["details"],
        "notes": req.notes,
    })
    return ticket
