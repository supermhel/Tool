import { useCallback, useEffect, useState } from "react";
import { Plus, Gavel } from "lucide-react";
import { api } from "../api.js";
import { Btn, Empty, ErrorNote, Field, SectionTitle, Skeleton } from "../components/ui.jsx";
import Workbench from "../components/Workbench.jsx";

const STATUS_CHIP = { scoring: "chip-acc", consensus: "chip-warn", awarding: "chip-warn", awarded: "chip-good" };
const lines = (text) => text.split("\n").map((l) => l.trim()).filter(Boolean);

function CreateTender({ templates, onCreated, onCancel }) {
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState(templates[0]?.id || "");
  const [bidders, setBidders] = useState("");
  const [evaluators, setEvaluators] = useState("");
  const [threshold, setThreshold] = useState(30);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const tpl = templates.find((t) => t.id === templateId);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const t = await api.createTender({
        name: name.trim(), template_id: templateId, template_version: tpl?.version,
        bidders: lines(bidders), evaluators: lines(evaluators), divergence_threshold: threshold / 100,
      });
      onCreated(t.id);
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  return (
    <form className="card space-y-3" onSubmit={submit}>
      <h3 className="font-semibold">New tender</h3>
      <Field label="Name" htmlFor="t-name">
        <input id="t-name" className="input" value={name} maxLength={160} required onChange={(e) => setName(e.target.value)}
               placeholder="e.g. Cloud hosting 2026" />
      </Field>
      <Field label="Evaluation criteria" htmlFor="t-tpl" hint="Weights are snapshotted now, before any bid is scored.">
        <select id="t-tpl" className="input" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name} v{t.version} · {t.criteria.length} criteria</option>)}
        </select>
      </Field>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Bidders" htmlFor="t-bid" hint="One per line, at least 2">
          <textarea id="t-bid" className="input" rows={4} value={bidders} onChange={(e) => setBidders(e.target.value)} placeholder={"Acme\nGlobex"} />
        </Field>
        <Field label="Evaluators" htmlFor="t-ev" hint="One per line, at least 1">
          <textarea id="t-ev" className="input" rows={4} value={evaluators} onChange={(e) => setEvaluators(e.target.value)} placeholder={"alice\nbob"} />
        </Field>
      </div>
      <Field label={`Flag divergence above ${threshold}% of the scale`} htmlFor="t-thr"
             hint="When evaluators' scores for a criterion differ by more than this, a consensus score is required.">
        <input id="t-thr" type="range" min={5} max={100} step={5} value={threshold} className="w-full"
               onChange={(e) => setThreshold(Number(e.target.value))} />
      </Field>
      <ErrorNote>{err}</ErrorNote>
      <div className="flex gap-2">
        <Btn type="submit" variant="primary" icon={Plus} busy={busy}>Create tender</Btn>
        <Btn onClick={onCancel}>Cancel</Btn>
      </div>
    </form>
  );
}

export default function TendersView({ templates, me }) {
  const [list, setList] = useState(null);
  const [selected, setSelected] = useState(null);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => api.tenders().then(setList).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="grid lg:grid-cols-4 gap-6">
      <aside className="lg:col-span-1 space-y-3" aria-label="Tenders">
        <SectionTitle aside={<Btn size="sm" icon={Plus} onClick={() => { setCreating(true); setSelected(null); }}>New</Btn>}>Tenders</SectionTitle>
        <ErrorNote>{err}</ErrorNote>
        {list === null && !err && <Skeleton className="h-20" />}
        {list?.length === 0 && !creating && (
          <Empty icon={Gavel} title="No tenders yet">Create one to run blind multi-evaluator scoring.</Empty>
        )}
        <ul className="space-y-2">
          {list?.map((t) => (
            <li key={t.id}>
              <button onClick={() => { setSelected(t.id); setCreating(false); }} aria-current={selected === t.id}
                      className={`w-full text-left rounded-xl border p-3 transition-colors ${
                        selected === t.id ? "border-line2 bg-panel2" : "border-line bg-panel card-hover"}`}>
                <div className="font-semibold text-sm truncate">{t.name}</div>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`chip ${STATUS_CHIP[t.status]}`}>{t.status}</span>
                  <span className="hint">{t.bidders} bidders · {t.evaluators} evaluators</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="lg:col-span-3" aria-label="Tender workbench">
        {creating ? (
          <CreateTender templates={templates} onCancel={() => setCreating(false)}
                        onCreated={async (id) => { await load(); setCreating(false); setSelected(id); }} />
        ) : selected ? (
          <Workbench id={selected} onChanged={load} me={me} />
        ) : (
          <Empty icon={Gavel} title="Select or create a tender">
            Evaluators score each bid blind, divergent criteria go to consensus, and the award is sealed with a written
            justification for every score.
          </Empty>
        )}
      </section>
    </div>
  );
}
