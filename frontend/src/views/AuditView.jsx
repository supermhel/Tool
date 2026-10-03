import { useCallback, useEffect, useState } from "react";
import { Download, ScrollText, ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "../api.js";
import { Btn, Empty, ErrorNote, SectionTitle, Skeleton } from "../components/ui.jsx";

function describe(e) {
  const d = e.detail || {};
  const bits = Object.entries(d).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
  return bits.join(" · ");
}

export default function AuditView() {
  const [entries, setEntries] = useState(null);
  const [verify, setVerify] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(() => api.audit(200).then(setEntries).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); }, [load]);

  async function run(name, fn) {
    setBusy(name); setErr("");
    try { await fn(); } catch (e) { setErr(e.message); } finally { setBusy(""); }
  }

  return (
    <section className="space-y-4" aria-label="Audit log">
      <SectionTitle aside={
        <div className="flex gap-2">
          <Btn size="sm" icon={ShieldCheck} busy={busy === "v"} onClick={() => run("v", async () => setVerify(await api.verifyAudit()))}>Verify integrity</Btn>
          <Btn size="sm" icon={Download} busy={busy === "x"} onClick={() => run("x", () => api.downloadAudit())}>Export JSON</Btn>
        </div>
      }>Audit log</SectionTitle>

      <p className="text-sm text-muted max-w-prose">
        Every create, score, consensus and award is recorded with who did it. Entries are hash-chained: changing or removing one is detectable.
        Blind scores are never written to the log.
      </p>

      {verify && (
        <p role="status" className={`chip ${verify.ok ? "chip-good" : "chip-bad"}`}>
          {verify.ok
            ? <><ShieldCheck size={12} /> Chain intact · {verify.count} {verify.count === 1 ? "entry" : "entries"}</>
            : <><ShieldAlert size={12} /> Integrity failure at {verify.broken_at || "chain head"}: {verify.reason}</>}
        </p>
      )}
      <ErrorNote>{err}</ErrorNote>

      {entries === null && !err && <Skeleton className="h-40" />}
      {entries?.length === 0 && <Empty icon={ScrollText} title="Nothing recorded yet">Actions appear here as they happen.</Empty>}
      {entries?.length > 0 && (
        <div className="card overflow-x-auto" style={{ padding: 8 }}>
          <table className="data">
            <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="text-muted whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                  <td>{e.actor}</td>
                  <td><span className="chip">{e.action}</span></td>
                  <td className="text-muted">{e.entity} <span className="text-faint">{e.entity_id}</span></td>
                  <td className="text-muted">{describe(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
