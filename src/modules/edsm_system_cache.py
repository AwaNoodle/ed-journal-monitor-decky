"""
Per-system TTL cache for EDSM body-lookup results.

Keyed by system name (exact match, case-sensitive as returned by the journal).
In-memory only; cleared on restart.  A few hours TTL is appropriate because a
system's explored state changes slowly.

Both stores are additionally bounded to ``max_entries`` and evict the
least-recently-used entry on insert past the cap: the TTL alone frees nothing
for a system that is never queried again, so a long route through many distinct
systems would otherwise grow the cache without limit.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import TYPE_CHECKING, TypeVar

from src.modules.constants import MAX_SYSTEM_CACHE_ENTRIES

if TYPE_CHECKING:
    from src.modules.edsm_read_client import SystemBodiesResult, SystemValueResult

DEFAULT_TTL_SECONDS = 4 * 3600  # 4 hours

_T = TypeVar("_T")


class SystemLookupCache:
    """Thread-unsafe in-memory TTL + LRU cache.  Acceptable: asyncio is single-threaded.

    Holds two independent per-system stores sharing one TTL and one entry cap:
    the bodies lookup (``get``/``set``) and the estimated-value lookup
    (``get_value``/``set_value``).  The caps are applied per store, so evicting
    a bodies entry never drops that system's value entry.
    """

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = MAX_SYSTEM_CACHE_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max(1, int(max_entries))
        self._store: OrderedDict[str, tuple[float, SystemBodiesResult]] = OrderedDict()
        self._value_store: OrderedDict[str, tuple[float, SystemValueResult]] = OrderedDict()

    def get(self, system_name: str) -> SystemBodiesResult | None:
        """Return the cached result if fresh, else None (and evict the stale entry)."""
        return self._get_fresh(self._store, system_name)

    def set(self, system_name: str, result: SystemBodiesResult) -> None:
        """Store a result under ``system_name`` with the current timestamp."""
        self._put_bounded(self._store, system_name, result)

    def get_value(self, system_name: str) -> SystemValueResult | None:
        """Return the cached estimated-value result if fresh, else None."""
        return self._get_fresh(self._value_store, system_name)

    def set_value(self, system_name: str, result: SystemValueResult) -> None:
        """Store an estimated-value result under ``system_name``."""
        self._put_bounded(self._value_store, system_name, result)

    def clear(self) -> None:
        """Discard all cached entries (e.g. on session start)."""
        self._store.clear()
        self._value_store.clear()

    # --- internal ---

    def _get_fresh(
        self, store: OrderedDict[str, tuple[float, _T]], system_name: str,
    ) -> _T | None:
        """Read one store, honouring the TTL and refreshing LRU recency on a hit."""
        entry = store.get(system_name)
        if entry is None:
            return None
        stored_at, result = entry
        if time.monotonic() - stored_at > self._ttl:
            del store[system_name]
            return None
        store.move_to_end(system_name)
        return result

    def _put_bounded(
        self, store: OrderedDict[str, tuple[float, _T]], system_name: str, result: _T,
    ) -> None:
        """Insert into one store, evicting least-recently-used entries past the cap."""
        store[system_name] = (time.monotonic(), result)
        store.move_to_end(system_name)
        while len(store) > self._max_entries:
            store.popitem(last=False)
