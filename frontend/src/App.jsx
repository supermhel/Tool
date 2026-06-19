import { useEffect, useState, useRef } from "react";
import YAML from "js-yaml";
import mammoth from "mammoth";
import {
  Activity, Server, HeartPulse, FileText, FileJson, Trash2,
  Send, Bot, Plug, CheckCircle2, XCircle, Loader2, ClipboardList,
  Upload, Sparkles, ChevronRight, TrendingUp,
} from "lucide-react";
import { api } from "./api.js";

const ICONS = { process: Activity, system: Server, sentiment: HeartPulse };
const GRADE_COLOR = {
  A: "#34c47a", B: "#7ed957", C: "#f0a742", D: "#f07042", E: "#e05555",
};
const GRADE_BG = {
  A: "#34c47a18", B: "#7ed95718", C: "#f0a74218", D: "#f0704218", E: "#e0555518",
};

/* ── Template picker ─────────────────────────────────────────────────── */
function TemplatePicker({ templates, selected, onSelect }) {
  return (
    <div className="grid sm:grid-cols-3 gap-3">
      {templates.map((t) => {
        const Icon = ICONS[t.id] || Activity;
        const active = selected?.id === t.id;
        return (
          <button
            key={t.id}
            onClick={() => onSelect(t)}
            className={`text-left rounded-2xl border p-4 transition-all duration-150 ${
              active
                ? "border-line2 bg-panel2 shadow-lg"
                : "border-line bg-panel card-hover"
            }`}
            style={active ? {
              borderColor: t.color,
              boxShadow: `0 0 0 1px ${t.color}22, 0 4px 24px ${t.color}18`,
            } : {}}
          >
            <div className="flex items-center gap-2 mb-1">
              <div className="w-7 h-7 rounded-lg grid place-items-center"
                   style={{ background: `${t.color}22` }}>
                <Icon size={15} style={{ color: t.color }} />
              </div>
              <span className="font-semibold text-sm">{t.name}</span>
              {active && <ChevronRight size={14} className="ml-auto text-faint" />}
            </div>
            <p className="text-xs text-muted leading-relaxed mt-1">{t.description}</p>
          </button>
        );
      })}
    </div>
  );
}

/* ── Upload custom template ──────────────────────────────────────────── */
function UploadTemplate({ onUpload }) {
  const fileRef = useRef(null);
  const [err, setErr] = useState("");

  function parseCsv(text) {
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return null;
    const hasHeader = /id|label|max|weight/i.test(lines[0]);
    const rows = lines.map((line) => {
      const cols = [];
      let cur = "", inQ = false;
      for (const ch of line) {
        if (ch === '"') { inQ = !inQ; continue; }
        if (ch === ',' && !inQ) { cols.push(cur); cur = ""; continue; }
        cur += ch;
      }
      cols.push(cur);
      return cols.map((c) => c.trim());
    });

    const result = { id: `csv-${Date.now()}`, name: "Uploaded CSV template", criteria: [], scope: { covered: [], excluded: [] } };
    if (hasHeader) {
      const headers = rows[0].map((h) => h.toLowerCase());
      for (let i = 1; i < rows.length; i++) {
        const r = rows[i];
        if (!r.length) continue;
        const obj = Object.fromEntries(headers.map((h, j) => [h, r[j]]));
        result.criteria.push({
          id: obj.id || `c${i}`, label: obj.label || obj.name || `Criterion ${i}`,
          max: Number(obj.max) || 10, weight: Number(obj.weight) || 1, detail: obj.detail || "",
        });
      }
    } else {
      rows.forEach((r, i) => result.criteria.push({
        id: r[0] || `c${i}`, label: r[1] || `Criterion ${i}`,
        max: Number(r[2]) || 10, weight: Number(r[3]) || 1, detail: r[4] || "",
      }));
    }
    return result;
  }

  async function handleFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const name = (f.name || "").toLowerCase();
    let tpl = null;

    function extractStructuredFromText(text) {
      try { const j = JSON.parse(text); if (j?.criteria) return j; } catch {}
      const jsMatch = text.match(/\{[\s\S]*\}/);
      if (jsMatch) { try { const j = JSON.parse(jsMatch[0]); if (j?.criteria) return j; } catch {} }
      try { const y = YAML.load(text); if (y?.criteria) return y; } catch {}
      try { const c = parseCsv(text); if (c?.criteria?.length) return c; } catch {}
      return null;
    }

    try {
      if (name.endsWith('.json')) {
        tpl = JSON.parse(await f.text());
      } else if (name.endsWith('.yaml') || name.endsWith('.yml')) {
        tpl = YAML.load(await f.text());
      } else if (name.endsWith('.csv') || f.type === 'text/csv') {
        tpl = parseCsv(await f.text());
      } else if (name.endsWith('.docx')) {
        const res = await mammoth.extractRawText({ arrayBuffer: await f.arrayBuffer() });
        tpl = extractStructuredFromText(res.value || "");
      } else {
        tpl = extractStructuredFromText(await f.text());
      }
      if (!tpl?.id || !tpl?.name || !Array.isArray(tpl.criteria)) throw new Error("Missing required fields (id, name, criteria)");
      tpl.criteria.forEach((c) => {
        if (!c.id || !c.label || typeof c.max !== "number" || typeof c.weight !== "number")
          throw new Error("Invalid criteria format");
      });
      tpl.scope = tpl.scope || { covered: [], excluded: [] };
      onUpload(tpl);
      setErr("");
    } catch (err) {
      setErr("Could not parse template: " + (err.message || err));
    }
    e.target.value = "";
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => fileRef.current?.click()}
        className="inline-flex items-center gap-2 border border-line2 hover:border-acc hover:text-acc rounded-xl px-3 py-2 text-sm text-muted transition-colors"
      >
        <Upload size={14} />
        Load custom template
      </button>
      <input
        ref={fileRef} type="file"
        accept="application/json,.json,.yaml,.yml,text/csv,.csv,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={handleFile} className="hidden"
      />
      {err && <span className="text-xs text-bad">{err}</span>}
    </div>
  );
}

/* ── Scope blocks ────────────────────────────────────────────────────── */
function ScopeBlocks({ scope }) {
  if (!scope) return null;
  return (
    <div className="grid sm:grid-cols-2 gap-2 mt-4">
      <div className="rounded-xl border border-line bg-surface p-3">
        <div className="text-[10px] font-bold uppercase tracking-widest text-good mb-2">Covered</div>
        <ul className="space-y-1">
          {scope.covered.map((c, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-muted">
              <CheckCircle2 size={12} className="text-good mt-0.5 shrink-0" />{c}
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-line bg-surface p-3">
        <div className="text-[10px] font-bold uppercase tracking-widest text-faint mb-2">Not covered</div>
        <ul className="space-y-1">
          {scope.excluded.map(({ label, ref }, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-muted">
              <ChevronRight size={12} className="text-faint mt-0.5 shrink-0" />
              {label} <span className="text-faint ml-1">→ {ref}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ── Evaluation form ─────────────────────────────────────────────────── */
function EvalForm({ template, onCreated }) {
  const [subject, setSubject] = useState("");
  const [notes, setNotes] = useState("");
  const [scores, setScores] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const init = {};
    template.criteria.forEach((c) => (init[c.id] = Math.round(c.max / 2)));
    setScores(init);
    setSubject(""); setNotes(""); setErr("");
  }, [template]);

  const totalW = template.criteria.reduce((s, c) => s + c.weight, 0);
  const weighted = template.criteria.reduce(
    (s, c) => s + ((scores[c.id] ?? 0) / c.max) * c.weight, 0);
  const estimate = totalW ? Math.round((weighted / totalW) * 1000) / 10 : 0;
  const estGrade = estimate >= 85 ? "A" : estimate >= 70 ? "B" : estimate >= 55 ? "C" : estimate >= 40 ? "D" : "E";

  async function submit() {
    if (!subject.trim()) { setErr("Please provide the subject being evaluated."); return; }
    setBusy(true); setErr("");
    try {
      const ticket = await api.evaluate({
        template_id: template.id, subject: subject.trim(), scores, notes: notes || null,
      });
      onCreated(ticket);
      setSubject(""); setNotes("");
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl grid place-items-center"
               style={{ background: `${template.color}22` }}>
            {(() => { const I = ICONS[template.id] || Activity; return <I size={16} style={{ color: template.color }} />; })()}
          </div>
          <h3 className="font-semibold">Evaluate — <span style={{ color: template.color }}>{template.name}</span></h3>
        </div>
        {/* Live estimate badge */}
        <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold"
             style={{ background: GRADE_BG[estGrade], color: GRADE_COLOR[estGrade] }}>
          <TrendingUp size={13} />
          {estimate} / 100 · {estGrade}
        </div>
      </div>

      <input
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject being evaluated (e.g. Onboarding process, Payment API, Acme Corp…)"
        className="w-full bg-surface border border-line rounded-xl px-3 py-2.5 text-sm outline-none focus:border-acc transition-colors placeholder:text-faint"
      />

      <div className="mt-5 space-y-4">
        {template.criteria.map((c) => {
          const val = scores[c.id] ?? 0;
          const pct = (val / c.max) * 100;
          return (
            <div key={c.id}>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium">{c.label}</span>
                <span className="text-muted tabular-nums">
                  {val} / {c.max}
                  <span className="text-faint text-xs ml-1">· w {c.weight}</span>
                </span>
              </div>
              {/* Progress track */}
              <div className="relative h-1.5 rounded-full bg-surface overflow-hidden mb-1">
                <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-100"
                     style={{ width: `${pct}%`, background: template.color }} />
              </div>
              <input
                type="range" min={0} max={c.max} value={val}
                onChange={(e) => setScores({ ...scores, [c.id]: Number(e.target.value) })}
                className="w-full"
              />
              <p className="text-xs text-faint mt-0.5">{c.detail}</p>
            </div>
          );
        })}
      </div>

      <textarea
        value={notes} onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes (optional)" rows={2}
        className="w-full mt-4 bg-surface border border-line rounded-xl px-3 py-2.5 text-sm outline-none focus:border-acc transition-colors placeholder:text-faint resize-none"
      />

      <ScopeBlocks scope={template.scope} />

      {err && <p className="text-bad text-xs mt-3">{err}</p>}

      <button
        onClick={submit} disabled={busy}
        className="mt-4 inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50 hover:brightness-110 active:scale-95"
        style={{ background: `linear-gradient(135deg, ${template.color}, ${template.color}cc)` }}
      >
        {busy ? <Loader2 size={15} className="animate-spin" /> : <ClipboardList size={15} />}
        Create ticket
      </button>
    </div>
  );
}

/* ── Ticket card ─────────────────────────────────────────────────────── */
function TicketCard({ t, onDelete }) {
  const color = GRADE_COLOR[t.grade] || "#5b8cff";
  const bg = GRADE_BG[t.grade] || "#5b8cff18";
  return (
    <div className="card card-hover transition-all duration-150 group">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] text-faint mb-0.5 truncate">
            {t.template_name} · {new Date(t.created_at).toLocaleString()}
          </div>
          <div className="font-semibold truncate">{t.subject}</div>
        </div>
        {/* Grade badge */}
        <div className="shrink-0 w-14 h-14 rounded-2xl grid place-items-center"
             style={{ background: bg, border: `1px solid ${color}44` }}
             title={`${t.score} / 100 · ${t.grade_label}`}>
          <div className="text-2xl font-black leading-none" style={{ color }}>{t.grade}</div>
          <div className="text-[10px] font-semibold mt-0.5" style={{ color }}>{t.score}</div>
        </div>
      </div>

      {/* Criteria bars */}
      <div className="mt-3 space-y-1.5">
        {t.details.map((d) => (
          <div key={d.id} className="flex items-center gap-2">
            <span className="w-36 truncate text-xs text-muted shrink-0">{d.label}</span>
            <div className="flex-1 h-1 rounded-full bg-surface overflow-hidden">
              <div className="h-full rounded-full transition-all"
                   style={{ width: `${d.contribution}%`, background: `${color}cc` }} />
            </div>
            <span className="text-[11px] text-faint tabular-nums w-12 text-right shrink-0">
              {d.value}/{d.max}
            </span>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-line">
        <a href={api.exportUrl(t.id, "pdf")} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1.5 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:border-line2 hover:text-acc transition-colors text-muted">
          <FileText size={13} /> PDF
        </a>
        <a href={api.exportUrl(t.id, "json")} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1.5 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:border-line2 hover:text-acc transition-colors text-muted">
          <FileJson size={13} /> JSON
        </a>
        <button onClick={() => onDelete(t.id)}
           className="ml-auto inline-flex items-center gap-1.5 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:border-bad/60 hover:text-bad transition-colors text-faint">
          <Trash2 size={13} /> Delete
        </button>
      </div>
    </div>
  );
}

/* ── Chatbot ─────────────────────────────────────────────────────────── */
function Chatbot({ tickets }) {
  const [msgs, setMsgs] = useState([
    { role: "assistant", content: "Ask a question about your evaluations — e.g. \"Which subject has the lowest grade?\"" },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    const next = [...msgs, { role: "user", content: q }];
    setMsgs(next); setInput(""); setBusy(true);
    try {
      const history = next.slice(1).map((m) => ({ role: m.role, content: m.content }));
      const res = await api.chat(history);
      setMsgs([...next, { role: "assistant", content: res.reply, model: res.model }]);
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: "Error: " + e.message }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="card flex flex-col" style={{ height: 460 }}>
      {/* Header */}
      <div className="flex items-center gap-2 pb-3 mb-3 border-b border-line">
        <div className="w-7 h-7 rounded-lg grid place-items-center bg-acc2/10">
          <Bot size={15} className="text-acc2" />
        </div>
        <span className="font-semibold text-sm">Assistant</span>
        <span className="ml-auto text-xs text-faint">{tickets.length} ticket{tickets.length !== 1 ? "s" : ""} in context</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === "user"
                ? "bg-acc text-white rounded-br-sm"
                : "bg-panel2 border border-line text-muted rounded-bl-sm"
            }`}>
              {m.content}
              {m.model && (
                <div className="text-[10px] mt-1 opacity-50">model: {m.model}</div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="bg-panel2 border border-line rounded-2xl rounded-bl-sm px-3.5 py-2.5">
              <div className="flex gap-1">
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-faint animate-bounce"
                       style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 mt-3 pt-3 border-t border-line">
        <input
          value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Ask about your tickets…"
          className="flex-1 bg-surface border border-line rounded-xl px-3 py-2 text-sm outline-none focus:border-acc transition-colors placeholder:text-faint"
        />
        <button onClick={send} disabled={busy}
          className="w-9 h-9 grid place-items-center rounded-xl bg-acc2 text-ink font-bold hover:brightness-110 disabled:opacity-40 transition-all active:scale-95 shrink-0">
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

/* ── API panel ───────────────────────────────────────────────────────── */
const ENDPOINTS = [
  ["GET",  "/api/v1/templates",                    "List templates"],
  ["POST", "/api/v1/evaluations",                  "Create evaluation → ticket"],
  ["GET",  "/api/v1/tickets",                      "List tickets"],
  ["GET",  "/api/v1/tickets/{id}/export?format=…", "Export (pdf | json | html)"],
  ["POST", "/api/v1/chat",                         "Chatbot (ticket context)"],
  ["GET",  "/api/v1/health",                       "Health check"],
];

function ApiPanel({ health }) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg grid place-items-center bg-acc/10">
          <Plug size={14} className="text-acc" />
        </div>
        <span className="font-semibold text-sm">REST API</span>
        <a href="/docs" target="_blank" rel="noreferrer"
           className="ml-auto text-xs text-acc hover:underline">Swagger →</a>
      </div>

      <div className="flex items-center gap-2 mb-3 text-xs">
        {health === "ok"
          ? <><CheckCircle2 size={13} className="text-good" /><span className="text-good">Backend connected</span></>
          : <><XCircle size={13} className="text-bad" /><span className="text-bad">Backend unreachable</span></>}
      </div>

      <div className="space-y-1.5">
        {ENDPOINTS.map(([method, path, desc]) => (
          <div key={path}
               className="flex items-center gap-2 rounded-xl bg-surface border border-line px-3 py-2 font-mono text-xs">
            <span className={`font-bold shrink-0 ${method === "GET" ? "text-good" : "text-acc"}`}>
              {method}
            </span>
            <span className="text-text/70 truncate">{path}</span>
            <span className="ml-auto text-faint font-sans hidden lg:block shrink-0">{desc}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── App ─────────────────────────────────────────────────────────────── */
export default function App() {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState("?");
  const [loadErr, setLoadErr] = useState("");

  function handleUploadTemplate(tpl) {
    setTemplates((prev) => prev.find((p) => p.id === tpl.id) ? prev : [tpl, ...prev]);
    setSelected(tpl);
  }

  useEffect(() => {
    api.templates()
      .then((t) => { setTemplates(t); setSelected(t[0]); })
      .catch((e) => setLoadErr(e.message));
    api.health().then(() => setHealth("ok")).catch(() => setHealth("ko"));
    api.tickets().then(setTickets).catch(() => {});
  }, []);

  function onCreated(ticket) { setTickets((prev) => [ticket, ...prev]); }
  async function onDelete(id) {
    await api.deleteTicket(id).catch(() => {});
    setTickets((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <div className="min-h-full">
      {/* ── Header ── */}
      <header className="border-b border-line backdrop-blur-sm sticky top-0 z-10"
              style={{ background: "rgba(8,11,18,.85)" }}>
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl grid place-items-center border border-line2"
               style={{ background: "linear-gradient(135deg,#4f7eff22,#34d1b022)" }}>
            <Sparkles size={17} className="text-gradient" style={{ color: "#4f7eff" }} />
          </div>
          <div>
            <div className="font-extrabold leading-tight tracking-tight text-gradient">Tool</div>
            <div className="text-[11px] text-faint">Generic evaluation platform</div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${health === "ok" ? "bg-good" : "bg-bad"}`}
                 title={health === "ok" ? "API connected" : "API unreachable"} />
            <span className="text-xs text-faint hidden sm:block">
              {health === "ok" ? "API connected" : "API offline"}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-8 grid lg:grid-cols-3 gap-6">
        {/* ── Left column ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Upload row */}
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm text-muted uppercase tracking-wider">Templates</h2>
            <UploadTemplate onUpload={handleUploadTemplate} />
          </div>

          {loadErr && (
            <div className="rounded-2xl border border-bad/30 bg-bad/5 text-bad text-sm px-4 py-3">
              Could not load templates: {loadErr}. Make sure the backend is running.
            </div>
          )}

          {templates.length > 0 && (
            <>
              <TemplatePicker templates={templates} selected={selected} onSelect={setSelected} />
              {selected && <EvalForm template={selected} onCreated={onCreated} />}
            </>
          )}

          {/* Tickets section */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-muted uppercase tracking-wider">
                Tickets
              </h2>
              {tickets.length > 0 && (
                <span className="text-xs text-faint tabular-nums">{tickets.length} total</span>
              )}
            </div>
            {tickets.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-line p-8 text-center">
                <ClipboardList size={28} className="text-faint mx-auto mb-2" />
                <p className="text-sm text-faint">No tickets yet. Run an evaluation above.</p>
              </div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {tickets.map((t) => (
                  <TicketCard key={t.id} t={t} onDelete={onDelete} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Right column ── */}
        <div className="space-y-6">
          <Chatbot tickets={tickets} />
          <ApiPanel health={health} />
        </div>
      </main>

      <footer className="max-w-6xl mx-auto px-5 py-6 border-t border-line mt-4">
        <p className="text-xs text-faint text-center">
          Tool · process / system / sentiment evaluation · weighted scoring → grade · PDF / JSON export
        </p>
      </footer>
    </div>
  );
}
