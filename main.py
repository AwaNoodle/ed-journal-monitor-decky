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
from src.modules.parser import JournalParser  # noqa: E402
from src.modules.path_finder import JournalPathFinder  # noqa: E402
from src.modules.session_stats import SessionStats, SessionStatsAccumulator  # noqa: E402
from src.modules.settings import PluginSettings  # noqa: E402
from src.modules.signal_batcher import SignalBatcher  # noqa: E402
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
        self.watcher: JournalWatcher | None = None
        self.ed_running: bool = False
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
        signal_batcher = SignalBatcher()
        self.watcher = JournalWatcher(
            settings=self.settings,
            parser=self.parser,
            validator=self.validator,
            submitter=self.submitter,
            signal_batcher=signal_batcher,
            consumers=[self.session_stats],
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

        stats = {
            "success_count": 0,
            "fail_count": 0,
            "last_upload_time": None,
            "last_upload_event": None,
        }
        if self.submitter:
            stats.update(self.submitter.get_stats())

        return {
            "ed_running": self.ed_running,
            "watcher_running": is_running,
            "journal_path": journal_path,
            "journal_path_source": self.settings.get("journal_path_source") if self.settings else None,
            "uploader_id": uploader_id,
            "enabled": self.settings.get("enabled", True) if self.settings else True,
            "detailed_logging": self.settings.get("detailed_logging", False) if self.settings else False,
            **stats,
        }

    async def set_uploader_id(self, uploader_id: str) -> dict:
        """Set the EDDN uploader ID."""
        await self.settings.set("uploader_id", uploader_id)
        return {"success": True}

    async def set_enabled(self, enabled: bool) -> dict:
        """Enable or disable the monitor."""
        await self.settings.set("enabled", enabled)
        if not enabled and self.watcher and self.watcher.is_running:
            await self.watcher.stop()
        return {"success": True, "enabled": enabled}

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
        if enabled and self.submitter:
            self.submitter.reset_stats()
            await decky.emit("status_update", self.submitter.get_stats())
        if enabled and self.session_stats:
            # Reset session stats on the same launch epoch as upload stats.
            # Runs before start_watcher's _initial_scan replay so the current
            # launch's earlier events are recounted (retroactive totals).
            self.session_stats.reset()
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

    # --- internal helpers ---

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
