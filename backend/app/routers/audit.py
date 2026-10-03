from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from .. import repo
from ..auth import Caller, get_caller

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

_FIELDS = ("id", "created_at", "actor", "action", "entity", "entity_id", "detail",
           "prev_hash", "hash")


def _public(e: dict) -> dict:
    return {k: e.get(k) for k in _FIELDS}


@router.get("", summary="Audit log, newest first")
def list_audit(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               caller: Caller = Depends(get_caller)):
    return [_public(e) for e in repo.audit_log.list(caller.org, limit, offset)]


@router.get("/verify", summary="Verify the integrity of the audit hash chain")
def verify(caller: Caller = Depends(get_caller)):
    return repo.audit_log.verify(caller.org)


@router.get("/export", summary="Download the full audit log (oldest first) as JSON")
def export(caller: Caller = Depends(get_caller)):
    entries, page = [], 0
    while True:
        batch = repo.get_store().list("audit", caller.org, limit=500, offset=page * 500,
                                      oldest_first=True)
        if not batch:
            break
        entries.extend(_public(e) for e in batch)
        page += 1
    return JSONResponse(
        {"org": caller.org, "verification": repo.audit_log.verify(caller.org), "entries": entries},
        headers={"Content-Disposition": 'attachment; filename="audit-log.json"'},
    )
