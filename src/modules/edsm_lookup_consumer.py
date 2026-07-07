"""
EDSM arrival-triggered system lookup consumer.

Implements the StreamConsumer protocol.  On FSDJump/Location events, fires a
single background lookup for the arrived system and emits a worth-scanning
verdict back to the frontend via a decky event.

Design principles:
- Fire-and-forget: the lookup runs in a background asyncio task; observe()
  returns immediately.
- Non-gating: EDDN/EDSM-write are completely unaffected by lookup
  success or failure.
- Dedupe: at most one in-flight or completed lookup per system entry per
  session (deduped by the session's current system name).
- Toggle: if edsm_lookups_enabled is False, observe() short-circuits before
  any network call.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

import decky
from src.modules.edsm_read_client import STATUS_UNAVAILABLE, EdsmReadClient
from src.modules.edsm_system_cache import SystemLookupCache
from src.modules.edsm_worth_scanning import derive_verdict
from src.modules.ssl_context import build_ssl_context

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState
    from src.modules.settings import PluginSettings

_ARRIVAL_EVENTS = frozenset({"FSDJump", "Location"})

VERDICT_EVENT = "edsm_worth_scanning"


class EdsmLookupConsumer:
    """StreamConsumer that triggers per-system EDSM worth-scanning lookups on arrival."""

    name = "edsm_lookup"
    reports_upload_stats = False  # read-only; does not contribute to upload stats

    def __init__(
        self,
        settings: PluginSettings,
        read_client: EdsmReadClient | None = None,
        cache: SystemLookupCache | None = None,
        on_verdict: Callable[[str, str | None], None] | None = None,
    ) -> None:
        self._settings = settings
        self._client = read_client or EdsmReadClient(ssl_context=build_ssl_context())
        self._cache = cache or SystemLookupCache()
        self._on_verdict = on_verdict  # optional callback for testing / wiring
        self._last_system: str = ""
        self._lookup_tasks: set[asyncio.Task] = set()

    # --- StreamConsumer protocol ---

    def observe(self, event: ParsedEvent, session_state: SessionState | None = None) -> None:  # noqa: ARG002
        """Handle a parsed event. Never raises, never blocks."""
        try:
            if event.event_type not in _ARRIVAL_EVENTS:
                return
            if not self._settings.get("edsm_lookups_enabled", False):
                return
            system = event.raw.get("StarSystem", "")
            if not system or system == self._last_system:
                return
            self._last_system = system
            self._fire_lookup(system)
        except Exception as e:
            decky.logger.error(f"EdsmLookupConsumer.observe error: {e}")

    def on_session_start(self) -> None:
        """New game launch: clear session state."""
        self._last_system = ""
        self._cache.clear()

    def on_session_stop(self) -> None:
        """Watcher stopped: cancel in-flight lookups."""
        for task in list(self._lookup_tasks):
            if not task.done():
                task.cancel()

    def clear_last_system(self) -> None:
        """Reset dedup state so the next arrival re-triggers a lookup.

        Called by main.py when lookups are re-enabled mid-session, so the
        player gets a verdict for the system they're already in.
        """
        self._last_system = ""

    def get_stats(self) -> dict:
        return {}

    # --- internal ---

    def _fire_lookup(self, system_name: str) -> None:
        """Schedule a background lookup for system_name (fire-and-forget)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop (e.g. in sync tests); run synchronously for testability.
            self._do_lookup_sync(system_name)
            return
        task = loop.create_task(self._lookup_async(system_name))
        self._lookup_tasks.add(task)
        task.add_done_callback(self._lookup_tasks.discard)

    def _do_lookup_sync(self, system_name: str) -> None:
        """Synchronous lookup path (used when no event loop is running)."""
        cached = self._cache.get(system_name)
        if cached is not None:
            result = cached
        else:
            result = self._client.get_system_bodies(system_name)
            if result.status != STATUS_UNAVAILABLE:
                self._cache.set(system_name, result)
        verdict = derive_verdict(result)
        if verdict is None:
            return
        if system_name != self._last_system:
            return
        self._emit_verdict(system_name, verdict)

    async def _lookup_async(self, system_name: str) -> None:
        """Async fire-and-forget lookup.  Never propagates exceptions."""
        try:
            cached = self._cache.get(system_name)
            if cached is not None:
                result = cached
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, self._client.get_system_bodies, system_name
                )
                if result.status != STATUS_UNAVAILABLE:
                    self._cache.set(system_name, result)
            verdict = derive_verdict(result)
            if verdict is None:
                return
            if system_name != self._last_system:
                return
            self._emit_verdict(system_name, verdict)
            await decky.emit(VERDICT_EVENT, {
                "system": system_name,
                "verdict": verdict,
                "source": "edsm",
            })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            decky.logger.error(f"EDSM lookup failed for {system_name!r}: {e}")

    def _emit_verdict(self, system_name: str, verdict: str | None) -> None:
        """Call the optional on_verdict callback (used in main.py for session state)."""
        if self._on_verdict is not None:
            try:
                self._on_verdict(system_name, verdict)
            except Exception as e:
                decky.logger.error(f"EDSM verdict callback error: {e}")
