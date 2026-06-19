import pytest
from app import storage
from app.routers import tickets as tickets_router, evaluations as eval_router, chat as chat_router


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Each test gets a fresh JsonStore in a temp directory."""
    new_store = storage.JsonStore(str(tmp_path / "tickets.json"))
    for module in (storage, tickets_router, eval_router, chat_router):
        monkeypatch.setattr(module, "store", new_store)
    return new_store
