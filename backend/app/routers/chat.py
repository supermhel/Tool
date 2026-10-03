from fastapi import APIRouter, Depends

from .. import repo
from ..auth import Caller
from ..models import ChatRequest, ChatResponse
from ..ollama_client import build_context, chat
from ..ratelimit import rate_limited

router = APIRouter(prefix="/api/v1/chat", tags=["chatbot"])


@router.post("", response_model=ChatResponse,
             summary="Ask a natural-language question about evaluations")
async def post_chat(req: ChatRequest, caller: Caller = Depends(rate_limited)):
    """The chatbot uses ticket context from the caller's organisation only. If
    `ticket_id` is provided the context is restricted to that ticket; otherwise it
    covers the 20 most recent tickets. Only `user` and `assistant` roles are accepted."""
    if req.ticket_id:
        t = repo.tickets.get(caller.org, req.ticket_id)
        tickets = [t] if t else []
    else:
        tickets = repo.tickets.list(caller.org, limit=20)

    context = build_context(tickets)
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    reply, model = await chat(messages, context, tickets)

    return ChatResponse(
        reply=reply,
        model=model,
        grounded_on=[t["id"] for t in tickets if t],
    )
