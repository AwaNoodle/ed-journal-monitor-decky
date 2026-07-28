"""
EDSM arrival-triggered system lookup consumer.

Implements the StreamConsumer protocol.  On FSDJump/Location events, fires a
single background lookup for the arrived system and emits a worth-scanning
verdict, plus a system value summary, back to the frontend via one merged
decky event.

Design principles:
- Fire-and-forget: the lookup runs in a background asyncio task; observe()
  returns immediately.
- Non-gating: EDDN/EDSM-write are completely unaffected by lookup
  success or failure.
- Dedupe: at most one in-flight or completed lookup per system entry per
  session (deduped by the session's current system name).
- Toggle: if edsm_lookups_enabled is False, observe() short-circuits before
  any network call.
- Bodies and estimated-value are fetched concurrently per arrival (one logical
  lookup, one cache entry per system). The value summary is reported via
  ``on_value`` and merged into the emitted event whenever the verdict itself
  is reported (i.e. the bodies fetch succeeded); a value-only failure reports
  neutral (None) without blocking the verdict.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

import decky
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
        on_verdict: Callable[[str, str | None, bool], None] | None = None,
        on_value: Callable[[str, dict | None], None] | None = None,
    ) -> None:
        self._settings = settings
        self._client = read_client or EdsmReadClient(ssl_context=build_ssl_context())
        self._cache = cache or SystemLookupCache()
        self._on_verdict = on_verdict  # optional callback for testing / wiring
        self._on_value = on_value  # optional callback for testing / wiring
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

    def force_lookup(self, system_name: str) -> None:
        """Trigger a lookup for system_name regardless of dedup state.

        Sets _last_system so the result passes the staleness guard, then fires
        the normal lookup path. No-op if system_name is empty.
        """
        if not system_name:
            return
        self._last_system = system_name
        self._fire_lookup(system_name)

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
        bodies_result = self._fetch_bodies_sync(system_name)
        value_result = self._fetch_value_sync(system_name)
        verdict = derive_verdict(bodies_result)
        value_summary = derive_value_summary(value_result)
        if verdict is None:
            return
        if system_name != self._last_system:
            return
        notify = self._compute_notify(verdict)
        self._emit_verdict(system_name, verdict, notify)
        self._emit_value(system_name, value_summary)

    async def _lookup_async(self, system_name: str) -> None:
        """Async fire-and-forget lookup.  Never propagates exceptions."""
        try:
            bodies_result, value_result = await asyncio.gather(
                self._fetch_bodies_async(system_name),
                self._fetch_value_async(system_name),
            )
            verdict = derive_verdict(bodies_result)
            value_summary = derive_value_summary(value_result)
            if verdict is None:
                return
            if system_name != self._last_system:
                return
            notify = self._compute_notify(verdict)
            self._emit_verdict(system_name, verdict, notify)
            self._emit_value(system_name, value_summary)
            await decky.emit(VERDICT_EVENT, {
                "system": system_name,
                "verdict": verdict,
                "source": "edsm",
                "notify": notify,
                **self._value_fields(value_summary),
            })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            decky.logger.error(f"EDSM lookup failed for {system_name!r}: {e}")

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

    def _compute_notify(self, verdict: str | None) -> bool:
        """Whether this verdict should raise a user-facing notification.

        Derived entirely from the already-computed verdict and the persisted
        settings — issues no additional EDSM request. Red and neutral verdicts
        never notify at either threshold.
        """
        if not self._settings.get("edsm_notifications_enabled", False):
            return False
        if verdict == "green":
            return True
        if verdict == "yellow":
            return bool(self._settings.get("edsm_notify_all_verdicts", False))
        return False

    def _emit_verdict(self, system_name: str, verdict: str | None, notify: bool) -> None:
        """Call the optional on_verdict callback (used in main.py for session state)."""
        if self._on_verdict is not None:
            try:
                self._on_verdict(system_name, verdict, notify)
            except Exception as e:
                decky.logger.error(f"EDSM verdict callback error: {e}")

    def _emit_value(self, system_name: str, summary: SystemValueSummary | None) -> None:
        """Call the optional on_value callback (used in main.py for session state)."""
        if self._on_value is not None:
            try:
                self._on_value(system_name, self._value_payload(summary))
            except Exception as e:
                decky.logger.error(f"EDSM value callback error: {e}")

    @staticmethod
    def _value_payload(summary: SystemValueSummary | None) -> dict | None:
        """Frontend-shaped value fields, or None when no summary is available."""
        if summary is None:
            return None
        return {"totalValue": summary.total_value, "priorityBodies": summary.priority_bodies}

    @classmethod
    def _value_fields(cls, summary: SystemValueSummary | None) -> dict:
        """Value fields for the merged emit, defaulting to the neutral state."""
        payload = cls._value_payload(summary)
        if payload is None:
            return {"totalValue": None, "priorityBodies": []}
        return payload
