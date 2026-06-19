"""FastAPI entry point.

Start with:  uvicorn app.main:app --reload
Auto Swagger docs at /docs, ReDoc at /redoc.
"""

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import templates, evaluations, tickets, chat


def require_api_key(x_api_key: str | None = Header(default=None)):
    """Optional guard: active only when API_KEY is set."""
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(401, "Invalid or missing API key (header X-Api-Key).")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Generic evaluation platform API. Three built-in templates "
        "(process, system, customer sentiment): weighted criteria → score → grade. "
        "Tickets exportable as PDF/JSON, REST API for integration, "
        "chatbot backed by a local open-source model."
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


@app.get("/api/v1/health", tags=["system"], summary="Health check")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.VERSION,
            "model": settings.OLLAMA_MODEL}
