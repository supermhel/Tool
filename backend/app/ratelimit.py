"""Tiny in-memory sliding-window rate limiter for the expensive endpoints.

Per-process only: on serverless platforms each instance counts separately, so
treat this as a safety net, not as a quota system.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from .auth import Caller, get_caller
from .config import settings

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def rate_limited(caller: Caller = Depends(get_caller)) -> Caller:
    limit = settings.RATE_LIMIT_PER_MIN
    if limit <= 0:
        return caller
    now = time.monotonic()
    key = f"{caller.org}:{caller.label}"
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Rate limit exceeded; retry in a minute.")
        q.append(now)
    return caller
