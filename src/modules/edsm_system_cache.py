from __future__ import annotations

"""
Per-system TTL cache for EDSM body-lookup results.

Keyed by system name (exact match, case-sensitive as returned by the journal).
In-memory only; cleared on restart.  A few hours TTL is appropriate because a
system's explored state changes slowly.
"""

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.edsm_read_client import SystemBodiesResult

DEFAULT_TTL_SECONDS = 4 * 3600  # 4 hours


class SystemLookupCache:
    """Thread-unsafe in-memory TTL cache.  Acceptable: asyncio is single-threaded."""

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, SystemBodiesResult]] = {}

    def get(self, system_name: str) -> SystemBodiesResult | None:
        """Return the cached result if fresh, else None (and evict the stale entry)."""
        entry = self._store.get(system_name)
        if entry is None:
            return None
        stored_at, result = entry
        if time.monotonic() - stored_at > self._ttl:
            del self._store[system_name]
            return None
        return result

    def set(self, system_name: str, result: SystemBodiesResult) -> None:
        """Store a result under ``system_name`` with the current timestamp."""
        self._store[system_name] = (time.monotonic(), result)

    def clear(self) -> None:
        """Discard all cached entries (e.g. on session start)."""
        self._store.clear()
