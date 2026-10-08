import { useCallback, useEffect, useState } from "react";
import { Sparkles, KeyRound, Lock, LockOpen } from "lucide-react";
import { api, getKey, setKey } from "./api.js";
import { Btn } from "./components/ui.jsx";
import EvaluateView from "./views/EvaluateView.jsx";
import TendersView from "./views/TendersView.jsx";
import SensitivityView from "./views/SensitivityView.jsx";
import AuditView from "./views/AuditView.jsx";

const TABS = [
  { id: "evaluate", label: "Evaluate" },
  { id: "tenders", label: "Tenders" },
  { id: "sensitivity", label: "Sensitivity" },
  { id: "audit", label: "Audit" },
];

function tabFromHash() {
  const id = window.location.hash.replace("#", "");
  return TABS.some((t) => t.id === id) ? id : "evaluate";
}

function KeyPanel({ onSaved, notice }) {
  const [value, setValue] = useState(getKey());
  return (
    <form className="max-w-6xl mx-auto px-5 pb-4 flex items-end gap-3 flex-wrap"
          onSubmit={(e) => { e.preventDefault(); setKey(value.trim()); onSaved(); }}>
      <div className="flex-1" style={{ minWidth: 240, maxWidth: 420 }}>
        <label className="label" htmlFor="api-key">API key</label>
        <input id="api-key" type="password" autoComplete="off" className="input" value={value}
               onChange={(e) => setValue(e.target.value)} placeholder="X-API-Key for your organisation" />
      </div>
      <Btn type="submit" variant="primary">Save key</Btn>
      <Btn onClick={() => { setValue(""); setKey(""); onSaved(); }}>Clear</Btn>
      <p className={`hint basis-full ${notice ? "text-warn" : ""}`}>
        {notice || "Stored in this browser only. Your key decides which organisation's data you see."}
      </p>
    </form>
  );
}

export default function App() {
  const [tab, setTab] = useState(tabFromHash);
  const [templates, setTemplates] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState(null); // null = unknown, false = unreachable
  const [me, setMe] = useState(null);         // { org, label, auth } for the current key
  const [loadErr, setLoadErr] = useState("");
  const [keyOpen, setKeyOpen] = useState(false);
  const [keyNotice, setKeyNotice] = useState("");

  const reloadTemplates = useCallback(
    () => api.templates().then((t) => { setTemplates(t); setLoadErr(""); }).catch((e) => setLoadErr(e.message)), []);

  const loadAll = useCallback(() => {
    api.health().then(setHealth).catch(() => setHealth(false));
    api.me().then(setMe).catch(() => setMe(null));
    reloadTemplates();
    api.tickets().then(setTickets).catch(() => setTickets([]));
  }, [reloadTemplates]);

  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    const onUnauthorized = () => {
      setKeyNotice(getKey() ? "The server rejected this key." : "This server requires an API key.");
      setKeyOpen(true);
    };
    window.addEventListener("hashchange", onHash);
    window.addEventListener("tool:unauthorized", onUnauthorized);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("tool:unauthorized", onUnauthorized);
    };
  }, []);

  const go = (id) => { window.location.hash = id; setTab(id); };
  const authOn = health && health.auth;

  return (
    <div className="min-h-full">
      <header className="border-b border-line sticky top-0 z-10 backdrop-blur-sm" style={{ background: "rgba(8,11,18,.88)" }}>
        <div className="max-w-6xl mx-auto px-5 pt-4 flex items-center gap-3 flex-wrap">
          <div className="w-9 h-9 rounded-xl grid place-items-center border border-line2"
               style={{ background: "linear-gradient(135deg,#4f7eff22,#34d1b022)" }}>
            <Sparkles size={17} style={{ color: "#4f7eff" }} />
          </div>
          <div>
            <div className="font-extrabold leading-tight tracking-tight">Tool</div>
            <div className="text-[11px] text-faint">Evaluation and tender workbench</div>
          </div>

          <div className="ml-auto flex items-center gap-2 flex-wrap">
            <span className={`chip ${health === false ? "chip-bad" : health ? "chip-good" : ""}`} role="status">
              {health === false ? "API offline" : health ? "API connected" : "Connecting…"}
            </span>
            {health && (
              <span className="chip" title={authOn ? "Data is scoped to your API key's organisation" : "No keys configured: everyone shares one open organisation"}>
                {authOn ? <Lock size={11} /> : <LockOpen size={11} />}{authOn ? "Key required" : "Open mode"}
              </span>
            )}
            <Btn size="sm" icon={KeyRound} aria-expanded={keyOpen} onClick={() => { setKeyNotice(""); setKeyOpen((o) => !o); }}>API key</Btn>
            <a className="btn btn-sm" href="/docs" target="_blank" rel="noreferrer">API docs</a>
          </div>

          <nav className="tabs basis-full -mb-px" role="tablist" aria-label="Sections">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} className="tab" onClick={() => go(t.id)}>{t.label}</button>
            ))}
          </nav>
        </div>
        {keyOpen && <div className="border-t border-line pt-3"><KeyPanel notice={keyNotice} onSaved={() => { setKeyOpen(false); setKeyNotice(""); loadAll(); }} /></div>}
      </header>

      <main className="max-w-6xl mx-auto px-5 py-8">
        {health === false && (
          <div role="alert" className="rounded-2xl border border-bad/30 bg-bad/5 text-bad text-sm px-4 py-3 mb-6">
            The API is unreachable. Start the backend (<code>uvicorn app.main:app</code>) or check the proxy target.
          </div>
        )}
        {tab === "evaluate" && (
          <EvaluateView templates={templates} reloadTemplates={reloadTemplates}
                        tickets={tickets} setTickets={setTickets} loadErr={loadErr} />
        )}
        {tab === "tenders" && <TendersView key={me ? `${me.org}:${me.label}` : "anon"} templates={templates} me={me} />}
        {tab === "sensitivity" && <SensitivityView />}
        {tab === "audit" && <AuditView />}
      </main>

      <footer className="max-w-6xl mx-auto px-5 py-6 border-t border-line mt-4">
        <p className="text-xs text-faint text-center">
          Weighted scoring · blind multi-evaluator tenders · weight-sensitivity analysis · tamper-evident records
        </p>
      </footer>
    </div>
  );
}
