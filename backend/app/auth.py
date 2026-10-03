"""API-key authentication with organisation scoping.

Every stored record belongs to an organisation. A key maps to exactly one
organisation, so one key can never read another organisation's data.
"""

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException

from .config import settings

DEFAULT_ORG = "default"


@dataclass(frozen=True)
class Caller:
    org: str
    label: str  # who is acting; recorded in the audit log


def _parse_keys() -> dict[str, Caller]:
    keys: dict[str, Caller] = {}
    for entry in filter(None, (e.strip() for e in settings.API_KEYS.split(","))):
        parts = entry.split(":")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        keys[parts[0]] = Caller(org=parts[1], label=parts[2] if len(parts) > 2 else parts[1])
    if settings.API_KEY:
        keys.setdefault(settings.API_KEY, Caller(org=DEFAULT_ORG, label="api-key"))
    return keys


def auth_enabled() -> bool:
    return bool(settings.API_KEY or settings.API_KEYS.strip())


def get_caller(x_api_key: str | None = Header(default=None)) -> Caller:
    """FastAPI dependency: resolve the caller from X-API-Key.

    Settings are read per request so keys can rotate without a restart in tests.
    """
    if not auth_enabled():
        return Caller(org=DEFAULT_ORG, label="anonymous")
    if x_api_key:
        for key, caller in _parse_keys().items():
            if hmac.compare_digest(key, x_api_key):
                return caller
    raise HTTPException(401, "Invalid or missing API key (header X-API-Key).")
