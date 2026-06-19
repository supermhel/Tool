from fastapi import APIRouter

from ..models import ChatRequest, ChatResponse
from ..ollama_client import build_context, chat
from ..storage import store

router = APIRouter(prefix="/api/v1/chat", tags=["chatbot"])


@router.post("", response_model=ChatResponse,
             summary="Ask a natural-language question about evaluations")
async def post_chat(req: ChatRequest):
    """The chatbot uses ticket context. If `ticket_id` is provided the context
    is restricted to that ticket; otherwise it covers all tickets.
    Inference is handled by the local open-source model (Ollama)."""
    if req.ticket_id:
        t = store.get(req.ticket_id)
        tickets = [t] if t else []
    else:
        tickets = store.list()

    context = build_context(tickets)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    reply, model = await chat(messages, context, tickets)

    return ChatResponse(
        reply=reply,
        model=model,
        grounded_on=[t["id"] for t in tickets if t],
    )
