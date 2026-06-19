"""Ollama client for the chatbot.

Sends ticket context to a local Ollama model. When Ollama is unreachable the
chat function falls back to a deterministic rule-based responder so the app
stays usable without any model infrastructure.
"""

import httpx

from .config import settings
from typing import Optional, List

SYSTEM_PROMPT = (
    "You are an assistant for an evaluation platform. Answer concisely and factually. "
    "Base your answers ONLY on the evaluation ticket context provided. If information "
    "is not in the context, say so. Cite criteria and scope when relevant. "
    "Never invent numbers."
)


def build_context(tickets: list[dict]) -> str:
    if not tickets:
        return "No evaluations recorded yet."
    lines = []
    for t in tickets[:20]:
        crit = ", ".join(
            f"{d['label']}={d['value']}/{d['max']}" for d in t.get("details", [])
        )
        lines.append(
            f"- Ticket {t['id']} | {t['template_name']} | subject: {t['subject']} | "
            f"score {t['score']}/100 (grade {t['grade']} – {t['grade_label']}) | "
            f"criteria: {crit}"
        )
    return "Available evaluation tickets:\n" + "\n".join(lines)


def _simple_fallback_answer(messages: list[dict], tickets: Optional[List[dict]]) -> str:
    """Rule-based answers from ticket data when the model is unavailable."""
    if not tickets:
        return "No evaluations available to answer this question."

    last_user = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "").lower()
            break
    if not last_user:
        return build_context(tickets)

    if "lowest" in last_user:
        t = min(tickets, key=lambda x: x.get("score", 0))
        return f"Lowest score: {t['subject']} (ticket {t['id']}) — {t.get('score', '?')} / 100, grade {t.get('grade','?')}"
    if "highest" in last_user:
        t = max(tickets, key=lambda x: x.get("score", 0))
        return f"Highest score: {t['subject']} (ticket {t['id']}) — {t.get('score', '?')} / 100, grade {t.get('grade','?')}"

    if "average" in last_user or "mean" in last_user:
        vals = [t.get("score", 0) for t in tickets]
        avg = sum(vals) / len(vals) if vals else 0
        return f"Average score across {len(vals)} tickets: {round(avg,1)} / 100"

    if "list" in last_user or "tickets" in last_user:
        lines = []
        for t in tickets[:10]:
            lines.append(f"- {t['id']}: {t['subject']} — {t.get('score','?')}/100 ({t.get('grade','?')})")
        return "Tickets:\n" + "\n".join(lines)

    for t in tickets:
        if str(t.get('id')) in last_user or (t.get('subject') and t['subject'].lower() in last_user):
            details = ", ".join(f"{d['label']}={d['value']}/{d['max']}" for d in t.get('details', []))
            return f"Ticket {t['id']} — {t['subject']}: score {t.get('score','?')} /100, grade {t.get('grade','?')}. Details: {details}"

    return build_context(tickets)


async def chat(messages: list[dict], context: str, tickets: Optional[List[dict]] = None) -> tuple[str, str]:
    """Return (reply, model_used)."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "CONTEXT\n" + context},
            *messages,
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
            r = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            reply = data.get("message", {}).get("content", "").strip()
            return reply or "(empty model response)", settings.OLLAMA_MODEL
    except Exception as exc:  # noqa: BLE001
        try:
            answer = _simple_fallback_answer(messages, tickets)
            return answer + "\n\n(software fallback: model unavailable)", "fallback"
        except Exception:
            return (
                f"⚠️ Local model (Ollama) is unreachable. "
                f"Make sure Ollama is running and the model is downloaded "
                f"(`ollama pull {settings.OLLAMA_MODEL}`). "
                f"Technical detail: {type(exc).__name__}.\n\n"
                "Here is the evaluation context anyway:\n" + context
            ), "fallback"
