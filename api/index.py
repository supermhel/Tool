"""Vercel serverless entry point for the FastAPI backend.

Vercel Python runtime expects a module-level `app` (ASGI) or a `handler`
function. We re-export the FastAPI app from the existing backend package.
The DATA_DIR is set to /tmp so Vercel's read-only filesystem doesn't block
writes (data is ephemeral per cold-start, which is acceptable for a demo).
"""

import os
import sys

# Make sure the backend package is importable when running under Vercel.
# Vercel runs from the repo root, so we add the backend directory to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Use /tmp for writable ephemeral storage on Vercel
os.environ.setdefault("DATA_DIR", "/tmp/tool_data")

# Override CORS to accept everything in this deployment
os.environ.setdefault("CORS_ORIGINS", "*")

from app.main import app  # noqa: E402  (import after sys.path manipulation)

# Vercel looks for `app` at module level (ASGI)
__all__ = ["app"]
