import { useEffect, useRef, useState } from "react";
import {
  Activity, Server, HeartPulse, FileText, FileJson, Trash2, ClipboardList, Upload,
  ChevronRight, CheckCircle2, TrendingUp, ShieldCheck, ShieldAlert, LayoutTemplate,
} from "lucide-react";
import { api } from "../api.js";
import { Btn, Empty, ErrorNote, GradeBadge, GRADE_BG, GRADE_COLOR, SectionTitle, gradeFor } from "../components/ui.jsx";
import Chatbot from "../components/Chatbot.jsx";

const ICONS = { process: Activity, system: Server, sentiment: HeartPulse };

/* ── Template picker ─────────────────────────────────────────────────────── */
function TemplatePicker({ templates, selected, onSelect, onDelete }) {
  return (
    <div className="grid sm:grid-cols-3 gap-3" role="radiogroup" aria-label="Template">
      {templates.map((t) => {
        const Icon = ICONS[t.id] || LayoutTemplate;
        const active = selected?.id === t.id;
        return (
          <div key={t.id} className="relative">
            <button
              role="radio" aria-checked={active} onClick={() => onSelect(t)}
              className={`w-full h-full text-left rounded-2xl border p-4 transition-colors duration-150 ${
                active ? "border-line2 bg-panel2" : "border-line bg-panel card-hover"}`}
              style={active ? { borderColor: t.color, boxShadow: `0 4px 20px ${t.color}18` } : {}}
            >
              <div className="flex items-center gap-2 mb-1 pr-6">
                <div className="w-7 h-7 rounded-lg grid place-items-center" style={{ background: `${t.color}22` }}>
                  <Icon size={15} style={{ color: t.color }} />
                </div>
                <span className="font-semibold text-sm truncate">{t.name}</span>
                {!t.builtin && <span className="chip">v{t.version}</span>}
                {active && <ChevronRight size={14} className="ml-auto text-faint shrink-0" />}
              </div>
              <p className="text-xs text-muted leading-relaxed mt-1">{t.description || `${t.criteria.length} criteria`}</p>
            </button>
            {!t.builtin && (
              <button onClick={() => onDelete(t)} aria-label={`Delete template ${t.name}`}
                      className="absolute top-2.5 right-2.5 p-1 rounded-md text-faint hover:text-bad transition-colors">
                <Trash2 size={13} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Template import (parsed server-side) ────────────────────────────────── */
function ImportTemplate({ onImported }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function handleFile(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(true); setErr("");
    try {
      if (f.size > 100_000) throw new Error("File is larger than 100 KB.");
      onImported(await api.importTemplate(f.name, await f.text()));
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <Btn icon={Upload} busy={busy} onClick={() => fileRef.current?.click()}>Import template</Btn>
      <input ref={fileRef} type="file" accept=".json,.yaml,.yml,.csv" onChange={handleFile}
             className="hidden" aria-label="Template file (JSON, YAML or CSV)" />
      <span className="hint">JSON, YAML or CSV · importing an existing id adds a new version</span>
      <ErrorNote>{err}</ErrorNote>
    </div>
  );
}

/* ── Scope blocks ────────────────────────────────────────────────────────── */
function ScopeBlocks({ scope }) {
  if (!scope || (!scope.covered?.length && !scope.excluded?.length)) return null;
  return (
    <div className="grid sm:grid-cols-2 gap-2 mt-4">
      <div className="rounded-xl border border-line bg-surface p-3">
        <h4 className="text-[11px] font-bold uppercase tracking-wider text-good mb-2">Covered</h4>
        <ul className="space-y-1">
          {scope.covered.map((c, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-muted">
              <CheckCircle2 size={12} className="text-good mt-0.5 shrink-0" />{c}
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-line bg-surface p-3">
        <h4 className="text-[11px] font-bold uppercase tracking-wider text-faint mb-2">Not covered</h4>
        <ul className="space-y-1">
          {scope.excluded.map(({ label, ref }, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-muted">
              <ChevronRight size={12} className="text-faint mt-0.5 shrink-0" />
              {label}{ref && <span className="text-faint ml-1">→ {ref}</span>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ── Evaluation form ─────────────────────────────────────────────────────── */
function EvalForm({ template, onCreated }) {
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");
  const [scores, setScores] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const Icon = ICONS[template.id] || LayoutTemplate;

  useEffect(() => {
    setScores(Object.fromEntries(template.criteria.map((c) => [c.id, Math.round(c.max / 2)])));
    setSubject(""); setNotes(""); setErr("");
  }, [template]);

  const totalW = template.criteria.reduce((s, c) => s + c.weight, 0);
  const weighted = template.criteria.reduce((s, c) => s + ((scores[c.id] ?? 0) / c.max) * c.weight, 0);
  const estimate = totalW ? Math.round((weighted / totalW) * 1000) / 10 : 0;
  const estGrade = gradeFor(estimate);

  async function submit(e) {
    e.preventDefault();
    if (!subject.trim()) { setErr("Enter the subject being evaluated."); return; }
    setBusy(true); setErr("");
    try {
      onCreated(await api.evaluate({
        template_id: template.id, template_version: template.version,
        subject: subject.trim(), scores, notes: notes.trim() || null,
      }));
      setSubject(""); setNotes("");
    } catch (e2) { setErr(e2.message); }
    finally { setBusy(false); }
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl grid place-items-center" style={{ background: `${template.color}22` }}>
            <Icon size={16} style={{ color: template.color }} />
          </div>
          <h3 className="font-semibold">Evaluate <span style={{ color: template.color }}>{template.name}</span></h3>
        </div>
        <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold tabular-nums"
             style={{ background: GRADE_BG[estGrade], color: GRADE_COLOR[estGrade] }}
             aria-live="polite" title="Live estimate; the server computes the final score">
          <TrendingUp size={13} /> {estimate} / 100 · {estGrade}
        </div>
      </div>

      <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200}
             aria-label="Subject" placeholder="Subject being evaluated (e.g. Onboarding process, Payment API, Acme Corp)" />

      <div className="mt-5 space-y-4">
        {template.criteria.map((c) => {
          const val = scores[c.id] ?? 0;
          return (
            <div key={c.id}>
              <div className="flex justify-between text-sm mb-1">
                <label htmlFor={`s-${c.id}`} className="font-medium">{c.label}</label>
                <span className="text-muted tabular-nums">
                  {val} / {c.max}<span className="text-faint text-xs ml-1">· weight {c.weight}</span>
                </span>
              </div>
              <input id={`s-${c.id}`} type="range" min={0} max={c.max} step={c.max <= 20 ? 1 : c.max / 100}
                     value={val} className="w-full"
                     onChange={(e) => setScores({ ...scores, [c.id]: Number(e.target.value) })} />
              {c.detail && <p className="hint">{c.detail}</p>}
            </div>
          );
        })}
      </div>

      <textarea className="input mt-4" rows={2} value={notes} maxLength={2000}
                onChange={(e) => setNotes(e.target.value)} aria-label="Notes" placeholder="Notes (optional)" />

      <ScopeBlocks scope={template.scope} />
      <ErrorNote>{err}</ErrorNote>

      <Btn type="submit" variant="primary" icon={ClipboardList} busy={busy} className="mt-4">Create ticket</Btn>
    </form>
  );
}

/* ── Ticket card ─────────────────────────────────────────────────────────── */
function TicketCard({ t, onDelete, onError }) {
  const color = GRADE_COLOR[t.grade] || "#4f7eff";
  const guard = (fn) => () => fn().catch((e) => onError(e.message));
  return (
    <article className="card card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] text-faint mb-0.5 truncate">
            {t.template_name} v{t.template_version} · {new Date(t.created_at).toLocaleString()}
          </div>
          <h3 className="font-semibold truncate" title={t.subject}>{t.subject}</h3>
        </div>
        <GradeBadge grade={t.grade} score={t.score} title={`${t.score} / 100 · ${t.grade_label}`} />
      </div>

      <div className="mt-3 space-y-1.5">
        {t.details.map((d) => (
          <div key={d.id} className="flex items-center gap-2">
            <span className="w-36 truncate text-xs text-muted shrink-0" title={d.label}>{d.label}</span>
            <div className="flex-1 h-1 rounded-full bg-surface overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${d.contribution}%`, background: `${color}cc` }} />
            </div>
            <span className="text-[11px] text-faint tabular-nums w-12 text-right shrink-0">{d.value}/{d.max}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-line">
        <Btn size="sm" icon={FileText} onClick={guard(() => api.openTicket(t.id, "pdf"))}>PDF</Btn>
        <Btn size="sm" icon={FileJson} onClick={guard(() => api.downloadTicket(t.id))}>JSON</Btn>
        <Btn size="sm" variant="danger" icon={Trash2} className="ml-auto" onClick={() => onDelete(t.id)}>Hide</Btn>
      </div>
    </article>
  );
}

/* ── Tickets section with integrity check ────────────────────────────────── */
function Tickets({ tickets, setTickets }) {
  const [verify, setVerify] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function check() {
    setBusy(true); setErr("");
    try { setVerify(await api.verifyTickets()); } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }
  async function remove(id) {
    try {
      await api.deleteTicket(id);
      setTickets((prev) => prev.filter((t) => t.id !== id));
    } catch (e) { setErr(e.message); }
  }

  return (
    <section aria-label="Tickets">
      <SectionTitle aside={
        <div className="flex items-center gap-3">
          {tickets.length > 0 && <span className="text-xs text-faint tabular-nums">{tickets.length} shown</span>}
          <Btn size="sm" icon={ShieldCheck} busy={busy} onClick={check}>Verify integrity</Btn>
        </div>
      }>Tickets</SectionTitle>

      {verify && (
        <p role="status" className={`chip ${verify.ok ? "chip-good" : "chip-bad"} mb-3`}>
          {verify.ok
            ? <><ShieldCheck size={12} /> Chain intact · {verify.count} sealed {verify.count === 1 ? "record" : "records"}</>
            : <><ShieldAlert size={12} /> Integrity failure at {verify.broken_at || "chain head"}: {verify.reason}</>}
        </p>
      )}
      <ErrorNote>{err}</ErrorNote>

      {tickets.length === 0 ? (
        <Empty icon={ClipboardList} title="No tickets yet">
          Score a subject above. Each ticket is sealed into a hash chain so later edits can be detected.
        </Empty>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {tickets.map((t) => <TicketCard key={t.id} t={t} onDelete={remove} onError={setErr} />)}
        </div>
      )}
    </section>
  );
}

/* ── View ────────────────────────────────────────────────────────────────── */
export default function EvaluateView({ templates, reloadTemplates, tickets, setTickets, loadErr }) {
  const [selectedId, setSelectedId] = useState(null);
  const [err, setErr] = useState("");
  const selected = templates.find((t) => t.id === selectedId) || templates[0];

  async function remove(t) {
    if (!window.confirm(`Delete template "${t.name}" and all its versions? Existing tickets keep their snapshot.`)) return;
    try { await api.deleteTemplate(t.id); await reloadTemplates(); setSelectedId(null); }
    catch (e) { setErr(e.message); }
  }

  return (
    <div className="grid lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
        <div>
          <SectionTitle>Templates</SectionTitle>
          <ImportTemplate onImported={async (tpl) => { await reloadTemplates(); setSelectedId(tpl.id); }} />
          <ErrorNote>{err}</ErrorNote>
        </div>

        {loadErr && (
          <div role="alert" className="rounded-2xl border border-bad/30 bg-bad/5 text-bad text-sm px-4 py-3">
            Could not load templates: {loadErr}
          </div>
        )}

        {templates.length > 0 && (
          <>
            <TemplatePicker templates={templates} selected={selected} onSelect={(t) => setSelectedId(t.id)} onDelete={remove} />
            {selected && <EvalForm template={selected} onCreated={(t) => setTickets((p) => [t, ...p])} />}
          </>
        )}

        <Tickets tickets={tickets} setTickets={setTickets} />
      </div>

      <div className="space-y-6">
        <Chatbot tickets={tickets} />
      </div>
    </div>
  );
}
