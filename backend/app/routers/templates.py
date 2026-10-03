from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from .. import repo
from ..auth import Caller, get_caller
from ..importers import ImportError_, parse_template
from ..models import TemplateImport, TemplateIn

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


def _save(caller: Caller, raw: dict) -> dict:
    try:
        data = TemplateIn(**raw).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()])
    try:
        tpl = repo.templates.save(caller.org, data)
    except repo.TemplateConflict as exc:
        raise HTTPException(409, str(exc))
    repo.record(caller, "template.save", "template", tpl["id"], {"version": tpl["version"]})
    return tpl


@router.get("", summary="List built-in and custom templates (latest versions)")
def list_templates(caller: Caller = Depends(get_caller)):
    """Templates with criteria, descriptions and scope (covered / not covered)."""
    return repo.templates.list(caller.org)


@router.post("", status_code=201, summary="Create a custom template, or add a new version")
def create_template(body: TemplateIn, caller: Caller = Depends(get_caller)):
    """Posting an existing custom id creates the next version. Older versions stay
    readable, and tickets pin the version they were scored against."""
    return _save(caller, body.model_dump())


@router.post("/import", status_code=201, summary="Import a template from JSON, YAML or CSV text")
def import_template(body: TemplateImport, caller: Caller = Depends(get_caller)):
    try:
        raw = parse_template(body.filename, body.content)
    except ImportError_ as exc:
        raise HTTPException(422, str(exc))
    return _save(caller, raw)


@router.get("/{template_id}", summary="Get a template (latest version unless ?version=)")
def get_one(template_id: str, version: int | None = Query(None, ge=1),
            caller: Caller = Depends(get_caller)):
    tpl = repo.templates.get(caller.org, template_id, version)
    if tpl is None:
        raise HTTPException(404, f"Unknown template: {template_id}")
    return tpl


@router.get("/{template_id}/versions", summary="All versions of a template")
def versions(template_id: str, caller: Caller = Depends(get_caller)):
    out = repo.templates.versions(caller.org, template_id)
    if not out:
        raise HTTPException(404, f"Unknown template: {template_id}")
    return out


@router.delete("/{template_id}", summary="Delete a custom template (all versions)")
def delete_template(template_id: str, caller: Caller = Depends(get_caller)):
    try:
        ok = repo.templates.delete(caller.org, template_id)
    except repo.TemplateConflict as exc:
        raise HTTPException(409, str(exc))
    if not ok:
        raise HTTPException(404, f"Unknown template: {template_id}")
    repo.record(caller, "template.delete", "template", template_id)
    return {"deleted": template_id}
