"""FastAPI entry point.

Start with:  uvicorn app.main:app --reload
Auto Swagger docs at /docs, ReDoc at /redoc.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import Caller, auth_enabled, get_caller
from .config import settings
from .routers import audit, chat, evaluations, sensitivity, templates, tenders, tickets

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Weighted-criteria evaluation platform. Built-in and custom (versioned) templates "
        "→ score → grade, tamper-evident tickets, a tender evaluation workbench "
        "(blind multi-evaluator scoring, consensus, weight-sensitivity analysis, award "
        "reports), an audit log, and a chatbot over your tickets. All data is scoped to "
        "the organisation behind your API key (header X-API-Key)."
    ),
)

# Credentials are never used (auth is a header, not a cookie), so wildcard origins are safe to allow.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (templates, evaluations, tickets, chat, tenders, sensitivity, audit):
    app.include_router(module.router)


@app.get("/api/v1/health", tags=["system"], summary="Health check")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION,
            "model": settings.OLLAMA_MODEL, "auth": auth_enabled()}


@app.get("/api/v1/me", tags=["system"], summary="Who am I? (organisation and label of the calling key)")
def me(caller: Caller = Depends(get_caller)):
    """With auth on, `label` is the evaluator name this key may score as."""
    return {"org": caller.org, "label": caller.label, "auth": auth_enabled()}
