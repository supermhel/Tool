"""Tender evaluation workbench: domain rules.

Lifecycle
  scoring   → each evaluator scores every bidder on every criterion, with a
              written justification. Scores are blind: nobody can read another
              evaluator's values (the API hides them until scoring is closed).
  consensus → scoring is closed and locked. Per-criterion spread between
              evaluators is computed; criteria whose spread exceeds the
              tender's threshold are flagged and MUST get a consensus value
              with a justification. Unflagged criteria default to the mean.
  awarding  → transient: the award has been claimed and tickets are being written.
              An interrupted award resumes by calling award again.
  awarded   → final ranking computed, one tamper-evident ticket written per
              bidder. The tender is then read-only.

The template (criteria + weights) is snapshotted at creation, so the weights
are fixed before any bid is scored.
"""

from . import repo
from .scoring import ScoringError, check_value, evaluate, score_to_grade, weighted_score
from .sensitivity import rank_scores


class TenderError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


MAX_CELLS = 3000  # bidders x criteria x evaluators; each cell stores a justification


def build(req, template: dict) -> dict:
    cells = len(req.bidders) * len(template["criteria"]) * len(req.evaluators)
    if cells > MAX_CELLS:
        raise TenderError(422, f"Tender too large: {len(req.bidders)} bidders x {len(template['criteria'])} "
                               f"criteria x {len(req.evaluators)} evaluators = {cells} scores (max {MAX_CELLS}).")
    return {
        "name": req.name.strip(),
        "status": "scoring",
        "template": {k: template[k] for k in ("id", "name", "version", "criteria")},
        "bidders": [{"id": f"b{i}", "name": n.strip()} for i, n in enumerate(req.bidders, 1)],
        "evaluators": [e.strip() for e in req.evaluators],
        "divergence_threshold": req.divergence_threshold,
        "scores": {},      # {bidder_id: {criterion_id: {evaluator: {value, justification, at}}}}
        "consensus": {},   # {bidder_id: {criterion_id: {value, justification, at}}}
        "ranking": [],
        "ticket_ids": {},
    }


def _criteria(doc) -> dict[str, dict]:
    return {c["id"]: c for c in doc["template"]["criteria"]}


def _bidder(doc, bidder_id) -> dict:
    for b in doc["bidders"]:
        if b["id"] == bidder_id:
            return b
    raise TenderError(404, f"Unknown bidder: {bidder_id}")


def progress(doc: dict) -> dict:
    crits, bidders = len(doc["template"]["criteria"]), len(doc["bidders"])
    per_eval = {e: 0 for e in doc["evaluators"]}
    for by_crit in doc["scores"].values():
        for by_eval in by_crit.values():
            for e in by_eval:
                per_eval[e] += 1
    return {"expected_per_evaluator": crits * bidders, "submitted": per_eval,
            "complete": all(n == crits * bidders for n in per_eval.values())}


def public_view(doc: dict) -> dict:
    """What the API returns. While scoring is open, score values are withheld."""
    view = {k: v for k, v in doc.items() if k not in ("scores", "consensus")}
    view["progress"] = progress(doc)
    if doc["status"] != "scoring":
        view["scores"], view["consensus"] = doc["scores"], doc["consensus"]
    return view


def submit_score(doc: dict, bidder_id, evaluator, criterion_id, value, justification) -> None:
    if doc["status"] != "scoring":
        raise TenderError(409, "Scoring is closed for this tender.")
    _bidder(doc, bidder_id)
    crit = _criteria(doc).get(criterion_id)
    if crit is None:
        raise TenderError(404, f"Unknown criterion: {criterion_id}")
    if evaluator not in doc["evaluators"]:
        raise TenderError(403, f"'{evaluator}' is not an evaluator of this tender.")
    try:
        v = check_value(value, crit)
    except ScoringError as exc:
        raise TenderError(422, str(exc)) from exc
    cell = doc["scores"].setdefault(bidder_id, {}).setdefault(criterion_id, {})
    cell[evaluator] = {"value": v, "justification": justification.strip(), "at": repo.now_iso()}


def close_scoring(doc: dict) -> None:
    if doc["status"] != "scoring":
        raise TenderError(409, "Scoring is already closed.")
    p = progress(doc)
    if not p["complete"]:
        missing = {e: p["expected_per_evaluator"] - n for e, n in p["submitted"].items() if n != p["expected_per_evaluator"]}
        raise TenderError(409, f"Scoring incomplete; scores still missing per evaluator: {missing}.")
    doc["status"] = "consensus"


def results(doc: dict) -> dict:
    """Per-bidder, per-criterion statistics and the current ranking."""
    if doc["status"] == "scoring":
        raise TenderError(409, "Results are hidden until scoring is closed.")
    crits = doc["template"]["criteria"]
    thr = doc["divergence_threshold"]
    bidders_out, totals, pending = [], {}, []
    for b in doc["bidders"]:
        rows, effective = [], {}
        for c in crits:
            given = doc["scores"][b["id"]][c["id"]]
            vals = [s["value"] for s in given.values()]
            mean = round(sum(vals) / len(vals), 2)
            spread = (max(vals) - min(vals)) / c["max"]
            flagged = len(vals) > 1 and spread > thr
            cons = doc["consensus"].get(b["id"], {}).get(c["id"])
            effective[c["id"]] = cons["value"] if cons else mean
            if flagged and not cons:
                pending.append({"bidder_id": b["id"], "criterion_id": c["id"]})
            rows.append({
                "criterion_id": c["id"], "label": c["label"], "weight": c["weight"], "max": c["max"],
                "scores": given, "mean": mean, "min": min(vals), "high": max(vals),
                "spread": round(spread, 3), "flagged": flagged,
                "consensus": cons, "effective": effective[c["id"]],
            })
        raw_total = weighted_score(crits, effective)
        totals[b["name"]] = raw_total          # rank on the exact value; rounding would invent ties
        total = round(raw_total, 1)
        letter, label = score_to_grade(total)
        bidders_out.append({"bidder_id": b["id"], "name": b["name"], "score": total,
                            "grade": letter, "grade_label": label, "criteria": rows})
    return {"status": doc["status"], "bidders": bidders_out,
            "ranking": rank_scores(totals), "pending_consensus": pending}


def set_consensus(doc: dict, bidder_id, criterion_id, value, justification) -> None:
    if doc["status"] != "consensus":
        raise TenderError(409, "Consensus can only be set after scoring is closed and before award.")
    _bidder(doc, bidder_id)
    crit = _criteria(doc).get(criterion_id)
    if crit is None:
        raise TenderError(404, f"Unknown criterion: {criterion_id}")
    try:
        v = check_value(value, crit)
    except ScoringError as exc:
        raise TenderError(422, str(exc)) from exc
    doc["consensus"].setdefault(bidder_id, {})[criterion_id] = {
        "value": v, "justification": justification.strip(), "at": repo.now_iso()}


def begin_award(doc: dict) -> None:
    """Claim the award. Mutation for Tenders.update: `consensus` -> `awarding`.

    `awarding` is also accepted, so an award interrupted half-way can be resumed; tickets already
    written are never written twice (see write_award_tickets)."""
    if doc["status"] not in ("consensus", "awarding"):
        raise TenderError(409, "Tender must be in the consensus stage to be awarded.")
    res = results(doc)
    if res["pending_consensus"]:
        raise TenderError(409, f"{len(res['pending_consensus'])} flagged criteria still need a "
                               f"consensus value: {res['pending_consensus']}")
    doc["status"] = "awarding"


def write_award_tickets(org: str, tender_id: str) -> dict:
    """Write one sealed ticket per bidder, then mark the tender awarded. Safe to re-run."""
    doc = repo.tenders.get(org, tender_id)
    res = results(doc)
    template = doc["template"]
    rank_of = {r["name"]: r["rank"] for r in res["ranking"]}
    n = len(doc["bidders"])
    for b in res["bidders"]:
        if b["bidder_id"] in doc["ticket_ids"]:
            continue
        ev = evaluate(template, {c["criterion_id"]: c["effective"] for c in b["criteria"]})
        ticket = repo.tickets.append(org, {
            "template_id": template["id"], "template_name": template["name"],
            "template_version": template["version"], "subject": b["name"],
            "score": ev["score"], "grade": ev["grade"], "grade_label": ev["grade_label"],
            "details": ev["details"], "tender_id": doc["id"],
            "notes": f"Tender '{doc['name']}': rank {rank_of[b['name']]} of {n}",
        })
        won = []

        def record(d, bid=b["bidder_id"], tid=ticket["id"]):
            won.clear()
            if bid in d["ticket_ids"]:
                return                      # another writer already recorded this bidder's ticket
            d["ticket_ids"][bid] = tid
            won.append(True)

        repo.tenders.update(org, tender_id, record)
        if not won:                         # lost the race: hide our duplicate (it stays sealed in the chain)
            repo.tickets.soft_delete(org, ticket["id"])

    def finish(d):
        d["ranking"] = res["ranking"]
        d["status"] = "awarded"
        d.setdefault("awarded_at", repo.now_iso())

    repo.tenders.update(org, tender_id, finish)
    return res
