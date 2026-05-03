from __future__ import annotations

"""
Journal watcher.
Polls the ED journal directory for new/changed files and processes events.
"""

import asyncio
import contextlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    from src.modules.parser import JournalParser, ParsedEvent
    from src.modules.settings import PluginSettings
    from src.modules.submitter import EDDNSubmitter
    from src.modules.validator import EDDNValidator


class JournalWatcher:
    """Watches ED journal directory for new events via polling."""

    def __init__(
        self,
        settings: PluginSettings,
        parser: JournalParser,
        validator: EDDNValidator,
        submitter: EDDNSubmitter,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.validator = validator
        self.submitter = submitter
        self.is_running = False

        self._journal_path: str | None = None
        self._poll_interval: int = 10  # seconds
        self._poll_task: asyncio.Task | None = None
        self._file_positions: dict[str, int] = {}  # filepath -> last line number
        self._known_files: set[str] = set()

    async def start(self, journal_path: str) -> None:
        """Start the polling watcher."""
        if self.is_running:
            return

        if not self.settings.get("enabled", True):
            decky.logger.info("Monitor is disabled, not starting watcher")
            return

        self._journal_path = journal_path
        self._poll_interval = self.settings.get("poll_interval", 10)
        self.is_running = True

        # Load persisted last-active timestamp for catch-up
        last_active = self._load_last_active()

        # Initial scan: process files from catch-up or current date
        await self._initial_scan(last_active)

        # Start periodic polling
        self._poll_task = asyncio.create_task(self._poll_loop())
        decky.logger.info(f"Journal watcher started on {journal_path}")

    async def stop(self) -> None:
        """Stop the watcher and persist state."""
        self.is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        # Persist last-active timestamp
        self._save_last_active()
        decky.logger.info("Journal watcher stopped")

    async def _initial_scan(self, last_active: str | None) -> None:
        """Process journal files on watcher start for catch-up."""
        journal_dir = Path(self._journal_path)
        if not journal_dir.is_dir():
            return

        log_files = sorted(journal_dir.glob("Journal*.log"))

        for log_file in log_files:
            if last_active:
                # Catch-up: process files modified after last-active timestamp
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
                try:
                    last_active_dt = datetime.fromisoformat(last_active)
                    if file_mtime < last_active_dt:
                        # File hasn't been modified since last session, skip
                        # But still track it for position
                        self._track_file_position(str(log_file))
                        continue
                except ValueError:
                    pass
            # First run: only process today's files
            elif not self._is_from_today(log_file.name):
                self._track_file_position(str(log_file))
                continue

            await self._process_file(str(log_file))

    async def _poll_loop(self) -> None:
        """Periodic polling loop."""
        while self.is_running:
            try:
                await self._poll()
            except Exception as e:
                decky.logger.error(f"Poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _poll(self) -> None:
        """Single poll cycle: check for new/changed files."""
        if not self._journal_path:
            return

        journal_dir = Path(self._journal_path)
        if not journal_dir.is_dir():
            return

        log_files = sorted(journal_dir.glob("Journal*.log"))

        for log_file in log_files:
            filepath = str(log_file)
            if filepath not in self._known_files:
                # New file detected
                decky.logger.info(f"New journal file detected: {log_file.name}")
                self._known_files.add(filepath)
            await self._process_file(filepath)

    async def _process_file(self, filepath: str) -> None:
        """
        Process a journal file, reading only new lines from last position.
        """
        try:
            with Path(filepath).open(encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            decky.logger.error(f"Failed to read {filepath}: {e}")
            return

        last_position = self._file_positions.get(filepath, 0)
        new_lines = lines[last_position:]

        if not new_lines:
            return

        self._known_files.add(filepath)

        for line in new_lines:
            event = self.parser.parse_line(line)
            if not event:
                continue

            if self.parser.is_reportable(event):
                await self._process_reportable_event(event)

        # Update position
        self._file_positions[filepath] = len(lines)

    async def _process_reportable_event(self, event: ParsedEvent) -> None:
        """Validate and submit a reportable event."""
        # Validate
        validated = self.validator.validate(event)
        if not validated:
            decky.logger.debug(f"Event validation failed: {event.event_type}")
            return

        # Transform to EDDN message
        message = self.validator.transform(event, self.parser.session_state)

        # Submit
        await self.submitter.submit(message)

    def _track_file_position(self, filepath: str) -> None:
        """Track a file's line count without processing it (for catch-up skipping)."""
        try:
            with Path(filepath).open(encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
            self._file_positions[filepath] = line_count
            self._known_files.add(filepath)
        except OSError:
            pass

    def _is_from_today(self, filename: str) -> bool:
        """Check if a journal filename is from today or newer."""
        match = re.match(r"Journal\.(\d{4}-\d{2}-\d{2})", filename)
        if not match:
            return False
        file_date = match.group(1)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return file_date >= today

    def _load_last_active(self) -> str | None:
        """Load the last-active timestamp from runtime dir."""
        runtime_dir = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", "")
        if not runtime_dir:
            return None
        ts_file = Path(runtime_dir) / "last_active"
        if ts_file.is_file():
            try:
                return ts_file.read_text().strip()
            except OSError:
                return None
        return None

    def _save_last_active(self) -> None:
        """Persist the last-active timestamp to runtime dir."""
        runtime_dir = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", "")
        if not runtime_dir:
            return
        ts_file = Path(runtime_dir) / "last_active"
        try:
            ts_file.parent.mkdir(parents=True, exist_ok=True)
            ts_file.write_text(datetime.now(timezone.utc).isoformat())
        except OSError as e:
            decky.logger.error(f"Failed to save last-active timestamp: {e}")
