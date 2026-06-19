"""Client du modèle open source local (Ollama).

Le chatbot reçoit le contexte des évaluations et répond en français. Si Ollama
n'est pas joignable, on renvoie une réponse de repli ancrée sur les données
locales plutôt que d'échouer — l'outil reste utilisable hors-ligne.
"""

import httpx

from .config import settings
from typing import Optional, List

SYSTEM_PROMPT = (
    "Tu es l'assistant d'une plateforme d'évaluation. Tu réponds en français, "
    "de façon concise et factuelle. Tu t'appuies UNIQUEMENT sur le contexte des "
    "tickets d'évaluation fourni. Si l'information n'y figure pas, dis-le. "
    "Cite les critères et le périmètre quand c'est pertinent. N'invente aucun chiffre."
)


def build_context(tickets: list[dict]) -> str:
    if not tickets:
        return "Aucune évaluation enregistrée pour le moment."
    lines = []
    for t in tickets[:20]:
        crit = ", ".join(
            f"{d['label']}={d['value']}/{d['max']}" for d in t.get("details", [])
        )
        lines.append(
            f"- Ticket {t['id']} | {t['template_name']} | sujet: {t['subject']} | "
            f"score {t['score']}/100 (grade {t['grade']} – {t['grade_label']}) | "
            f"critères: {crit}"
        )
    return "Tickets d'évaluation disponibles :\n" + "\n".join(lines)


def _simple_fallback_answer(messages: list[dict], tickets: Optional[List[dict]]) -> str:
    """Produce a simple rule-based answer from tickets when the model is unavailable.

    Handles a few common questions: lowest/highest grade, average score, list tickets,
    and ticket details. Falls back to returning the ticket context when unsure.
    """
    if not tickets:
        return "No evaluations available to answer this question."

    last_user = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m.get("content", "").lower()
            break
    if not last_user:
        return build_context(tickets)

    # Lowest / highest
    if "lowest" in last_user or "lowest grade" in last_user or "lowest score" in last_user:
        t = min(tickets, key=lambda x: x.get("score", 0))
        return f"Lowest score: {t['subject']} (ticket {t['id']}) — {t.get('score', '?')} / 100, grade {t.get('grade','?')}"
    if "highest" in last_user or "highest grade" in last_user or "highest score" in last_user:
        t = max(tickets, key=lambda x: x.get("score", 0))
        return f"Highest score: {t['subject']} (ticket {t['id']}) — {t.get('score', '?')} / 100, grade {t.get('grade','?')}"

    # Average
    if "average" in last_user or "mean" in last_user or "moyenne" in last_user:
        vals = [t.get("score", 0) for t in tickets]
        avg = sum(vals) / len(vals) if vals else 0
        return f"Average score across {len(vals)} tickets: {round(avg,1)} / 100"

    # List tickets
    if "list" in last_user or "tickets" in last_user:
        lines = []
        for t in tickets[:10]:
            lines.append(f"- {t['id']}: {t['subject']} — {t.get('score','?')}/100 ({t.get('grade','?')})")
        return "Tickets:\n" + "\n".join(lines)

    # Ticket details by id or subject
    for t in tickets:
        if str(t.get('id')) in last_user or (t.get('subject') and t['subject'].lower() in last_user):
            details = ", ".join(f"{d['label']}={d['value']}/{d['max']}" for d in t.get('details', []))
            return f"Ticket {t['id']} — {t['subject']}: score {t.get('score','?')} /100, grade {t.get('grade','?')}. Details: {details}"

    # Fallback: return context
    return build_context(tickets)


async def chat(messages: list[dict], context: str, tickets: Optional[List[dict]] = None) -> tuple[str, str]:
    """Retourne (réponse, modèle_utilisé)."""
    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "CONTEXTE\n" + context},
            *messages,
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
            r = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
            reply = data.get("message", {}).get("content", "").strip()
            return reply or "(réponse vide du modèle)", settings.OLLAMA_MODEL
    except Exception as exc:  # noqa: BLE001 — repli volontaire
        # Try a simple rule-based fallback that answers common questions using ticket data.
        try:
            answer = _simple_fallback_answer(messages, tickets)
            return answer + "\n\n(software fallback: model unavailable)", "fallback"
        except Exception:
            return (
                "⚠️ Le modèle local (Ollama) n'est pas joignable. "
                "Vérifiez qu'Ollama tourne et que le modèle est téléchargé "
                f"(`ollama pull {settings.OLLAMA_MODEL}`). "
                f"Détail technique : {type(exc).__name__}.\n\n"
                "Voici tout de même le contexte des évaluations :\n" + context
            ), "fallback"
