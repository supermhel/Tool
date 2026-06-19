import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from ..models import Ticket
from ..pdf import render_ticket_html
from ..storage import store

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


@router.get("", response_model=list[Ticket], summary="Liste tous les tickets")
def list_tickets():
    return store.list()


@router.get("/{ticket_id}", response_model=Ticket, summary="Détail d'un ticket")
def get_ticket(ticket_id: str):
    t = store.get(ticket_id)
    if t is None:
        raise HTTPException(404, "Ticket introuvable")
    return t


@router.delete("/{ticket_id}", summary="Supprime un ticket")
def delete_ticket(ticket_id: str):
    if not store.delete(ticket_id):
        raise HTTPException(404, "Ticket introuvable")
    return {"deleted": ticket_id}


@router.get("/{ticket_id}/export", summary="Exporte un ticket (json | pdf | html)")
def export_ticket(
    ticket_id: str,
    format: str = Query("json", pattern="^(json|pdf|html)$",
                        description="Format d'export"),
):
    t = store.get(ticket_id)
    if t is None:
        raise HTTPException(404, "Ticket introuvable")

    if format == "json":
        body = json.dumps(t, ensure_ascii=False, indent=2)
        return JSONResponse(
            content=t,
            headers={"Content-Disposition": f'attachment; filename="ticket-{ticket_id}.json"'},
        )

    if format == "html":
        return HTMLResponse(render_ticket_html(t))

    # format == "pdf": serve printable HTML — browser print dialog saves as PDF
    return HTMLResponse(render_ticket_html(t, auto_print=True))
