"""
ED Journal Monitor - Decky Plugin Backend
Monitors Elite Dangerous journal files and submits events to EDDN.
"""

import decky
from src.modules.parser import JournalParser
from src.modules.path_finder import JournalPathFinder
from src.modules.settings import PluginSettings
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


class Plugin:
    def __init__(self) -> None:
        self.settings: PluginSettings | None = None
        self.path_finder: JournalPathFinder | None = None
        self.parser: JournalParser | None = None
        self.validator: EDDNValidator | None = None
        self.submitter: EDDNSubmitter | None = None
        self.watcher: JournalWatcher | None = None

    async def _main(self) -> None:
        decky.logger.info("ED Journal Monitor starting...")

        # Initialize settings
        self.settings = PluginSettings()
        await self.settings.load()

        # Initialize components
        self.path_finder = JournalPathFinder(self.settings)
        self.parser = JournalParser()
        self.validator = EDDNValidator()
        self.submitter = EDDNSubmitter(self.settings)
        self.watcher = JournalWatcher(
            settings=self.settings,
            parser=self.parser,
            validator=self.validator,
            submitter=self.submitter,
        )

        # Try to find journal path from cache or VDF scan
        journal_path = await self.path_finder.find_journal_path()
        if journal_path:
            decky.logger.info(f"Journal path found: {journal_path}")
        else:
            decky.logger.info("Journal path not found - will re-scan when ED starts")

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

        stats = {}
        if self.submitter:
            stats = self.submitter.get_stats()

        return {
            "watcher_running": is_running,
            "journal_path": journal_path,
            "journal_path_source": self.settings.get("journal_path_source") if self.settings else None,
            "uploader_id": uploader_id,
            "enabled": self.settings.get("enabled", True) if self.settings else True,
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
