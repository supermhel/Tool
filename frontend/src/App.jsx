import { useEffect, useState, useRef } from "react";
import YAML from "js-yaml";
import mammoth from "mammoth";
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf";
// Configure pdfjs worker for browser usage (CDN fallback)
try {
  if (pdfjsLib.GlobalWorkerOptions) {
    const v = pdfjsLib.version || '3.8.162';
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${v}/build/pdf.worker.min.js`;
  }
} catch (e) {
  // ignore
}
import {
  Activity, Server, HeartPulse, FileText, FileJson, Trash2,
  Send, Bot, Plug, CheckCircle2, XCircle, Loader2, ClipboardList,
} from "lucide-react";
import { api } from "./api.js";

const ICONS = { process: Activity, system: Server, sentiment: HeartPulse };
const GRADE_COLOR = { A: "#46d39a", B: "#9fd356", C: "#ffb454", D: "#ff8e6b", E: "#ff6b6b" };

/* ------------------------------------------------------------------ */
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
            className={`text-left rounded-xl border p-4 transition ${
              active ? "border-line2 bg-panel2" : "border-line bg-panel hover:bg-panel2"
            }`}
            style={active ? { boxShadow: `inset 3px 0 0 ${t.color}` } : {}}
          >
            <div className="flex items-center gap-2">
              <Icon size={18} style={{ color: t.color }} />
              <span className="font-semibold">{t.name}</span>
            </div>
            <p className="text-sm text-muted mt-1">{t.description}</p>
          </button>
        );
      })}
    </div>
  );
}

function UploadTemplate({ onUpload }) {
  const fileRef = useRef(null);
  const [err, setErr] = useState("");

  function openPicker() { fileRef.current?.click(); }

  function parseCsv(text) {
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return null;
    const hasHeader = /id|label|max|weight/i.test(lines[0]);
    const rows = lines.map((line, idx) => {
      const cols = [];
      let cur = "", inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQ = !inQ; continue; }
        if (ch === ',' && !inQ) { cols.push(cur); cur = ""; continue; }
        cur += ch;
      }
      cols.push(cur);
      return cols.map((c) => c.trim());
    });

    const result = { id: `csv-${Date.now()}`, name: 'Uploaded CSV template', criteria: [], scope: { covered: [], excluded: [] } };
    if (hasHeader) {
      const headers = rows[0].map((h) => h.toLowerCase());
      for (let i = 1; i < rows.length; i++) {
        const r = rows[i];
        if (r.length === 0) continue;
        const obj = {};
        headers.forEach((h, j) => { obj[h] = r[j]; });
        const c = {
          id: obj.id || `c${i}`,
          label: obj.label || obj.name || `Criterion ${i}`,
          max: Number(obj.max) || 10,
          weight: Number(obj.weight) || 1,
          detail: obj.detail || "",
        };
        result.criteria.push(c);
      }
    } else {
      // assume columns: id,label,max,weight,detail
      rows.forEach((r, i) => {
        const c = {
          id: r[0] || `c${i}`,
          label: r[1] || `Criterion ${i}`,
          max: Number(r[2]) || 10,
          weight: Number(r[3]) || 1,
          detail: r[4] || "",
        };
        result.criteria.push(c);
      });
    }
    return result;
  }

  async function handleFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const name = (f.name || "").toLowerCase();
    let txt = "";
    async function extractPdfText(buffer) {
      const loadingTask = pdfjsLib.getDocument({ data: buffer });
      const pdf = await loadingTask.promise;
      let full = "";
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        const strings = content.items.map((it) => it.str || it.value || '');
        full += strings.join(' ') + '\n';
      }
      return full;
    }

    async function extractDocxText(buffer) {
      const res = await mammoth.extractRawText({ arrayBuffer: buffer });
      return res.value || "";
    }
    try {
      let tpl = null;
      function extractStructuredFromText(text) {
        // try raw JSON
        try { const j = JSON.parse(text); if (j && j.criteria) return j; } catch (e) {}
        // try JSON substring
        const jsMatch = text.match(/\{[\s\S]*\}/);
        if (jsMatch) {
          try { const j = JSON.parse(jsMatch[0]); if (j && j.criteria) return j; } catch (e) {}
        }
        // fallback: find first/last curly braces and try parse
        const first = text.indexOf('{');
        const last = text.lastIndexOf('}');
        if (first !== -1 && last !== -1 && last > first) {
          try { const j2 = JSON.parse(text.slice(first, last + 1)); if (j2 && j2.criteria) return j2; } catch (e) {}
        }
        // try YAML parse of full text
        try { const y = YAML.load(text); if (y && y.criteria) return y; } catch (e) {}
        // try YAML between markers
        const yamlMatch = text.match(/---BEGIN TEMPLATE[\s\S]*?---END TEMPLATE/mi);
        if (yamlMatch) {
          const inner = yamlMatch[0].replace(/---BEGIN TEMPLATE.*\n/i, '').replace(/---END TEMPLATE.*/i, '');
          try { const y2 = YAML.load(inner); if (y2 && y2.criteria) return y2; } catch (e) {}
        }
        // fallback to CSV
        try { const c = parseCsv(text); if (c && Array.isArray(c.criteria) && c.criteria.length) return c; } catch (e) {}
        return null;
      }

      if (name.endsWith('.json')) {
        txt = await f.text();
        tpl = JSON.parse(txt);
      } else if (name.endsWith('.yaml') || name.endsWith('.yml')) {
        txt = await f.text();
        tpl = YAML.load(txt);
      } else if (name.endsWith('.csv') || f.type === 'text/csv') {
        txt = await f.text();
        tpl = parseCsv(txt);
      } else if (name.endsWith('.docx')) {
        const buf = await f.arrayBuffer();
        txt = await extractDocxText(buf);
        tpl = extractStructuredFromText(txt);
      } else if (name.endsWith('.pdf')) {
        const buf = await f.arrayBuffer();
        txt = await extractPdfText(buf);
        tpl = extractStructuredFromText(txt);
      } else {
        // unknown extension: try text-based heuristics
        txt = await f.text();
        tpl = extractStructuredFromText(txt);
      }
      if (!tpl.id || !tpl.name || !Array.isArray(tpl.criteria)) throw new Error("missing required fields");
      tpl.criteria.forEach((c) => {
        if (!c.id || !c.label || typeof c.max !== "number" || typeof c.weight !== "number") {
          throw new Error("invalid criteria format");
        }
      });
      tpl.scope = tpl.scope || { covered: [], excluded: [] };
      onUpload(tpl);
      setErr("");
    } catch (err) {
      setErr("Failed to parse template: " + (err.message || err));
    }
    e.target.value = "";
  }

  return (
    <div className="flex items-center gap-3 mb-3">
      <button
        onClick={openPicker}
        className="inline-flex items-center gap-2 bg-acc hover:brightness-110 disabled:opacity-50 text-white font-semibold rounded-lg px-3 py-2 text-sm"
      >
        Load personal template
      </button>
      <input ref={fileRef} type="file" accept="application/json,.json,.yaml,.yml,text/csv,.csv" onChange={handleFile} className="hidden" />
      {err && <div className="text-sm text-bad">{err}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
function ScopeBlocks({ scope }) {
  if (!scope) return null;
  return (
    <div className="grid sm:grid-cols-2 gap-2 mt-3">
      <div className="rounded-lg bg-ink border border-line p-3">
        <div className="text-xs font-bold uppercase text-good mb-1">Covered</div>
        <ul className="text-sm text-muted list-disc pl-4 space-y-0.5">
          {scope.covered.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      </div>
      <div className="rounded-lg bg-ink border border-line p-3">
        <div className="text-xs font-bold uppercase text-faint mb-1">Not covered</div>
        <ul className="text-sm text-muted list-disc pl-4 space-y-0.5">
          {scope.excluded.map(([label, ref], i) => (
            <li key={i}>{label} <span className="text-faint">→ {ref}</span></li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
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
    setSubject("");
    setNotes("");
    setErr("");
  }, [template]);
  // Local estimate of the score (mirrors backend logic) for instant feedback.
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
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="font-semibold">Evaluate — {template.name}</h3>
        <div className="text-sm text-muted">
          Estimate: {" "}
          <span className="font-bold" style={{ color: GRADE_COLOR[estGrade] }}>
            {estimate} / 100 · {estGrade}
          </span>
        </div>
      </div>

      <input
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject being evaluated (e.g. Onboarding process, Payment API, Acme Customer…)"
        className="w-full mt-3 bg-ink border border-line rounded-lg px-3 py-2 text-sm outline-none focus:border-acc"
      />

      <div className="mt-4 space-y-4">
        {template.criteria.map((c) => (
          <div key={c.id}>
            <div className="flex justify-between text-sm">
              <span className="font-medium">{c.label}</span>
              <span className="text-muted">{scores[c.id] ?? 0} / {c.max}
                <span className="text-faint"> · weight {c.weight}</span></span>
            </div>
            <input
              type="range" min={0} max={c.max} value={scores[c.id] ?? 0}
              onChange={(e) => setScores({ ...scores, [c.id]: Number(e.target.value) })}
              className="w-full mt-1"
            />
            <p className="text-xs text-faint mt-0.5">{c.detail}</p>
          </div>
        ))}
      </div>

      <textarea
        value={notes} onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes (optional)" rows={2}
        className="w-full mt-4 bg-ink border border-line rounded-lg px-3 py-2 text-sm outline-none focus:border-acc"
      />

      <ScopeBlocks scope={template.scope} />

      {err && <p className="text-bad text-sm mt-3">{err}</p>}

      <button
        onClick={submit} disabled={busy}
        className="mt-4 inline-flex items-center gap-2 bg-acc hover:brightness-110 disabled:opacity-50 text-white font-semibold rounded-lg px-4 py-2 text-sm"
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : <ClipboardList size={16} />}
        Create ticket
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
function TicketCard({ t, onDelete }) {
  const color = GRADE_COLOR[t.grade] || "#5b8cff";
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-faint">{t.template_name} · {new Date(t.created_at).toLocaleString()}</div>
          <div className="font-semibold">{t.subject}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold leading-none" style={{ color }}>{t.grade}</div>
          <div className="text-xs text-muted">{t.score} / 100</div>
        </div>
      </div>

      <div className="mt-3 space-y-1">
        {t.details.map((d) => (
          <div key={d.id} className="flex items-center gap-2 text-xs">
            <span className="w-40 truncate text-muted">{d.label}</span>
            <div className="flex-1 h-1.5 rounded bg-ink overflow-hidden">
              <div className="h-full" style={{ width: `${d.contribution}%`, background: color }} />
            </div>
            <span className="text-faint w-14 text-right">{d.value}/{d.max}</span>
          </div>
        ))}
      </div>

      <div className="flex gap-2 mt-3">
        <a href={api.exportUrl(t.id, "pdf")} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:bg-panel2">
          <FileText size={14} /> PDF
        </a>
        <a href={api.exportUrl(t.id, "json")} target="_blank" rel="noreferrer"
           className="inline-flex items-center gap-1 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:bg-panel2">
          <FileJson size={14} /> JSON
        </a>
        <button onClick={() => onDelete(t.id)}
           className="inline-flex items-center gap-1 text-xs border border-line rounded-lg px-2.5 py-1.5 hover:bg-panel2 text-bad ml-auto">
          <Trash2 size={14} /> Delete
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
function Chatbot({ tickets }) {
  const [msgs, setMsgs] = useState([
    { role: "assistant", content: "Ask a question about your evaluations — e.g. 'which subject has the lowest grade?'" },
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
      // On envoie l'historique sans le message d'accueil initial (index 0).
      const history = next.slice(1).map((m) => ({ role: m.role, content: m.content }));
      const res = await api.chat(history);
      setMsgs([...next, { role: "assistant", content: res.reply, model: res.model }]);
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: "Error: " + e.message }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="rounded-xl border border-line bg-panel flex flex-col h-[460px]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
        <Bot size={18} className="text-acc2" />
        <span className="font-semibold">Assistant</span>
        <span className="text-xs text-faint ml-auto">{tickets.length} ticket(s) in context</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
              m.role === "user" ? "bg-acc text-white" : "bg-panel2 border border-line text-muted"}`}>
              {m.content}
              {m.model && <div className="text-[10px] text-faint mt-1">model: {m.model}</div>}
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-faint flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="p-3 border-t border-line flex gap-2">
        <input
          value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Your question…"
          className="flex-1 bg-ink border border-line rounded-lg px-3 py-2 text-sm outline-none focus:border-acc"
        />
        <button onClick={send} disabled={busy}
          className="bg-acc2 text-ink font-semibold rounded-lg px-3 disabled:opacity-50">
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
const ENDPOINTS = [
  ["GET", "/api/v1/templates", "List templates with criteria + scope"],
  ["POST", "/api/v1/evaluations", "Create an evaluation → ticket (score + grade)"],
  ["GET", "/api/v1/tickets", "List tickets"],
  ["GET", "/api/v1/tickets/{id}/export?format=pdf|json|html", "Export a ticket"],
  ["POST", "/api/v1/chat", "Ask the chatbot (local model)"],
  ["GET", "/api/v1/health", "API health check"],
];

function ApiPanel({ health }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center gap-2">
        <Plug size={18} className="text-acc" />
            <span className="font-semibold">REST API</span>
        <a href="/docs" target="_blank" rel="noreferrer" className="text-xs text-acc ml-auto hover:underline">Swagger /docs →</a>
      </div>
      <div className="mt-2 text-xs flex items-center gap-2">
            {health === "ok" ? <CheckCircle2 size={14} className="text-good" /> : <XCircle size={14} className="text-bad" />}
            <span className="text-muted">{health === "ok" ? "Backend connected" : "Backend unreachable (start the API)"}</span>
      </div>
      <div className="mt-3 space-y-1.5">
        {ENDPOINTS.map(([m, p, d]) => (
          <div key={p} className="flex items-center gap-2 bg-ink border border-line rounded-lg px-2.5 py-2 font-mono text-xs">
            <span className={`font-bold px-1.5 py-0.5 rounded ${m === "GET" ? "text-good" : "text-acc"}`}>{m}</span>
            <span className="text-[#cdd7ee] truncate">{p}</span>
            <span className="ml-auto text-muted font-sans hidden md:block">{d}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================== */
export default function App() {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState("?");
  const [loadErr, setLoadErr] = useState("");

  function handleUploadTemplate(tpl) {
    setTemplates((prev) => (prev.find((p) => p.id === tpl.id) ? prev : [tpl, ...prev]));
    setSelected(tpl);
  }

  async function refreshTickets() {
    try { setTickets(await api.tickets()); } catch {}
  }

  useEffect(() => {
    api.templates().then((t) => { setTemplates(t); setSelected(t[0]); })
      .catch((e) => setLoadErr(e.message));
    api.health().then(() => setHealth("ok")).catch(() => setHealth("ko"));
    refreshTickets();
  }, []);

  function onCreated(ticket) { setTickets((prev) => [ticket, ...prev]); }
  async function onDelete(id) {
    await api.deleteTicket(id).catch(() => {});
    setTickets((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-line">
        <div className="max-w-6xl mx-auto px-5 py-5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg grid place-items-center bg-panel2 border border-line2 text-acc2 font-extrabold">T</div>
          <div>
            <div className="font-extrabold leading-tight">Tool</div>
            <div className="text-xs text-muted">Generic evaluation platform</div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-5 py-6 grid lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <UploadTemplate onUpload={handleUploadTemplate} />
          {loadErr && (
            <div className="rounded-xl border border-bad/40 bg-bad/10 text-bad text-sm p-3">
              Unable to load templates: {loadErr}. Start the backend (port 8000).
            </div>
          )}
          {templates.length > 0 && (
            <>
              <TemplatePicker templates={templates} selected={selected} onSelect={setSelected} />
              {selected && <EvalForm template={selected} onCreated={onCreated} />}
            </>
          )}

          <div>
            <h2 className="font-semibold mb-2">Tickets ({tickets.length})</h2>
            {tickets.length === 0 ? (
              <p className="text-sm text-faint">No tickets. Run an evaluation above.</p>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {tickets.map((t) => <TicketCard key={t.id} t={t} onDelete={onDelete} />)}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <Chatbot tickets={tickets} />
          <ApiPanel health={health} />
        </div>
      </main>

      <footer className="max-w-6xl mx-auto px-5 py-8 text-xs text-faint">
        Tool · process/system/sentiment evaluation · weighted scoring → grade · PDF/JSON export · local open-source chatbot.
      </footer>
    </div>
  );
}
