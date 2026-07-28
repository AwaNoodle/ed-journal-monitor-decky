"""
ED Journal Monitor - Decky Plugin Backend
Monitors Elite Dangerous journal files and submits events to EDDN.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import decky

# Decky deploys modules to bin/src/modules/ but runs main.py from the plugin root.
# Add bin/ to sys.path so that `from src.modules...` imports resolve.
_bin_dir = Path(__file__).parent / "bin"
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

from src.modules.activity_log import ActivityLog  # noqa: E402
from src.modules.diagnostics import create_diagnostics as _create_diagnostics  # noqa: E402
from src.modules.edsm_lookup_consumer import EdsmLookupConsumer  # noqa: E402
from src.modules.edsm_nearest_scoopable_lookup import lookup_nearest_scoopable  # noqa: E402
from src.modules.edsm_next_hop_consumer import (  # noqa: E402
    EdsmNextHopConsumer,
    neutral_next_hop,
)
from src.modules.edsm_read_client import EdsmReadClient  # noqa: E402
from src.modules.edsm_system_cache import SystemLookupCache  # noqa: E402
from src.modules.forwarders.edsm import EdsmForwarder  # noqa: E402
from src.modules.parser import JournalParser  # noqa: E402
from src.modules.path_finder import JournalPathFinder  # noqa: E402
from src.modules.session_stats import SessionStats, SessionStatsAccumulator  # noqa: E402
from src.modules.settings import PluginSettings  # noqa: E402
from src.modules.signal_batcher import SignalBatcher  # noqa: E402
from src.modules.ssl_context import build_ssl_context  # noqa: E402
from src.modules.submitter import EDDNSubmitter  # noqa: E402
from src.modules.validator import EDDNValidator  # noqa: E402
from src.modules.watcher import JournalWatcher  # noqa: E402


class Plugin:
    def __init__(self) -> None:
        self.settings: PluginSettings | None = None
        self.path_finder: JournalPathFinder | None = None
        self.parser: JournalParser | None = None
        self.validator: EDDNValidator | None = None
        self.activity_log: ActivityLog | None = None
        self.submitter: EDDNSubmitter | None = None
        self.session_stats: SessionStatsAccumulator | None = None
        self.edsm: EdsmForwarder | None = None
        self.edsm_lookup: EdsmLookupConsumer | None = None
        self.edsm_next_hop: EdsmNextHopConsumer | None = None
        self.edsm_read_client: EdsmReadClient | None = None
        self.watcher: JournalWatcher | None = None
        # Stream consumers driven by lifecycle/stats fan-out (session stats,
        # EDSM forwarder, ...). The watcher fans observe() to the same list.
        self.consumers: list = []
        self.ed_running: bool = False
        # Current worth-scanning verdict for the active system (set by lookup consumer).
        self._edsm_verdict: dict | None = None
        # Next-in-route hop preview for the plotted route (set by next-hop consumer).
        self._edsm_next_hop: dict | None = None
        # Strong references to in-flight emit tasks (asyncio keeps only weak
        # references, so an unreferenced task can be GC'd mid-flight).
        self._emit_tasks: set[asyncio.Task] = set()

    async def _main(self) -> None:
        decky.logger.info("ED Journal Monitor starting...")

        # Initialize settings
        self.settings = PluginSettings()
        await self.settings.load()

        # Read version from package.json and persist to settings for EDDN headers
        pkg_json = Path(__file__).parent / "package.json"
        if pkg_json.exists():
            pkg_data = json.loads(pkg_json.read_text())
            version = pkg_data.get("version", "0.1.0")
            await self.settings.set("software_version", version)
            decky.logger.info(f"ED Journal Monitor v{version}")
        else:
            await self.settings.set("software_version", "0.1.0")
            decky.logger.warning("package.json not found, using default version 0.1.0")

        # Initialize components
        self.path_finder = JournalPathFinder(self.settings)
        self.parser = JournalParser()
        self.validator = EDDNValidator()
        self.activity_log = ActivityLog()
        self.submitter = EDDNSubmitter(self.settings, activity_log=self.activity_log)
        self.session_stats = SessionStatsAccumulator(on_change=self._on_session_stats_change)
        self.edsm = EdsmForwarder(
            self.settings,
            on_stats_change=self._on_target_stats_change,
            activity_log=self.activity_log,
        )
        # Share one read client + per-system cache across both EDSM read
        # consumers, so a system previewed as a next hop is a cache hit once it
        # becomes the current system (and vice versa).
        self.edsm_read_client = EdsmReadClient(ssl_context=build_ssl_context())
        edsm_cache = SystemLookupCache()
        self.edsm_lookup = EdsmLookupConsumer(
            settings=self.settings,
            read_client=self.edsm_read_client,
            cache=edsm_cache,
            on_verdict=self._on_edsm_verdict,
            on_value=self._on_edsm_value,
        )
        self.edsm_next_hop = EdsmNextHopConsumer(
            settings=self.settings,
            read_client=self.edsm_read_client,
            cache=edsm_cache,
            on_next_hop=self._on_edsm_next_hop,
        )
        self.consumers = [self.session_stats, self.edsm, self.edsm_lookup, self.edsm_next_hop]
        signal_batcher = SignalBatcher()
        self.watcher = JournalWatcher(
            settings=self.settings,
            parser=self.parser,
            validator=self.validator,
            submitter=self.submitter,
            signal_batcher=signal_batcher,
            consumers=self.consumers,
        )

        # Try to find journal path from cache or VDF scan
        journal_path = await self.path_finder.find_journal_path()
        if journal_path:
            decky.logger.info(f"Journal path found: {journal_path}")
        else:
            decky.logger.info("Journal path not found - will re-scan when ED starts")

        # Apply detailed logging preference on startup
        detailed_logging = self.settings.get("detailed_logging", False)
        if detailed_logging:
            decky.logger.setLevel(logging.DEBUG)
            decky.logger.info("Detailed logging enabled (DEBUG level)")
        else:
            decky.logger.setLevel(logging.INFO)

        decky.logger.info("ED Journal Monitor started successfully")

    async def _unload(self) -> None:
        decky.logger.info("ED Journal Monitor unloading...")
        if self.watcher and self.watcher.is_running:
            await self.watcher.stop()
            self._notify_consumers_session_stop()
        decky.logger.info("ED Journal Monitor unloaded")

    async def _uninstall(self) -> None:
        decky.logger.info("ED Journal Monitor uninstalled")

    async def _migration(self) -> None:
        pass

    # --- Callable methods (invoked from TypeScript frontend) ---

    async def start_watcher(self) -> dict:
        """Start the journal watcher. Returns status info."""
        if not self.watcher:
            return {"success": False, "error": "Watcher not initialized"}

        if not self.settings.get("enabled", True):
            return {"success": False, "error": "Monitor is disabled"}

        if self.watcher.is_running:
            return {"success": True, "status": "already_running"}

        # Ensure we have a journal path
        journal_path = await self.path_finder.find_journal_path()
        if not journal_path:
            return {"success": False, "error": "Journal path not found"}

        await self.watcher.start(journal_path)
        return {"success": True, "status": "started", "journal_path": journal_path}

    async def stop_watcher(self) -> dict:
        """Stop the journal watcher and persist state."""
        if not self.watcher or not self.watcher.is_running:
            return {"success": True, "status": "not_running"}

        await self.watcher.stop()
        self._notify_consumers_session_stop()
        return {"success": True, "status": "stopped"}

    async def find_journal_path(self) -> dict:
        """Attempt to find the ED journal directory. Returns path or None."""
        path = await self.path_finder.find_journal_path()
        if path:
            return {"success": True, "path": path}
        return {"success": False, "path": None}

    async def set_journal_path(self, path: str) -> dict:
        """Manually set the journal directory path."""
        return await self.path_finder.set_manual_path(path)

    async def get_status(self) -> dict:
        """Get current plugin status."""
        is_running = self.watcher.is_running if self.watcher else False
        journal_path = self.settings.get("journal_path") if self.settings else None
        uploader_id = self.settings.get("uploader_id") if self.settings else None

        return {
            "ed_running": self.ed_running,
            "watcher_running": is_running,
            "journal_path": journal_path,
            "journal_path_source": self.settings.get("journal_path_source") if self.settings else None,
            "uploader_id": uploader_id,
            "edsm_commander_name": self.settings.get("edsm_commander_name", "") if self.settings else "",
            "edsm_api_key_set": bool(self.settings.get("edsm_api_key")) if self.settings else False,
            "edsm_lookups_enabled": bool(self.settings.get("edsm_lookups_enabled", False)) if self.settings else False,
            "edsm_notifications_enabled": (
                bool(self.settings.get("edsm_notifications_enabled", False)) if self.settings else False
            ),
            "edsm_notify_all_verdicts": (
                bool(self.settings.get("edsm_notify_all_verdicts", False)) if self.settings else False
            ),
            "enabled": self.settings.get("enabled", True) if self.settings else True,
            "detailed_logging": self.settings.get("detailed_logging", False) if self.settings else False,
            "edsm_worth_scanning": self._edsm_verdict,
            "edsm_next_hop": self._edsm_next_hop,
            **self._build_target_stats(),
        }

    async def set_uploader_id(self, uploader_id: str) -> dict:
        """Set the EDDN uploader ID."""
        await self.settings.set("uploader_id", uploader_id)
        return {"success": True}

    async def set_edsm_credentials(self, commander_name: str, api_key: str) -> dict:
        """Set the EDSM commander name and API key. The API key's presence is the
        consent gate for identifiable EDSM uploads.

        If Elite Dangerous is already running when credentials are saved, the
        EDSM forwarder is (re)started immediately so the user doesn't have to
        relaunch the game to begin forwarding — mirroring the on_session_start
        hook fired at ED start.
        """
        await self.settings.set("edsm_commander_name", commander_name)
        # An empty api_key means "keep the existing saved key" so the user can
        # update the commander name without re-pasting their key.
        if api_key:
            await self.settings.set("edsm_api_key", api_key)
        if self.ed_running and self.edsm is not None:
            self.edsm.on_session_start()
            await decky.emit("status_update", self._build_target_stats())
        return {"success": True}

    async def get_edsm_credentials(self) -> dict:
        """Return the EDSM commander name and whether an API key is set. The raw
        API key is never returned to the frontend."""
        commander_name = self.settings.get("edsm_commander_name", "") if self.settings else ""
        api_key_set = bool(self.settings.get("edsm_api_key")) if self.settings else False
        return {"commander_name": commander_name, "api_key_set": api_key_set}

    async def set_enabled(self, enabled: bool) -> dict:
        """Enable or disable the monitor."""
        await self.settings.set("enabled", enabled)
        if not enabled and self.watcher and self.watcher.is_running:
            await self.watcher.stop()
        return {"success": True, "enabled": enabled}

    async def set_edsm_lookups_enabled(self, enabled: bool) -> dict:
        """Enable or disable EDSM auto-lookups. Independent of the EDSM API key."""
        await self.settings.set("edsm_lookups_enabled", enabled)
        if not enabled:
            self._edsm_verdict = None
            self._edsm_next_hop = None
            await decky.emit("edsm_worth_scanning", {
                "verdict": None, "system": None, "source": "edsm",
                "totalValue": None, "priorityBodies": [],
            })
            await decky.emit("edsm_next_hop", neutral_next_hop())
        else:
            if self.edsm_lookup is not None:
                self.edsm_lookup.force_lookup(self.edsm_lookup._last_system)
            if self.edsm_next_hop is not None:
                self.edsm_next_hop.reevaluate()
        return {"success": True}

    async def set_edsm_notifications_enabled(self, enabled: bool) -> dict:
        """Enable or disable worth-scanning toast notifications. Independent of
        the EDSM API key and of the EDDN/EDSM write paths."""
        await self.settings.set("edsm_notifications_enabled", enabled)
        return {"success": True}

    async def set_edsm_notify_all_verdicts(self, enabled: bool) -> dict:
        """Set the notification verdict threshold: False = green only, True =
        green and yellow."""
        await self.settings.set("edsm_notify_all_verdicts", enabled)
        return {"success": True}

    async def set_detailed_logging(self, enabled: bool) -> dict:
        """Set detailed logging (DEBUG) on or off (INFO). Persists to settings."""
        if enabled:
            decky.logger.setLevel(logging.DEBUG)
            decky.logger.debug("Detailed logging enabled")
        else:
            decky.logger.setLevel(logging.INFO)
            decky.logger.info("Detailed logging disabled")
        await self.settings.set("detailed_logging", enabled)
        return {"success": True, "detailed_logging": enabled}

    async def set_ed_running(self, enabled: bool) -> dict:
        """Set the ED running state. Emits ed_state_change event if state changes."""
        if enabled == self.ed_running:
            return {"success": True}
        self.ed_running = enabled
        if enabled:
            if self.submitter:
                self.submitter.reset_stats()
            self._edsm_verdict = None
            self._edsm_next_hop = None
            # New launch epoch: reset/start every stream consumer (session
            # stats, EDSM forwarder). Runs before start_watcher's _initial_scan
            # replay so the current launch's earlier events are recounted.
            for consumer in self.consumers:
                start = getattr(consumer, "on_session_start", None)
                if callable(start):
                    start()
            await decky.emit("status_update", self._build_target_stats())
        else:
            self._edsm_verdict = None
            self._edsm_next_hop = None
            await decky.emit("edsm_worth_scanning", {
                "verdict": None, "system": None, "source": "edsm",
                "totalValue": None, "priorityBodies": [],
            })
            await decky.emit("edsm_next_hop", neutral_next_hop())
        await decky.emit("ed_state_change", {"ed_running": enabled})
        return {"success": True}

    async def check_ed_running(self) -> dict:
        """Check if ED appears to be already running (e.g. started before plugin loaded)."""
        if not self.path_finder:
            return {"running": False, "reason": "path_finder not initialized"}

        # First, try to find journal path if we don't have one
        if not self.settings.get("journal_path"):
            await self.path_finder.find_journal_path()

        running = self.path_finder.is_ed_likely_running()
        return {"running": running}

    async def create_diagnostics(self) -> dict:
        """Create a diagnostic bundle zip file."""
        return _create_diagnostics(
            settings=self.settings,
            watcher=self.watcher,
            submitter=self.submitter,
        )

    async def get_recent_activity(
        self, limit: int = 50, outcome: str | None = None,
    ) -> list[dict]:
        """Get recent activity log entries."""
        if not self.activity_log:
            return []
        return self.activity_log.get_recent(limit=limit, outcome=outcome)

    async def get_session_stats(self) -> dict:
        """Get the current session stats for the active ED game launch."""
        if not self.session_stats:
            return SessionStats().__dict__.copy()
        return self.session_stats.get_stats()

    async def get_nearest_scoopable_star(self) -> dict:
        """On-demand: find the nearest fuel-scoopable star from the current
        system via an EDSM sphere-systems query. Gated by edsm_lookups_enabled;
        makes no request when disabled or before the current system is known."""
        current_system = self.edsm_next_hop.current_system if self.edsm_next_hop else ""
        lookups_enabled = bool(self.settings.get("edsm_lookups_enabled", False)) if self.settings else False
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lookup_nearest_scoopable, self.edsm_read_client, current_system, lookups_enabled,
        )
        return {
            "status": result.status,
            "system": result.system,
            "distance": result.distance,
            "star_class": result.star_class,
        }

    # --- internal helpers ---

    def _on_edsm_verdict(self, system_name: str, verdict: str | None, notify: bool) -> None:  # noqa: ARG002
        """Called by the lookup consumer when a verdict is ready.  Stores it for
        get_status() rehydration and schedules a frontend emit.

        notify is intentionally not stored — a status fetch must never be able
        to replay a notification, so the rehydration dict structurally cannot
        carry the flag that triggers one."""
        self._edsm_verdict = {"system": system_name, "verdict": verdict, "source": "edsm"}

    def _on_edsm_value(self, system_name: str, value_payload: dict | None) -> None:
        """Called by the lookup consumer when a value summary is ready (or
        unavailable). Merges totalValue/priorityBodies onto the verdict already
        stored for the same system by _on_edsm_verdict, which the lookup
        consumer always calls first within the same lookup pass."""
        if self._edsm_verdict is None or self._edsm_verdict.get("system") != system_name:
            return
        if value_payload is None:
            self._edsm_verdict["totalValue"] = None
            self._edsm_verdict["priorityBodies"] = []
        else:
            self._edsm_verdict["totalValue"] = value_payload["totalValue"]
            self._edsm_verdict["priorityBodies"] = value_payload["priorityBodies"]

    def _on_edsm_next_hop(self, payload: dict) -> None:
        """Called by the next-hop consumer with a preview (or a neutral payload).

        Stores it for get_status() rehydration; a neutral payload (system None)
        is stored as None so get_status mirrors the verdict's neutral state."""
        self._edsm_next_hop = payload if payload.get("system") else None

    def _build_target_stats(self) -> dict:
        """Aggregate per-target upload stats by iterating the consumer registry.

        EDDN is wired in as one target entry from the embedded submitter; every
        consumer that reports upload stats contributes an entry under its own
        ``name``. The map uses no hardcoded per-target reporting branches, so a
        further target is purely additive.
        """
        targets: dict = {}
        if self.submitter:
            targets["eddn"] = self.submitter.get_stats()
        for consumer in self.consumers:
            if getattr(consumer, "reports_upload_stats", False):
                targets[consumer.name] = consumer.get_stats()
        return {
            "targets": targets,
            "last_upload_time": None,
            "last_upload_event": None,
        }

    def _notify_consumers_session_stop(self) -> None:
        """Call on_session_stop for every consumer (e.g. forced EDSM flush)."""
        for consumer in self.consumers:
            stop = getattr(consumer, "on_session_stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception as e:
                    decky.logger.error(f"Consumer on_session_stop error: {e}")

    def _on_session_stats_change(self, stats: dict) -> None:
        """Emit a session_update to the frontend when session stats change."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running event loop (e.g. during teardown) — skip emit.
            return
        task = loop.create_task(decky.emit("session_update", stats))
        self._emit_tasks.add(task)
        task.add_done_callback(self._emit_tasks.discard)

    def _on_target_stats_change(self) -> None:
        """Emit a status_update with the full per-target map when a non-EDDN
        target's stats change (e.g. an EDSM batch completes)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(decky.emit("status_update", self._build_target_stats()))
        self._emit_tasks.add(task)
        task.add_done_callback(self._emit_tasks.discard)
