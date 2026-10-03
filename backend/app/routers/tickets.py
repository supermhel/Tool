from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from .. import repo
from ..auth import Caller, get_caller
from ..models import Ticket
from ..pdf import render_ticket_html

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=list[Ticket], summary="List tickets, newest first")
def list_tickets(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                 caller: Caller = Depends(get_caller)):
    return repo.tickets.list(caller.org, limit, offset)


@router.get("/verify", summary="Verify the integrity of the ticket hash chain")
def verify_chain(caller: Caller = Depends(get_caller)):
    """Recomputes every ticket hash. `ok: false` means a ticket was altered, removed
    or reordered after it was written."""
    return repo.tickets.verify(caller.org)


@router.get("/{ticket_id}", response_model=Ticket, summary="Ticket detail")
def get_ticket(ticket_id: str, caller: Caller = Depends(get_caller)):
    t = repo.tickets.get(caller.org, ticket_id)
    if t is None:
        raise HTTPException(404, "Ticket not found")
    return t


@router.delete("/{ticket_id}", summary="Hide a ticket (soft delete; the record stays in the chain)")
def delete_ticket(ticket_id: str, caller: Caller = Depends(get_caller)):
    if not repo.tickets.soft_delete(caller.org, ticket_id):
        raise HTTPException(404, "Ticket not found")
    repo.record(caller, "ticket.delete", "ticket", ticket_id)
    return {"deleted": ticket_id}


@router.get("/{ticket_id}/export", summary="Export a ticket (json | pdf | html)")
def export_ticket(
    ticket_id: str,
    format: str = Query("json", pattern="^(json|pdf|html)$", description="Export format"),
    caller: Caller = Depends(get_caller),
):
    raw = repo.tickets.get(caller.org, ticket_id)
    if raw is None:
        raise HTTPException(404, "Ticket not found")
    t = Ticket(**raw).model_dump(mode="json")

    if format == "json":
        return JSONResponse(
            content=t,
            headers={"Content-Disposition": f'attachment; filename="ticket-{ticket_id}.json"'},
        )
    if format == "html":
        return HTMLResponse(render_ticket_html(t))
    # format == "pdf": printable HTML — the browser's print dialog saves it as PDF
    return HTMLResponse(render_ticket_html(t, auto_print=True))
