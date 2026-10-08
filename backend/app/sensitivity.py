"""Weight-sensitivity analysis: would a different weighting change the winner?

Score_b = Σ w_i · r_bi / Σ w_i, with r = value / max. For the leader `a` and a
rival `b`, the lead is N = Σ w_j (r_aj − r_bj). Scaling one weight by (1 + t)
changes it to N + t · w_i · (r_ai − r_bi), which reaches zero (a tie) at
    t* = −N / (w_i · (r_ai − r_bi)).
That is exact, so no search or sampling is needed. A flip needs t* > −1
(a weight cannot go below zero).
"""

from .scoring import ScoringError, check_value


def rank_scores(scores: dict[str, float]) -> list[dict]:
    """Competition ranking (1, 2, 2, 4): equal scores share a rank."""
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    out, prev, rank = [], None, 0
    for i, (name, s) in enumerate(ordered, 1):
        if prev is None or abs(s - prev) > 1e-9:
            rank = i
        out.append({"rank": rank, "name": name, "score": round(s, 2)})
        prev = s
    return out


def _scores(weights: dict[str, float], ratios: dict[str, dict[str, float]]) -> dict[str, float]:
    total = sum(weights.values())
    return {b: sum(weights[c] * r[c] for c in weights) / total * 100 for b, r in ratios.items()}


def analyze(criteria: list[dict], bidders: list[dict], delta: float = 0.2) -> dict:
    """criteria: [{id,label,weight,max}]; bidders: [{name, scores:{cid: value}}]."""
    cmap = {c["id"]: c for c in criteria}
    ratios: dict[str, dict[str, float]] = {}
    for b in bidders:
        missing = sorted(set(cmap) - set(b["scores"]))
        unknown = sorted(set(b["scores"]) - set(cmap))
        if missing or unknown:
            raise ScoringError(
                f"Bidder '{b['name']}': " + (f"missing {', '.join(missing)}. " if missing else "")
                + (f"unknown {', '.join(unknown)}." if unknown else ""))
        ratios[b["name"]] = {
            cid: check_value(b["scores"][cid], c) / c["max"] for cid, c in cmap.items()
        }

    weights = {cid: c["weight"] for cid, c in cmap.items()}
    base = _scores(weights, ratios)
    ranking = rank_scores(base)
    top = ranking[0]
    tied = [r["name"] for r in ranking if r["rank"] == 1]
    result = {
        "ranking": ranking,
        "winner": top["name"] if len(tied) == 1 else None,
        "tie_at_top": len(tied) > 1,
        "margin": round(top["score"] - ranking[1]["score"], 2),
        "delta": delta,
        "criteria": [], "scenarios": [], "most_sensitive": None, "stable": len(tied) == 1,
    }
    if len(tied) > 1:
        return result

    a = top["name"]
    rivals = [n for n in ratios if n != a]
    for cid, c in cmap.items():
        best = None
        for b in rivals:
            lead = sum(weights[j] * (ratios[a][j] - ratios[b][j]) for j in weights)
            d = ratios[a][cid] - ratios[b][cid]
            if abs(d) < 1e-12:
                continue
            t = -lead / (weights[cid] * d)
            if t <= -1:
                continue  # would need a negative weight
            if best is None or abs(t) < abs(best[0]):
                best = (t, b)
        entry = {"id": cid, "label": c.get("label") or cid, "weight": weights[cid],
                 "tie_at_pct": None, "overtaken_by": None, "flips_within_delta": False}
        if best:
            entry["tie_at_pct"] = round(best[0] * 100, 1)
            entry["overtaken_by"] = best[1]

        flipped = False
        for sign in (-1, 1):
            w2 = dict(weights, **{cid: weights[cid] * (1 + sign * delta)})
            changed, winner = False, a
            if sum(w2.values()) > 0:   # delta=1 on the only criterion would leave nothing to weigh
                s = _scores(w2, ratios)
                others = {n: v for n, v in s.items() if n != a}
                rival = max(others, key=lambda n: (others[n], n))
                # Losing the strict lead (a tie included) counts as a change; names never decide.
                changed = others[rival] >= s[a] - 1e-9
                if changed:
                    tied = abs(others[rival] - s[a]) <= 1e-9
                    winner = None if tied else rival     # an exact tie has no winner
            flipped = flipped or changed
            result["scenarios"].append({
                "criterion_id": cid, "change_pct": round(sign * delta * 100),
                "winner": winner, "changed": changed,
            })
        # Derived from the scenarios themselves so the two can never disagree on float edges.
        entry["flips_within_delta"] = flipped
        result["criteria"].append(entry)

    flippable = [c for c in result["criteria"] if c["tie_at_pct"] is not None]
    if flippable:
        result["most_sensitive"] = min(flippable, key=lambda c: abs(c["tie_at_pct"]))
    result["stable"] = not any(c["flips_within_delta"] for c in result["criteria"])
    return result
