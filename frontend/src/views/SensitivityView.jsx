import { useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { api } from "../api.js";
import { Btn, ErrorNote, SectionTitle } from "../components/ui.jsx";
import SensitivityResult from "../components/SensitivityResult.jsx";

let counter = 0;
const key = () => `k${++counter}`;

function sample() {
  const crit = [
    { key: key(), label: "Price", weight: 40, max: 10 },
    { key: key(), label: "Technical quality", weight: 35, max: 10 },
    { key: key(), label: "Delivery plan", weight: 25, max: 10 },
  ];
  const scores = (a, b, c) => ({ [crit[0].key]: a, [crit[1].key]: b, [crit[2].key]: c });
  return {
    crit,
    bidders: [
      { key: key(), name: "Acme", scores: scores(9, 6, 7) },
      { key: key(), name: "Globex", scores: scores(6, 9, 6) },
      { key: key(), name: "Initech", scores: scores(7, 7, 8) },
    ],
  };
}

/** Client-side checks so the user sees a precise message before the API does. */
function validate(crit, bidders) {
  if (crit.length < 1) return "Add at least one criterion.";
  if (bidders.length < 2) return "Add at least two bidders.";
  for (const c of crit) {
    if (!c.label.trim()) return "Every criterion needs a name.";
    if (!(c.weight > 0)) return `"${c.label}": weight must be above 0.`;
    if (!(c.max > 0)) return `"${c.label}": scale maximum must be above 0.`;
  }
  const names = bidders.map((b) => b.name.trim().toLowerCase());
  if (names.some((n) => !n)) return "Every bidder needs a name.";
  if (new Set(names).size !== names.length) return "Bidder names must be different.";
  for (const b of bidders) for (const c of crit) {
    const v = b.scores[c.key];
    if (v === "" || v === undefined || Number.isNaN(Number(v))) return `${b.name}: enter a score for "${c.label}".`;
    if (v < 0 || v > c.max) return `${b.name}: "${c.label}" must be between 0 and ${c.max}.`;
  }
  return "";
}

export default function SensitivityView() {
  const [{ crit, bidders }, setData] = useState(sample);
  const [delta, setDelta] = useState(20);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");
  const seq = useRef(0);

  const setCrit = (fn) => setData((d) => ({ ...d, crit: fn(d.crit) }));
  const setBidders = (fn) => setData((d) => ({ ...d, bidders: fn(d.bidders) }));

  useEffect(() => {
    const problem = validate(crit, bidders);
    if (problem) { setErr(problem); setResult(null); return; }
    setErr("");
    const mine = ++seq.current;
    const t = setTimeout(async () => {
      const ids = Object.fromEntries(crit.map((c, i) => [c.key, `c${i + 1}`]));
      try {
        const res = await api.sensitivity({
          delta: delta / 100,
          criteria: crit.map((c) => ({ id: ids[c.key], label: c.label.trim(), weight: Number(c.weight), max: Number(c.max) })),
          bidders: bidders.map((b) => ({
            name: b.name.trim(),
            scores: Object.fromEntries(crit.map((c) => [ids[c.key], Number(b.scores[c.key])])),
          })),
        });
        if (mine === seq.current) setResult(res);
      } catch (e) { if (mine === seq.current) { setErr(e.message); setResult(null); } }
    }, 350);
    return () => clearTimeout(t);
  }, [crit, bidders, delta]);

  const setScore = (bk, ck, v) =>
    setBidders((bs) => bs.map((b) => (b.key === bk ? { ...b, scores: { ...b.scores, [ck]: v } } : b)));

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <section className="lg:col-span-3 space-y-4" aria-label="Inputs">
        <SectionTitle>Would a different weighting change the winner?</SectionTitle>
        <p className="text-sm text-muted max-w-prose">
          Enter your criteria weights and each bid's scores. The calculator finds the exact weight change at which
          another bid would overtake the leader. Nothing is stored; the example below is placeholder data.
        </p>

        <div className="card overflow-x-auto">
          <table className="data" style={{ minWidth: 520 }}>
            <thead>
              <tr>
                <th style={{ minWidth: 170 }}>Criterion</th>
                <th style={{ width: 80 }}>Weight</th>
                <th style={{ width: 80 }}>Scale 0–</th>
                {bidders.map((b) => (
                  <th key={b.key} style={{ minWidth: 110 }}>
                    <div className="flex items-center gap-1">
                      <input className="input input-sm" value={b.name} maxLength={120} aria-label="Bidder name"
                             onChange={(e) => setBidders((bs) => bs.map((x) => (x.key === b.key ? { ...x, name: e.target.value } : x)))} />
                      {bidders.length > 2 && (
                        <button aria-label={`Remove ${b.name}`} className="text-faint hover:text-bad p-1"
                                onClick={() => setBidders((bs) => bs.filter((x) => x.key !== b.key))}><X size={13} /></button>
                      )}
                    </div>
                  </th>
                ))}
                <th style={{ width: 40 }}>
                  <button aria-label="Add bidder" className="text-faint hover:text-acc p-1" disabled={bidders.length >= 50}
                          onClick={() => setBidders((bs) => [...bs, {
                            key: key(), name: `Bidder ${bs.length + 1}`,
                            scores: Object.fromEntries(crit.map((c) => [c.key, Math.round(c.max / 2)])),
                          }])}><Plus size={15} /></button>
                </th>
              </tr>
            </thead>
            <tbody>
              {crit.map((c) => (
                <tr key={c.key}>
                  <td>
                    <div className="flex items-center gap-1">
                      <input className="input input-sm" value={c.label} maxLength={80} aria-label="Criterion name"
                             onChange={(e) => setCrit((cs) => cs.map((x) => (x.key === c.key ? { ...x, label: e.target.value } : x)))} />
                      {crit.length > 1 && (
                        <button aria-label={`Remove ${c.label}`} className="text-faint hover:text-bad p-1"
                                onClick={() => setCrit((cs) => cs.filter((x) => x.key !== c.key))}><X size={13} /></button>
                      )}
                    </div>
                  </td>
                  {["weight", "max"].map((f) => (
                    <td key={f}>
                      <input className="input input-sm tabular-nums" type="number" min={0} step="any" value={c[f]}
                             aria-label={`${c.label} ${f === "max" ? "scale maximum" : "weight"}`}
                             onChange={(e) => setCrit((cs) => cs.map((x) => (x.key === c.key ? { ...x, [f]: e.target.value === "" ? "" : Number(e.target.value) } : x)))} />
                    </td>
                  ))}
                  {bidders.map((b) => (
                    <td key={b.key}>
                      <input className="input input-sm tabular-nums" type="number" min={0} max={c.max} step="any"
                             value={b.scores[c.key] ?? ""} aria-label={`${b.name}, ${c.label}`}
                             onChange={(e) => setScore(b.key, c.key, e.target.value === "" ? "" : Number(e.target.value))} />
                    </td>
                  ))}
                  <td />
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-4 flex-wrap mt-3 pt-3 border-t border-line">
            <Btn size="sm" icon={Plus} disabled={crit.length >= 30}
                 onClick={() => {
                   const k = key();
                   setData((d) => ({
                     crit: [...d.crit, { key: k, label: `Criterion ${d.crit.length + 1}`, weight: 10, max: 10 }],
                     bidders: d.bidders.map((b) => ({ ...b, scores: { ...b.scores, [k]: 5 } })),
                   }));
                 }}>Add criterion</Btn>
            <label className="flex items-center gap-2 text-xs text-muted ml-auto">
              Plausible weight dispute
              <input type="range" min={5} max={50} step={5} value={delta} onChange={(e) => setDelta(Number(e.target.value))}
                     aria-label="Plausible weight change in percent" />
              <span className="tabular-nums w-10">±{delta}%</span>
            </label>
          </div>
        </div>
        <Btn size="sm" onClick={() => setData(sample())}>Reset to example</Btn>
      </section>

      <section className="lg:col-span-2" aria-label="Result">
        <SectionTitle>Result</SectionTitle>
        <div className="card">
          {err ? <ErrorNote>{err}</ErrorNote>
            : result ? <SensitivityResult result={result} />
              : <p className="text-sm text-faint">Calculating…</p>}
        </div>
      </section>
    </div>
  );
}
