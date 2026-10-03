import httpx
import pytest
from fastapi.testclient import TestClient

from app import ratelimit, storage
from app.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Fresh SQLite store, open auth, rules proposer and a clean rate limiter per test."""
    storage.set_store(storage.SqliteDocStore(str(tmp_path / "test.db")))
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(settings, "API_KEYS", "")
    monkeypatch.setattr(settings, "PROPOSER", "rules")
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MIN", 30)
    ratelimit.reset()

    class Unreachable:  # Ollama is never really contacted; fail instantly instead of timing out
        def __init__(self, **kw): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): raise ConnectionError("ollama unreachable (test)")

    monkeypatch.setattr(httpx, "AsyncClient", Unreachable)
    yield
    storage.set_store(None)


@pytest.fixture
def client():
    return TestClient(app)


PROCESS_SCORES = {"steps": 8, "bottlenecks": 6, "compliance": 9, "automation": 5, "repeatability": 7}
