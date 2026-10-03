from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from .. import repo, tenders as svc
from ..auth import Caller, auth_enabled, get_caller
from ..models import ProposeIn, TenderConsensusIn, TenderIn, TenderScoreIn
from ..pdf import render_debrief_html, render_tender_report_html
from ..proposers import propose_all
from ..ratelimit import rate_limited
from ..scoring import ScoringError
from ..sensitivity import analyze

router = APIRouter(prefix="/api/v1/tenders", tags=["tenders"])


def _load(caller: Caller, tender_id: str) -> dict:
    doc = repo.tenders.get(caller.org, tender_id)
    if doc is None:
        raise HTTPException(404, "Tender not found")
    return doc


def _fail(exc: svc.TenderError):
    raise HTTPException(exc.status, exc.message)


def _update(caller: Caller, tender_id: str, mutate):
    """Atomic read-modify-write of a tender; maps domain errors and a missing tender to HTTP."""
    try:
        out = repo.tenders.update(caller.org, tender_id, mutate)
    except svc.TenderError as exc:
        _fail(exc)
    if out is None:
        raise HTTPException(404, "Tender not found")
    return out


@router.post("", status_code=201, summary="Create a tender (weights are fixed from this moment)")
def create_tender(req: TenderIn, caller: Caller = Depends(get_caller)):
    tpl = repo.templates.get(caller.org, req.template_id, req.template_version)
    if tpl is None:
        raise HTTPException(404, f"Unknown template: {req.template_id}")
    try:
        body = svc.build(req, tpl)
    except svc.TenderError as exc:
        _fail(exc)
    doc = repo.tenders.create(caller.org, body)
    repo.record(caller, "tender.create", "tender", doc["id"],
                {"template": tpl["id"], "version": tpl["version"],
                 "bidders": len(doc["bidders"]), "evaluators": len(doc["evaluators"])})
    return svc.public_view(doc)


@router.get("", summary="List tenders, newest first")
def list_tenders(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 caller: Caller = Depends(get_caller)):
    return [{"id": d["id"], "name": d["name"], "status": d["status"],
             "bidders": len(d["bidders"]), "evaluators": len(d["evaluators"]),
             "created_at": d["created_at"]}
            for d in repo.tenders.list(caller.org, limit, offset)]


@router.get("/{tender_id}", summary="Tender detail (scores stay hidden while scoring is open)")
def get_tender(tender_id: str, caller: Caller = Depends(get_caller)):
    return svc.public_view(_load(caller, tender_id))


@router.post("/{tender_id}/scores", summary="Submit or replace one evaluator's score (with auth on, only as the key's own label)")
def submit_score(tender_id: str, body: TenderScoreIn, caller: Caller = Depends(get_caller)):
    # With auth on, a key's label IS the evaluator identity: one key per committee member.
    if auth_enabled() and body.evaluator != caller.label:
        raise HTTPException(
            403, f"This key may only score as '{caller.label}'. Use a key labelled with your evaluator name.")
    doc, _ = _update(caller, tender_id, lambda d: svc.submit_score(
        d, body.bidder_id, body.evaluator, body.criterion_id, body.value, body.justification))
    # Values are not logged: they stay blind until scoring closes.
    repo.record(caller, "tender.score", "tender", tender_id,
                {"evaluator": body.evaluator, "bidder_id": body.bidder_id,
                 "criterion_id": body.criterion_id})
    return svc.progress(doc)


@router.post("/{tender_id}/close-scoring", summary="Lock scoring and reveal results")
def close_scoring(tender_id: str, caller: Caller = Depends(get_caller)):
    doc, _ = _update(caller, tender_id, svc.close_scoring)
    repo.record(caller, "tender.close_scoring", "tender", tender_id)
    return svc.results(doc)


@router.get("/{tender_id}/results", summary="Per-criterion statistics, flags and ranking")
def get_results(tender_id: str, caller: Caller = Depends(get_caller)):
    try:
        return svc.results(_load(caller, tender_id))
    except svc.TenderError as exc:
        _fail(exc)


@router.put("/{tender_id}/consensus", summary="Set a consensus value for one criterion of one bidder")
def put_consensus(tender_id: str, body: TenderConsensusIn, caller: Caller = Depends(get_caller)):
    doc, _ = _update(caller, tender_id, lambda d: svc.set_consensus(
        d, body.bidder_id, body.criterion_id, body.value, body.justification))
    repo.record(caller, "tender.consensus", "tender", tender_id,
                {"bidder_id": body.bidder_id, "criterion_id": body.criterion_id,
                 "value": body.value})
    return svc.results(doc)


@router.post("/{tender_id}/award", summary="Finalise: ranking, sealed tickets, read-only tender")
def award(tender_id: str, caller: Caller = Depends(get_caller)):
    with repo.tender_lock(caller.org, tender_id):   # serialises awards inside this process
        _update(caller, tender_id, svc.begin_award)  # atomic claim: consensus -> awarding (or resume)
        res = svc.write_award_tickets(caller.org, tender_id)
    doc = _load(caller, tender_id)
    repo.record(caller, "tender.award", "tender", tender_id,
                {"ranking": [(r["name"], r["score"]) for r in res["ranking"]]})
    return {**res, "ticket_ids": doc["ticket_ids"]}


@router.get("/{tender_id}/sensitivity",
            summary="Would a different weighting change the winner?")
def tender_sensitivity(tender_id: str, delta: float = Query(0.2, gt=0, le=1),
                       caller: Caller = Depends(get_caller)):
    doc = _load(caller, tender_id)
    try:
        res = svc.results(doc)
        return analyze(
            doc["template"]["criteria"],
            [{"name": b["name"], "scores": {c["criterion_id"]: c["effective"] for c in b["criteria"]}}
             for b in res["bidders"]],
            delta)
    except svc.TenderError as exc:
        _fail(exc)
    except ScoringError as exc:
        raise HTTPException(422, str(exc))


@router.post("/{tender_id}/propose",
             summary="Suggest evidence/scores for one bid (advice only, never saved)")
async def propose(tender_id: str, body: ProposeIn, caller: Caller = Depends(rate_limited)):
    """Returns one proposal per criterion: an evidence quote, an optional proposed score
    and a confidence. Nothing is stored; an evaluator must still submit each score with
    their own justification. Quotes that are not present in the text are dropped."""
    doc = _load(caller, tender_id)
    if doc["status"] != "scoring":
        raise HTTPException(409, "Proposals are only available while scoring is open.")
    if not any(b["id"] == body.bidder_id for b in doc["bidders"]):
        raise HTTPException(404, f"Unknown bidder: {body.bidder_id}")
    proposals = await propose_all(doc["template"]["criteria"], body.document_text)
    repo.record(caller, "tender.propose", "tender", tender_id,
                {"bidder_id": body.bidder_id, "provider": proposals[0].provider if proposals else None,
                 "document_chars": len(body.document_text)})
    return {"bidder_id": body.bidder_id, "proposals": [p.model_dump() for p in proposals]}


def _html(markup: str):
    return HTMLResponse(markup)


@router.get("/{tender_id}/report", summary="Award report (html | pdf)")
def report(tender_id: str, format: str = Query("html", pattern="^(html|pdf)$"),
           caller: Caller = Depends(get_caller)):
    doc = _load(caller, tender_id)
    if doc["status"] != "awarded":
        raise HTTPException(409, "The report is available once the tender is awarded.")
    return _html(render_tender_report_html(doc, svc.results(doc), auto_print=format == "pdf"))


@router.get("/{tender_id}/debrief/{bidder_id}", summary="Debrief letter for one bidder (html | pdf)")
def debrief(tender_id: str, bidder_id: str, format: str = Query("html", pattern="^(html|pdf)$"),
            caller: Caller = Depends(get_caller)):
    doc = _load(caller, tender_id)
    if doc["status"] != "awarded":
        raise HTTPException(409, "Debriefs are available once the tender is awarded.")
    if not any(b["id"] == bidder_id for b in doc["bidders"]):
        raise HTTPException(404, f"Unknown bidder: {bidder_id}")
    return _html(render_debrief_html(doc, svc.results(doc), bidder_id, auto_print=format == "pdf"))
