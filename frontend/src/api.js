// Couche d'accès à l'API REST. Le base path "/api/v1" est proxifié vers le
// backend FastAPI (voir vite.config.js).
const BASE = (import.meta.env.VITE_API_BASE || "") + "/api/v1";
const API_KEY = import.meta.env.VITE_API_KEY || "";

function headers() {
  const h = { "Content-Type": "application/json" };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

async function handle(res) {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  templates: () => fetch(`${BASE}/templates`, { headers: headers() }).then(handle),

  evaluate: (payload) =>
    fetch(`${BASE}/evaluations`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload),
    }).then(handle),

  tickets: () => fetch(`${BASE}/tickets`, { headers: headers() }).then(handle),

  deleteTicket: (id) =>
    fetch(`${BASE}/tickets/${id}`, { method: "DELETE", headers: headers() }).then(handle),

  exportUrl: (id, format) => `${BASE}/tickets/${id}/export?format=${format}`,

  chat: (messages, ticketId) =>
    fetch(`${BASE}/chat`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ messages, ticket_id: ticketId || null }),
    }).then(handle),

  health: () => fetch(`${BASE}/health`, { headers: headers() }).then(handle),
};
