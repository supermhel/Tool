from fastapi import APIRouter, HTTPException

from ..templates_data import list_templates, get_template

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.get("", summary="Liste les templates d'évaluation")
def get_templates():
    """Retourne les 3 templates avec leurs critères, descriptions et périmètre
    (couvert / non couvert)."""
    return list_templates()


@router.get("/{template_id}", summary="Détail d'un template")
def get_one(template_id: str):
    tpl = get_template(template_id)
    if tpl is None:
        raise HTTPException(404, f"Template inconnu : {template_id}")
    return tpl
