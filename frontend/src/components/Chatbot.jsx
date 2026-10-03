import { useEffect, useRef, useState } from "react";
import { Bot, Send } from "lucide-react";
import { api } from "../api.js";

const GREETING = {
  role: "assistant",
  content: "Ask a question about your evaluations, e.g. \"Which subject has the lowest grade?\"",
};

export default function Chatbot({ tickets }) {
  const [msgs, setMsgs] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ block: "nearest" }); }, [msgs, busy]);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;
    const next = [...msgs, { role: "user", content: q }];
    setMsgs(next); setInput(""); setBusy(true);
    try {
      // The greeting is UI-only; the API accepts just user/assistant turns.
      const history = next.slice(1).slice(-20).map(({ role, content }) => ({ role, content }));
      const res = await api.chat(history);
      setMsgs([...next, { role: "assistant", content: res.reply, model: res.model }]);
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: `Error: ${e.message}`, error: true }]);
    } finally { setBusy(false); }
  }

  return (
    <section className="card flex flex-col" style={{ height: 460 }} aria-label="Assistant">
      <div className="flex items-center gap-2 pb-3 mb-3 border-b border-line">
        <div className="w-7 h-7 rounded-lg grid place-items-center bg-acc2/10">
          <Bot size={15} className="text-acc2" />
        </div>
        <h3 className="font-semibold text-sm">Assistant</h3>
        <span className="ml-auto text-xs text-faint">
          {tickets.length} ticket{tickets.length !== 1 ? "s" : ""} in context
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1" role="log" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === "user"
                ? "bg-acc text-white rounded-br-sm"
                : `bg-panel2 border rounded-bl-sm ${m.error ? "border-bad/50 text-bad" : "border-line text-muted"}`
            }`}>
              {m.content}
              {m.model && <div className="text-[11px] mt-1 text-faint">model: {m.model}</div>}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start" aria-label="Assistant is typing">
            <div className="bg-panel2 border border-line rounded-2xl rounded-bl-sm px-3.5 py-2.5 flex gap-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-1.5 h-1.5 rounded-full bg-faint animate-pulse"
                     style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="flex gap-2 mt-3 pt-3 border-t border-line"
            onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000}
               placeholder="Ask about your tickets…" aria-label="Message" className="input" />
        <button type="submit" disabled={busy || !input.trim()} aria-label="Send"
                className="btn btn-primary shrink-0" style={{ width: 40, padding: 0 }}>
          <Send size={14} />
        </button>
      </form>
    </section>
  );
}
