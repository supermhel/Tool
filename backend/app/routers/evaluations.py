from fastapi import APIRouter, Depends, HTTPException

from .. import repo
from ..auth import Caller, get_caller
from ..models import EvaluationRequest, Ticket
from ..scoring import ScoringError, evaluate

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.post("", response_model=Ticket, summary="Run an evaluation and create a ticket")
def create_evaluation(req: EvaluationRequest, caller: Caller = Depends(get_caller)):
    """Compute the score (weighted average of criteria, normalised to 100) and grade,
    then persist the result as a tamper-evident ticket. Every criterion of the
    template must be scored, and every value must lie within 0..max."""
    tpl = repo.templates.get(caller.org, req.template_id, req.template_version)
    if tpl is None:
        raise HTTPException(404, f"Unknown template: {req.template_id}"
                            + (f" v{req.template_version}" if req.template_version else ""))
    try:
        result = evaluate(tpl, req.scores)
    except ScoringError as exc:
        raise HTTPException(422, str(exc))

    ticket = repo.tickets.append(caller.org, {
        "template_id": tpl["id"],
        "template_name": tpl["name"],
        "template_version": tpl["version"],
        "subject": req.subject,
        "score": result["score"],
        "grade": result["grade"],
        "grade_label": result["grade_label"],
        "details": result["details"],
        "notes": req.notes,
    })
    repo.record(caller, "ticket.create", "ticket", ticket["id"],
                {"template": tpl["id"], "version": tpl["version"], "score": result["score"]})
    return ticket
