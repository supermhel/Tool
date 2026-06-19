from fastapi import APIRouter

from ..models import ChatRequest, ChatResponse
from ..ollama_client import build_context, chat
from ..storage import store

router = APIRouter(prefix="/api/v1/chat", tags=["chatbot"])


@router.post("", response_model=ChatResponse,
             summary="Pose une question en langage naturel sur les évaluations")
async def post_chat(req: ChatRequest):
    """Le chatbot s'appuie sur le contexte des tickets. Si `ticket_id` est fourni,
    le contexte est restreint à ce ticket ; sinon il porte sur l'ensemble.
    L'inférence est faite par le modèle open source local (Ollama)."""
    if req.ticket_id:
        t = store.get(req.ticket_id)
        tickets = [t] if t else []
    else:
        tickets = store.list()

    context = build_context(tickets)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    # pass the tickets list to the chat client so the fallback can compute answers
    reply, model = await chat(messages, context, tickets)

    return ChatResponse(
        reply=reply,
        model=model,
        grounded_on=[t["id"] for t in tickets if t],
    )
