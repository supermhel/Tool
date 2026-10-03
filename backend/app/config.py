"""Configuration via environment variables (12-factor)."""

import os


def _csv(name: str, default: str = "") -> list[str]:
    return [p.strip() for p in os.getenv(name, default).split(",") if p.strip()]


class Settings:
    APP_NAME = "Tool — evaluation API"
    VERSION = "2.0.0"

    # CORS: allowed origins. "*" is for development only.
    CORS_ORIGINS = _csv("CORS_ORIGINS", "*") or ["*"]

    # Ollama (local open-source model)
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

    # Auth. API_KEYS="key1:org-a[:label],key2:org-b". Legacy API_KEY maps to org "default".
    # Neither set => open dev mode, everything lives in org "default".
    API_KEY = os.getenv("API_KEY", "")
    API_KEYS = os.getenv("API_KEYS", "")

    # Score proposer used by the tender workbench: "rules" (offline) or "ollama".
    PROPOSER = os.getenv("PROPOSER", "rules")

    # Requests per minute per caller for the expensive endpoints (chat, propose). 0 = off.
    RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))


settings = Settings()
