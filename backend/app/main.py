"""Point d'entrée FastAPI.

Lance avec :  uvicorn app.main:app --reload
Documentation Swagger auto sur /docs , ReDoc sur /redoc.
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import templates, evaluations, tickets, chat


def require_api_key(x_api_key: str | None = Header(default=None)):
    """Garde optionnelle : active uniquement si API_KEY est défini."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(401, "Clé API invalide ou manquante (header X-API-Key).")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "API d'une plateforme d'évaluation générique. Trois templates "
        "(processus, système, sentiment client) : critères pondérés → score → grade. "
        "Tickets exportables en PDF/JSON et chatbot branché sur un modèle open source local."
    ),
    dependencies=[Depends(require_api_key)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(templates.router)
app.include_router(evaluations.router)
app.include_router(tickets.router)
app.include_router(chat.router)


@app.get("/api/v1/health", tags=["système"], summary="Vérification de disponibilité")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION,
            "model": settings.OLLAMA_MODEL}
