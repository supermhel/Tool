"""Vercel serverless entry point for the FastAPI backend.

Vercel Python runtime expects a module-level `app` (ASGI) or a `handler`
function. We re-export the FastAPI app from the existing backend package.
The SQLite file goes to /tmp because Vercel's filesystem is read-only elsewhere;
it is ephemeral per instance. Enable the KV integration (Upstash) for real
persistence, and set API_KEYS: without it everyone shares one open organisation.
"""

import os
import sys

# Make sure the backend package is importable when running under Vercel.
# Vercel runs from the repo root, so we add the backend directory to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Use /tmp for writable ephemeral storage on Vercel
os.environ.setdefault("DB_PATH", "/tmp/tool.db")

# Override CORS to accept everything in this deployment
os.environ.setdefault("CORS_ORIGINS", "*")

from app.main import app  # noqa: E402  (import after sys.path manipulation)

# Vercel looks for `app` at module level (ASGI)
__all__ = ["app"]
