from fastapi import APIRouter, HTTPException

from ..models import SensitivityRequest
from ..scoring import ScoringError
from ..sensitivity import analyze

# Stateless and stores nothing, so it needs no API key: it can back a free public calculator.
router = APIRouter(prefix="/api/v1/sensitivity", tags=["sensitivity"])


@router.post("", summary="Would a different weighting change the winner? (stateless)")
def sensitivity(req: SensitivityRequest):
    """For each criterion: the exact relative weight change at which the leader is
    overtaken (`tie_at_pct`), and the winner under ±`delta` scenarios."""
    try:
        return analyze(
            [c.model_dump() for c in req.criteria],
            [b.model_dump() for b in req.bidders],
            req.delta,
        )
    except ScoringError as exc:
        raise HTTPException(422, str(exc))
