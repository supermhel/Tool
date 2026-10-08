import { useCallback, useEffect, useRef, useState } from "react";
import {
  Lock, Gavel, FileText, Sparkles, CheckCircle2, AlertTriangle, Save, EyeOff, Trophy, Users,
} from "lucide-react";
import { api } from "../api.js";
import { Btn, ErrorNote, GradeBadge, Skeleton } from "./ui.jsx";
import SensitivityResult from "./SensitivityResult.jsx";

const STAGES = [
  { id: "scoring", label: "Blind scoring" },
  { id: "consensus", label: "Consensus" },
  { id: "awarded", label: "Awarded" },
];

function Stepper({ status }) {
  // "awarding" is transient (award claimed, tickets being written); show it as the consensus step
  const at = STAGES.findIndex((s) => s.id === (status === "awarding" ? "consensus" : status));
  return (
    <ol className="flex items-center gap-2 flex-wrap" aria-label="Tender stage">
      {STAGES.map((s, i) => (
        <li key={s.id} aria-current={i === at ? "step" : undefined}
            className={`chip ${i < at ? "chip-good" : i === at ? "chip-acc" : ""}`}>
          {i < at && <CheckCircle2 size={11} />}{s.label}
        </li>
      ))}
    </ol>
  );
}

/* ── Ranking ─────────────────────────────────────────────────────────────── */
function Ranking({ ranking }) {
  return (
    <ol className="space-y-1.5">
      {ranking.map((r) => (
        <li key={r.name} className="flex items-center gap-3">
          <span className="w-6 text-xs text-faint tabular-nums text-right">{r.rank}</span>
          {r.rank === 1 && <Trophy size={13} className="text-warn -ml-1" aria-label="First place" />}
          <span className="flex-1 truncate text-sm" title={r.name}>{r.name}</span>
          <span className="text-sm tabular-nums">{r.score}</span>
        </li>
      ))}
    </ol>
  );
}

/* ── Scoring stage ───────────────────────────────────────────────────────── */
function ProposalAssist({ tender, bidderId, onUse }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [out, setOut] = useState(null);

  async function run() {
    setBusy(true); setErr("");
    try { setOut(await api.propose(tender.id, bidderId, text)); } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  const labels = Object.fromEntries(tender.template.criteria.map((c) => [c.id, c.label]));

  return (
    <details className="rounded-xl border border-line bg-surface p-3">
      <summary className="cursor-pointer text-sm font-semibold flex items-center gap-2">
        <Sparkles size={14} className="text-acc2" /> Find evidence in the bid text
      </summary>
      <p className="hint my-2">Paste this bidder's text. Suggestions are advice only: you still score and justify each criterion yourself.</p>
      <textarea className="input" rows={4} value={text} maxLength={50000} onChange={(e) => setText(e.target.value)}
                aria-label="Bid text" placeholder="Paste the relevant part of the bid…" />
      <Btn size="sm" icon={Sparkles} busy={busy} disabled={!text.trim()} onClick={run} className="mt-2">Suggest evidence</Btn>
      <ErrorNote>{err}</ErrorNote>
      {out && (
        <ul className="mt-3 space-y-2">
          {out.proposals.map((p) => (
            <li key={p.criterion_id} className="rounded-lg border border-line p-2.5 text-sm">
              <div className="flex items-center gap-2 flex-wrap">
                <b>{labels[p.criterion_id]}</b>
                <span className="chip">confidence {Math.round(p.confidence * 100)}%</span>
                {p.proposed_score !== null && <span className="chip chip-acc">suggested {p.proposed_score}</span>}
                <span className="hint ml-auto">{p.provider}</span>
              </div>
              {p.evidence_quote
                ? <blockquote className="text-muted mt-1.5 italic">"{p.evidence_quote}"</blockquote>
                : <p className="text-faint mt-1.5">{p.rationale}</p>}
              {!p.quote_verified && <p className="text-warn text-xs mt-1">The model's quote was not found in the text and was discarded.</p>}
              {p.evidence_quote && (
                <Btn size="sm" className="mt-2" onClick={() => onUse(p)}>Use as justification</Btn>
              )}
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

function ScoringStage({ tender, refresh, me }) {
  // With auth on, a key may only score as its own label (one key per committee member).
  const bound = me?.auth ? me.label : null;
  const allowed = !bound || tender.evaluators.includes(bound);
  const [picked, setPicked] = useState(tender.evaluators[0]);
  // Derived on every render: the key (and so `me`) can change while this stage stays mounted.
  const evaluator = bound && allowed ? bound : picked;
  const [bidderId, setBidderId] = useState(tender.bidders[0].id);
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [closing, setClosing] = useState(false);

  const crits = tender.template.criteria;
  const dk = (c) => `${evaluator}|${bidderId}|${c}`;
  const blank = (c) => ({ value: Math.round(c.max / 2), why: "", touched: false });
  const draft = (c) => drafts[dk(c.id)] || blank(c);
  const patch = (cid, p) => {
    const crit = crits.find((c) => c.id === cid);
    setDrafts((d) => ({ ...d, [dk(cid)]: { ...(d[dk(cid)] || blank(crit)), ...p } }));
  };
  const p = tender.progress;
  const unscored = crits.filter((c) => { const d = draft(c); return !d.touched && !d.saved; }).length;

  async function saveBidder() {
    setBusy(true); setErr("");
    try {
      for (const c of crits) {
        const d = draft(c);
        if (!d.touched) {
          if ((d.why || "").trim()) patch(c.id, { error: "Set the score first: click or move the slider." });
          continue;
        }
        if ((d.why || "").trim().length < 10) { patch(c.id, { error: "Write a justification of at least 10 characters." }); continue; }
        try {
          await api.submitScore(tender.id, { bidder_id: bidderId, evaluator, criterion_id: c.id, value: d.value, justification: d.why.trim() });
          patch(c.id, { saved: true, error: "", touched: false });
        } catch (e) { patch(c.id, { error: e.message }); }
      }
      await refresh();
    } finally { setBusy(false); }
  }

  async function close() {
    if (!window.confirm("Close scoring? Scores become final, results are revealed and nobody can edit them.")) return;
    setClosing(true); setErr("");
    try { await api.closeScoring(tender.id); await refresh(); } catch (e) { setErr(e.message); }
    finally { setClosing(false); }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 text-xs text-muted rounded-xl border border-line bg-surface px-3 py-2.5">
        <EyeOff size={14} className="mt-0.5 shrink-0 text-acc2" />
        <p>Scores are blind. The server withholds every evaluator's scores until scoring is closed, so you cannot
          see anyone else's, and nobody can see yours. Each score needs a written justification.</p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="who">Scoring as</label>
          <select id="who" className="input" value={evaluator} disabled={!!bound}
                  onChange={(e) => setPicked(e.target.value)}>
            {tender.evaluators.map((e) => <option key={e}>{e}</option>)}
          </select>
          {bound && allowed && <p className="hint mt-1">Your key is labelled “{bound}”, so you score as {bound}.</p>}
          {bound && !allowed && (
            <p role="alert" className="text-xs text-warn mt-1">
              Your key is labelled “{bound}”, which is not an evaluator of this tender, so it cannot submit scores.
              Use a key labelled with your evaluator name.
            </p>
          )}
        </div>
        <div>
          <span className="label">Submitted so far</span>
          <ul className="flex flex-wrap gap-1.5">
            {Object.entries(p.submitted).map(([e, n]) => (
              <li key={e} className={`chip ${n === p.expected_per_evaluator ? "chip-good" : ""}`}>
                <Users size={11} />{e} {n}/{p.expected_per_evaluator}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div role="tablist" aria-label="Bidder" className="tabs border-b border-line">
        {tender.bidders.map((b) => (
          <button key={b.id} role="tab" aria-selected={b.id === bidderId} className="tab" onClick={() => setBidderId(b.id)}>{b.name}</button>
        ))}
      </div>

      <ProposalAssist tender={tender} bidderId={bidderId}
        onUse={(pr) => patch(pr.criterion_id, { why: `Evidence: "${pr.evidence_quote}"`, ...(pr.proposed_score !== null ? { value: pr.proposed_score, touched: true } : {}) })} />

      <div className="space-y-5">
        {crits.map((c) => {
          const d = draft(c);
          return (
            <div key={c.id}>
              <div className="flex justify-between text-sm mb-1 gap-3">
                <label htmlFor={`v-${c.id}`} className="font-medium">{c.label}</label>
                <span className="text-muted tabular-nums">
                  {d.touched || d.saved ? d.value : "not scored"} / {c.max}
                  <span className="text-faint text-xs ml-1">· weight {c.weight}</span>
                  {d.saved && !d.touched && <CheckCircle2 size={12} className="inline ml-1.5 text-good" aria-label="Saved" />}
                </span>
              </div>
              <input id={`v-${c.id}`} type="range" min={0} max={c.max} step={c.max <= 20 ? 0.5 : c.max / 100}
                     value={d.value ?? 0} className="w-full" style={{ opacity: d.touched || d.saved ? 1 : 0.5 }}
                     onChange={(e) => patch(c.id, { value: Number(e.target.value), touched: true, saved: false })}
                     onPointerUp={() => patch(c.id, { touched: true, saved: false })}
                     onKeyUp={(e) => e.key.startsWith("Arrow") && patch(c.id, { touched: true, saved: false })} />
              {c.detail && <p className="hint">{c.detail}</p>}
              <textarea className="input input-sm mt-1.5" rows={2} value={d.why} maxLength={2000}
                        aria-label={`Justification for ${c.label}`} placeholder="Why this score? (required, min 10 characters)"
                        onChange={(e) => patch(c.id, { why: e.target.value })} />
              <ErrorNote>{d.error}</ErrorNote>
            </div>
          );
        })}
      </div>

      <ErrorNote>{err}</ErrorNote>
      {unscored > 0 && <p className="hint" role="status">{unscored} of {crits.length} criteria have no score entered this session for this bidder.</p>}
      <div className="flex items-center gap-3 flex-wrap pt-3 border-t border-line">
        <Btn variant="primary" icon={Save} busy={busy} disabled={!allowed} onClick={saveBidder}>Save scores for {tender.bidders.find((b) => b.id === bidderId).name}</Btn>
        <Btn icon={Lock} busy={closing} disabled={!p.complete} onClick={close} className="ml-auto"
             title={p.complete ? "" : "Every evaluator must score every bidder on every criterion"}>Close scoring</Btn>
      </div>
    </div>
  );
}

/* ── Results (consensus & awarded) ───────────────────────────────────────── */
function ConsensusForm({ crit, bidder, row, onSave }) {
  const [value, setValue] = useState(Math.round(row.mean));
  const [why, setWhy] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save() {
    setBusy(true); setErr("");
    try { await onSave({ bidder_id: bidder.bidder_id, criterion_id: crit.criterion_id, value: Number(value), justification: why.trim() }); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  }
  return (
    <div className="mt-2 rounded-lg border border-warn/40 bg-warn/5 p-2.5 space-y-2">
      <p className="text-xs text-warn flex items-center gap-1.5"><AlertTriangle size={12} /> Evaluators diverge; agree a consensus score.</p>
      <div className="flex gap-2">
        <input type="number" className="input input-sm tabular-nums" style={{ width: 80 }} min={0} max={crit.max} step="any"
               value={value} onChange={(e) => setValue(e.target.value)} aria-label="Consensus value" />
        <textarea className="input input-sm" rows={2} value={why} maxLength={2000} onChange={(e) => setWhy(e.target.value)}
                  aria-label="Consensus justification" placeholder="Reason for the agreed score (min 10 characters)" />
      </div>
      <Btn size="sm" variant="primary" busy={busy} disabled={why.trim().length < 10 || value === "" || Number.isNaN(Number(value))} onClick={save}>Save consensus</Btn>
      <ErrorNote>{err}</ErrorNote>
    </div>
  );
}

function ResultsTable({ results, onConsensus }) {
  return (
    <div className="space-y-4">
      {results.bidders.map((b) => (
        <div key={b.bidder_id} className="rounded-xl border border-line p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <h4 className="font-semibold">{b.name}</h4>
            <GradeBadge grade={b.grade} score={b.score} size={44} title={`${b.score} / 100 · ${b.grade_label}`} />
          </div>
          <div className="overflow-x-auto">
            <table className="data">
              <thead><tr><th>Criterion</th><th>Evaluators</th><th className="num">Mean</th><th className="num">Spread</th><th className="num">Final</th></tr></thead>
              <tbody>
                {b.criteria.map((c) => (
                  <tr key={c.criterion_id}>
                    <td>
                      {c.label}
                      {c.flagged && <span className={`chip ml-2 ${c.consensus ? "chip-good" : "chip-warn"}`}>{c.consensus ? "reconciled" : "divergent"}</span>}
                      {c.consensus && <p className="hint mt-1">Consensus: {c.consensus.justification}</p>}
                      {onConsensus && c.flagged && !c.consensus && <ConsensusForm crit={c} bidder={b} row={c} onSave={onConsensus} />}
                    </td>
                    <td className="text-muted">
                      {Object.entries(c.scores).map(([e, s]) => (
                        <div key={e} title={s.justification}>{e}: <span className="tabular-nums">{s.value}</span></div>
                      ))}
                    </td>
                    <td className="num">{c.mean}</td>
                    <td className="num">{Math.round(c.spread * 100)}%</td>
                    <td className="num font-semibold">{c.effective}/{c.max}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Workbench ───────────────────────────────────────────────────────────── */
export default function Workbench({ id, onChanged, me }) {
  const [tender, setTender] = useState(null);
  const [results, setResults] = useState(null);
  const [sens, setSens] = useState(null);
  const [delta, setDelta] = useState(20);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const latest = useRef(0);
  const refresh = useCallback(async () => {
    const mine = ++latest.current;       // a slower, older response must not overwrite a newer one
    const t = await api.tender(id);
    const r = t.status === "scoring" ? null : await api.tenderResults(id);
    if (mine !== latest.current) return;
    setTender(t);
    setResults(r);
    onChanged?.();
  }, [id, onChanged]);

  useEffect(() => {
    setTender(null); setResults(null); setSens(null); setErr("");
    refresh().catch((e) => setErr(e.message));
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const status = tender?.status;
  useEffect(() => {
    if (!status || status === "scoring") return;
    let live = true;
    const t = setTimeout(() => {
      api.tenderSensitivity(id, delta / 100).then((r) => live && setSens(r)).catch(() => live && setSens(null));
    }, 250); // a slider drag fires many changes; only the last one needs a request
    return () => { live = false; clearTimeout(t); };
  }, [id, status, delta, results]);

  if (err && !tender) return <ErrorNote>{err}</ErrorNote>;
  if (!tender) return <Skeleton className="h-72" />;

  async function award() {
    if (!window.confirm("Award this tender? The ranking is sealed into tamper-evident tickets and the tender becomes read-only.")) return;
    setBusy(true); setErr("");
    try { await api.award(id); await refresh(); } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  const guard = (fn) => () => fn().catch((e) => setErr(e.message));
  const pending = results?.pending_consensus.length || 0;

  return (
    <div className="space-y-5">
      <div className="card">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <h3 className="font-semibold text-lg truncate" title={tender.name}>{tender.name}</h3>
            <p className="hint">
              {tender.template.name} v{tender.template.version} · {tender.bidders.length} bidders · evaluators: {tender.evaluators.join(", ")}
              · divergence flag above {Math.round(tender.divergence_threshold * 100)}% of scale
            </p>
          </div>
          <Stepper status={tender.status} />
        </div>
        <details className="mt-3 text-xs text-muted">
          <summary className="cursor-pointer">Criteria and weights (fixed before scoring)</summary>
          <ul className="mt-1.5 grid sm:grid-cols-2 gap-x-6">
            {tender.template.criteria.map((c) => <li key={c.id}>{c.label} <span className="text-faint">· weight {c.weight}, scale 0–{c.max}</span></li>)}
          </ul>
        </details>
      </div>

      <ErrorNote>{err}</ErrorNote>

      {tender.status === "scoring" && <div className="card"><ScoringStage key={tender.id} tender={tender} refresh={refresh} me={me} /></div>}

      {results && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="font-semibold">{tender.status === "awarded" ? "Final ranking" : "Current ranking"}</h3>
            {(tender.status === "consensus" || tender.status === "awarding") && (
              <Btn variant="primary" icon={Gavel} busy={busy} disabled={pending > 0} onClick={award}
                   title={pending ? "Resolve divergent criteria first" : ""}>
                {tender.status === "awarding" ? "Resume award" : "Award tender"}
              </Btn>
            )}
            {tender.status === "awarded" && (
              <Btn icon={FileText} onClick={guard(() => api.openReport(id, "pdf"))}>Award report (PDF)</Btn>
            )}
          </div>
          <Ranking ranking={results.ranking} />
          {tender.status === "awarding" && (
            <p className="text-sm text-warn" role="status">
              An earlier award attempt was interrupted. Resume it: tickets already written are kept, none are duplicated.
            </p>
          )}
          {tender.status === "consensus" && (
            <p className={`text-sm ${pending ? "text-warn" : "text-good"}`} role="status">
              {pending ? `${pending} divergent ${pending === 1 ? "criterion needs" : "criteria need"} a consensus score before award.`
                : "No divergent criteria remain. Ready to award."}
            </p>
          )}
          {tender.status === "awarded" && (
            <div className="flex flex-wrap gap-2">
              {tender.bidders.map((b) => (
                <Btn key={b.id} size="sm" icon={FileText} onClick={guard(() => api.openDebrief(id, b.id, "pdf"))}>Debrief: {b.name}</Btn>
              ))}
            </div>
          )}
        </div>
      )}

      {results && (
        <div className="card">
          <h3 className="font-semibold mb-3">Scores by criterion</h3>
          <ResultsTable results={results}
                        onConsensus={tender.status === "consensus" ? async (c) => { await api.setConsensus(id, c); await refresh(); } : null} />
        </div>
      )}

      {results && (
        <div className="card">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <h3 className="font-semibold">Weight sensitivity</h3>
            <label className="flex items-center gap-2 text-xs text-muted">
              Plausible weight dispute
              <input type="range" min={5} max={50} step={5} value={delta} onChange={(e) => setDelta(Number(e.target.value))}
                     aria-label="Plausible weight change in percent" />
              <span className="tabular-nums w-10">±{delta}%</span>
            </label>
          </div>
          {sens ? <SensitivityResult result={sens} /> : <Skeleton className="h-24" />}
        </div>
      )}
    </div>
  );
}
