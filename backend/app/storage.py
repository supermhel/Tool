"""Stockage des tickets.

Implémentation par défaut : persistance dans un fichier JSON (simple, sans
dépendance). En production on remplacerait `JsonStore` par un repository
PostgreSQL sans changer l'interface utilisée par les routers.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone

_DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
_DATA_FILE = os.path.join(_DATA_DIR, "tickets.json")
_lock = threading.Lock()


class JsonStore:
    def __init__(self, path: str = _DATA_FILE):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write([])

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def create(self, ticket: dict) -> dict:
        with _lock:
            data = self._read()
            ticket = dict(ticket)
            ticket["id"] = uuid.uuid4().hex[:12]
            ticket["created_at"] = datetime.now(timezone.utc).isoformat()
            data.insert(0, ticket)
            self._write(data)
            return ticket

    def list(self) -> list:
        with _lock:
            return self._read()

    def get(self, ticket_id: str):
        with _lock:
            for t in self._read():
                if t["id"] == ticket_id:
                    return t
            return None

    def delete(self, ticket_id: str) -> bool:
        with _lock:
            data = self._read()
            new = [t for t in data if t["id"] != ticket_id]
            if len(new) == len(data):
                return False
            self._write(new)
            return True


store = JsonStore()
