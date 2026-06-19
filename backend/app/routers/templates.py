from fastapi import APIRouter, HTTPException

from ..templates_data import list_templates, get_template

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("", summary="List evaluation templates")
def get_templates():
    """Return all templates with their criteria, descriptions, and scope (covered / not covered)."""
    return list_templates()


@router.get("/{template_id}", summary="Get a single template")
def get_one(template_id: str):
    tpl = get_template(template_id)
    if tpl is None:
        raise HTTPException(404, f"Unknown template: {template_id}")
    return tpl
