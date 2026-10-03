// REST access layer. "/api/v1" is proxied to the FastAPI backend (see vite.config.js).
const BASE = (import.meta.env.VITE_API_BASE || "") + "/api/v1";
const KEY_STORE = "tool.apiKey";

export function getKey() {
  try { return localStorage.getItem(KEY_STORE) || import.meta.env.VITE_API_KEY || ""; }
  catch { return import.meta.env.VITE_API_KEY || ""; }
}

export function setKey(key) {
  try {
    if (key) localStorage.setItem(KEY_STORE, key);
    else localStorage.removeItem(KEY_STORE);
  } catch { /* storage unavailable: the key then lasts only until reload via env */ }
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

function headers(json = true) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const key = getKey();
  if (key) h["X-API-Key"] = key;
  return h;
}

// FastAPI returns `detail` as a string, or a list of {loc, msg} for validation errors.
function explain(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const where = Array.isArray(d.loc) ? d.loc.filter((p) => p !== "body").join(".") : "";
      return where ? `${where}: ${d.msg}` : d.msg;
    }).join("; ");
  }
  return fallback;
}

async function fail(res) {
  let msg = res.statusText || `HTTP ${res.status}`;
  try { msg = explain((await res.json()).detail, msg); } catch { /* non-JSON error body */ }
  if (res.status === 401) window.dispatchEvent(new Event("tool:unauthorized"));
  throw new ApiError(msg, res.status);
}

async function request(path, { method = "GET", body } = {}) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) await fail(res);
  return res.json();
}

async function fetchBlob(path) {
  const res = await fetch(`${BASE}${path}`, { headers: headers(false) });
  if (!res.ok) await fail(res);
  return res.blob();
}

/** Open an HTML endpoint (report, ticket PDF…) in a new tab. A plain link cannot
 *  carry the X-API-Key header, so the page is fetched and shown from a blob URL. */
export async function openDocument(path) {
  const tab = window.open("", "_blank"); // opened synchronously so popup blockers allow it
  try {
    const html = await (await fetchBlob(path)).text();
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    if (tab) tab.location.href = url;
    else window.location.href = url;
  } catch (e) {
    tab?.close();
    throw e;
  }
}

export async function download(path, filename) {
  const url = URL.createObjectURL(await fetchBlob(path));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const enc = encodeURIComponent;

export const api = {
  health: () => request("/health"),
  me: () => request("/me"),

  templates: () => request("/templates"),
  createTemplate: (t) => request("/templates", { method: "POST", body: t }),
  importTemplate: (filename, content) =>
    request("/templates/import", { method: "POST", body: { filename, content } }),
  deleteTemplate: (id) => request(`/templates/${enc(id)}`, { method: "DELETE" }),

  evaluate: (payload) => request("/evaluations", { method: "POST", body: payload }),
  tickets: (limit = 100) => request(`/tickets?limit=${limit}`),
  verifyTickets: () => request("/tickets/verify"),
  deleteTicket: (id) => request(`/tickets/${enc(id)}`, { method: "DELETE" }),
  openTicket: (id, format) => openDocument(`/tickets/${enc(id)}/export?format=${format}`),
  downloadTicket: (id) => download(`/tickets/${enc(id)}/export?format=json`, `ticket-${id}.json`),

  chat: (messages, ticketId) =>
    request("/chat", { method: "POST", body: { messages, ticket_id: ticketId || null } }),

  tenders: () => request("/tenders"),
  createTender: (t) => request("/tenders", { method: "POST", body: t }),
  tender: (id) => request(`/tenders/${enc(id)}`),
  submitScore: (id, s) => request(`/tenders/${enc(id)}/scores`, { method: "POST", body: s }),
  closeScoring: (id) => request(`/tenders/${enc(id)}/close-scoring`, { method: "POST" }),
  tenderResults: (id) => request(`/tenders/${enc(id)}/results`),
  setConsensus: (id, c) => request(`/tenders/${enc(id)}/consensus`, { method: "PUT", body: c }),
  award: (id) => request(`/tenders/${enc(id)}/award`, { method: "POST" }),
  tenderSensitivity: (id, delta) => request(`/tenders/${enc(id)}/sensitivity?delta=${delta}`),
  propose: (id, bidder_id, document_text) =>
    request(`/tenders/${enc(id)}/propose`, { method: "POST", body: { bidder_id, document_text } }),
  openReport: (id, format = "pdf") => openDocument(`/tenders/${enc(id)}/report?format=${format}`),
  openDebrief: (id, bidder, format = "pdf") =>
    openDocument(`/tenders/${enc(id)}/debrief/${enc(bidder)}?format=${format}`),

  sensitivity: (body) => request("/sensitivity", { method: "POST", body }),

  audit: (limit = 100) => request(`/audit?limit=${limit}`),
  verifyAudit: () => request("/audit/verify"),
  downloadAudit: () => download("/audit/export", "audit-log.json"),
};
