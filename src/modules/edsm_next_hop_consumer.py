"""
EDSM next-in-route hop preview consumer.

A StreamConsumer that previews the *next* system in the plotted route before
the player jumps: its primary-star scoopability (from the route's ``StarClass``)
plus the EDSM worth-scanning verdict and value summary when available.

Mirrors ``EdsmLookupConsumer`` but points one hop ahead:
- The route comes from NavRoute.json via ``on_nav_route()``; the current system
  comes from FSDJump/Location via ``observe()``.  On either change the next hop
  is re-derived.
- When auto-lookups are enabled and a next hop exists, it runs the same
  per-system read (bodies + estimated-value) through the *shared* cache — so a
  hop looked up here is usually a cache hit once it becomes the current system.
- Fire-and-forget, non-gating, contained on failure.
- Scoopability comes from the plotted route, so the preview is emitted even when
  the EDSM lookup is unknown or fails (verdict/value simply stay None) — the
  fuel-safety signal is the reason this preview exists.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

import decky
from src.modules.edsm_next_hop import NextHop, NextHopTracker
from src.modules.edsm_read_client import STATUS_UNAVAILABLE, EdsmReadClient
from src.modules.edsm_system_cache import SystemLookupCache
from src.modules.edsm_system_value import derive_value_summary
from src.modules.edsm_worth_scanning import derive_verdict
from src.modules.ssl_context import build_ssl_context

if TYPE_CHECKING:
    from src.modules.edsm_read_client import SystemBodiesResult, SystemValueResult
    from src.modules.edsm_system_value import SystemValueSummary
    from src.modules.parser import ParsedEvent, SessionState
    from src.modules.settings import PluginSettings

_ARRIVAL_EVENTS = frozenset({"FSDJump", "Location"})

NEXT_HOP_EVENT = "edsm_next_hop"


def neutral_next_hop() -> dict:
    """The neutral 'no preview' payload (no route / no hop / disabled / failed)."""
    return {
        "system": None,
        "scoopable": None,
        "starClass": None,
        "verdict": None,
        "source": "edsm",
        "totalValue": None,
        "priorityBodies": [],
    }


class EdsmNextHopConsumer:
    """StreamConsumer that previews the next system in the plotted route."""

    name = "edsm_next_hop"
    reports_upload_stats = False  # read-only; does not contribute to upload stats

    def __init__(
        self,
        settings: PluginSettings,
        read_client: EdsmReadClient | None = None,
        cache: SystemLookupCache | None = None,
        on_next_hop: Callable[[dict], None] | None = None,
    ) -> None:
        self._settings = settings
        self._client = read_client or EdsmReadClient(ssl_context=build_ssl_context())
        self._cache = cache or SystemLookupCache()
        self._on_next_hop = on_next_hop  # optional callback for testing / wiring
        self._tracker = NextHopTracker()
        self._current_system: str = ""
        self._current_address: int | None = None
        # Dedup key of the last hop acted on: a system name, "" for the neutral
        # (no-hop) state, or None when nothing has been evaluated yet.
        self._last_hop: str | None = None
        self._tasks: set[asyncio.Task] = set()

    # --- StreamConsumer protocol ---

    def observe(self, event: ParsedEvent, session_state: SessionState | None = None) -> None:  # noqa: ARG002
        """Track the current system from arrivals and re-derive the next hop."""
        try:
            if event.event_type not in _ARRIVAL_EVENTS:
                return
            system = event.raw.get("StarSystem", "")
            if system:
                self._current_system = system
            address = event.raw.get("SystemAddress")
            if address is not None:
                self._current_address = address
            self._reevaluate()
        except Exception as e:
            decky.logger.error(f"EdsmNextHopConsumer.observe error: {e}")

    def on_nav_route(self, route: list[dict]) -> None:
        """Update the tracked route from a NavRoute.json update and re-derive."""
        try:
            self._tracker.set_route(route)
            self._reevaluate()
        except Exception as e:
            decky.logger.error(f"EdsmNextHopConsumer.on_nav_route error: {e}")

    def on_session_start(self) -> None:
        """New game launch: forget the route and current-system state.

        The shared cache lifecycle is owned by ``EdsmLookupConsumer``; this
        consumer does not clear it (both are reset in the same start pass).
        """
        self._tracker.clear()
        self._current_system = ""
        self._current_address = None
        self._last_hop = None

    def on_session_stop(self) -> None:
        """Watcher stopped: cancel in-flight lookups."""
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

    def reevaluate(self) -> None:
        """Public re-trigger (e.g. after auto-lookups are re-enabled)."""
        self._last_hop = None  # force a fresh emit for the current state
        self._reevaluate()

    def get_stats(self) -> dict:
        return {}

    # --- internal ---

    def _reevaluate(self) -> None:
        """Re-derive the next hop and, if changed, refresh the preview."""
        if not self._settings.get("edsm_lookups_enabled", False):
            return
        if not self._current_system:
            return  # don't know where we are yet; wait for an arrival
        hop = self._tracker.next_hop(self._current_system, self._current_address)
        if hop is None:
            if self._last_hop == "":
                return  # already neutral
            self._last_hop = ""
            self._emit(neutral_next_hop())
            return
        if hop.system == self._last_hop:
            return  # unchanged; avoid a redundant lookup
        self._last_hop = hop.system
        self._fire_lookup(hop)

    def _fire_lookup(self, hop: NextHop) -> None:
        """Schedule a background lookup for the hop (fire-and-forget)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop (e.g. in sync tests); run synchronously for testability.
            self._do_lookup_sync(hop)
            return
        task = loop.create_task(self._lookup_async(hop))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _do_lookup_sync(self, hop: NextHop) -> None:
        """Synchronous lookup path (used when no event loop is running)."""
        bodies_result = self._fetch_bodies_sync(hop.system)
        value_result = self._fetch_value_sync(hop.system)
        if hop.system != self._last_hop:
            return
        self._report(hop, derive_verdict(bodies_result), derive_value_summary(value_result))

    async def _lookup_async(self, hop: NextHop) -> None:
        """Async fire-and-forget lookup.  Never propagates exceptions."""
        try:
            bodies_result, value_result = await asyncio.gather(
                self._fetch_bodies_async(hop.system),
                self._fetch_value_async(hop.system),
            )
            if hop.system != self._last_hop:
                return
            self._report(hop, derive_verdict(bodies_result), derive_value_summary(value_result))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            decky.logger.error(f"EDSM next-hop lookup failed for {hop.system!r}: {e}")

    def _fetch_bodies_sync(self, system_name: str) -> SystemBodiesResult:
        cached = self._cache.get(system_name)
        if cached is not None:
            return cached
        result = self._client.get_system_bodies(system_name)
        if result.status != STATUS_UNAVAILABLE:
            self._cache.set(system_name, result)
        return result

    def _fetch_value_sync(self, system_name: str) -> SystemValueResult:
        cached = self._cache.get_value(system_name)
        if cached is not None:
            return cached
        result = self._client.get_estimated_value(system_name)
        if result.status != STATUS_UNAVAILABLE:
            self._cache.set_value(system_name, result)
        return result

    async def _fetch_bodies_async(self, system_name: str) -> SystemBodiesResult:
        cached = self._cache.get(system_name)
        if cached is not None:
            return cached
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._client.get_system_bodies, system_name)
        if result.status != STATUS_UNAVAILABLE:
            self._cache.set(system_name, result)
        return result

    async def _fetch_value_async(self, system_name: str) -> SystemValueResult:
        cached = self._cache.get_value(system_name)
        if cached is not None:
            return cached
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self._client.get_estimated_value, system_name)
        if result.status != STATUS_UNAVAILABLE:
            self._cache.set_value(system_name, result)
        return result

    def _report(
        self, hop: NextHop, verdict: str | None, value_summary: SystemValueSummary | None,
    ) -> None:
        self._emit(self._payload(hop, verdict, value_summary))

    def _emit(self, payload: dict) -> None:
        """Update stored state (callback) and emit the frontend event."""
        if self._on_next_hop is not None:
            try:
                self._on_next_hop(payload)
            except Exception as e:
                decky.logger.error(f"EDSM next-hop callback error: {e}")
        self._schedule_emit(payload)

    def _schedule_emit(self, payload: dict) -> None:
        """Emit the ``edsm_next_hop`` decky event when a loop is running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no loop (e.g. sync tests) — callback already carried state
        task = loop.create_task(decky.emit(NEXT_HOP_EVENT, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    def _payload(
        hop: NextHop, verdict: str | None, value_summary: SystemValueSummary | None,
    ) -> dict:
        payload = {
            "system": hop.system,
            "scoopable": hop.scoopable,
            "starClass": hop.star_class,
            "verdict": verdict,
            "source": "edsm",
            "totalValue": None,
            "priorityBodies": [],
        }
        if value_summary is not None:
            payload["totalValue"] = value_summary.total_value
            payload["priorityBodies"] = value_summary.priority_bodies
        return payload
