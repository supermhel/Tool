import { CheckCircle2, AlertTriangle } from "lucide-react";

const sign = (n) => (n > 0 ? `+${n}` : `${n}`);

/** Renders the output of POST /sensitivity or GET /tenders/{id}/sensitivity. */
export default function SensitivityResult({ result }) {
  if (!result) return null;
  const pct = Math.round(result.delta * 100);
  const sens = result.most_sensitive;
  const flips = result.scenarios.filter((s) => s.changed);
  const labelOf = Object.fromEntries(result.criteria.map((c) => [c.id, c.label]));

  let verdict;
  if (result.tie_at_top) {
    verdict = { bad: true, text: "The top bids are tied, so there is no single winner to stress-test." };
  } else if (result.stable) {
    verdict = {
      bad: false,
      text: sens
        ? `${result.winner} stays first for any single weight change up to ±${pct}%. The nearest tipping point is ${sens.label} at ${sign(sens.tie_at_pct)}%.`
        : `${result.winner} stays first however any single weight is changed: no other bid can overtake by reweighting.`,
    };
  } else {
    verdict = {
      bad: true,
      text: `${result.winner}'s lead is fragile: changing ${sens.label} by ${sign(sens.tie_at_pct)}% lets ${sens.overtaken_by} catch up. That is within the ±${pct}% you would plausibly argue over.`,
    };
  }

  const top = result.ranking[0]?.score || 1;
  return (
    <div className="space-y-5" aria-live="polite">
      <div className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm ${
        verdict.bad ? "border-warn/40 bg-warn/5 text-warn" : "border-good/40 bg-good/5 text-good"}`}>
        {verdict.bad ? <AlertTriangle size={16} className="mt-0.5 shrink-0" /> : <CheckCircle2 size={16} className="mt-0.5 shrink-0" />}
        <p>{verdict.text}</p>
      </div>

      <div>
        <h4 className="label">Ranking <span className="font-normal text-faint">· lead over second: {result.margin} points</span></h4>
        <ol className="space-y-1.5">
          {result.ranking.map((r) => (
            <li key={r.name} className="flex items-center gap-3">
              <span className="w-5 text-xs text-faint tabular-nums text-right">{r.rank}</span>
              <span className="w-32 truncate text-sm" title={r.name}>{r.name}</span>
              <div className="flex-1 h-2 rounded-full bg-surface overflow-hidden">
                <div className="h-full rounded-full bg-acc" style={{ width: `${(r.score / top) * 100}%`, opacity: r.rank === 1 ? 1 : 0.55 }} />
              </div>
              <span className="w-12 text-sm tabular-nums text-right">{Number(r.score.toFixed(1))}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="overflow-x-auto">
        <table className="data">
          <thead>
            <tr><th>Criterion</th><th className="num">Weight</th><th className="num">Tipping point</th><th>Overtaken by</th><th>±{pct}%</th></tr>
          </thead>
          <tbody>
            {result.criteria.map((c) => (
              <tr key={c.id}>
                <td>{c.label}</td>
                <td className="num">{c.weight}</td>
                <td className="num">{c.tie_at_pct === null ? "never" : `${sign(c.tie_at_pct)}%`}</td>
                <td>{c.overtaken_by || <span className="text-faint">–</span>}</td>
                <td>{c.flips_within_delta ? <span className="chip chip-warn">flips</span> : <span className="chip chip-good">holds</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint mt-2">
          Tipping point: the relative change to one weight, others fixed, at which the leader is tied by the nearest rival.
          "never" means no change to that weight alone can dethrone the leader.
        </p>
      </div>

      {flips.length > 0 && (
        <div>
          <h4 className="label">Scenarios that change the winner</h4>
          <ul className="text-sm text-muted space-y-1">
            {flips.map((s, i) => (
              <li key={i}>{labelOf[s.criterion_id]} {sign(s.change_pct)}% → {s.winner
                ? <><b style={{ color: "var(--text)" }}>{s.winner}</b> wins</>
                : <b style={{ color: "var(--text)" }}>exact tie for first</b>}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
