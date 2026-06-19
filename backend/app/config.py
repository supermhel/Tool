"""Configuration via variables d'environnement (12-factor)."""

import os


class Settings:
    APP_NAME = "Tool — API d'évaluation"
    VERSION = "1.0.0"

    # CORS : origines autorisées (frontend). "*" en dev uniquement.
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # Ollama (modèle open source local)
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

    # Clé API simple pour protéger les endpoints (laisser vide = désactivé en dev)
    API_KEY = os.getenv("API_KEY", "")


settings = Settings()
