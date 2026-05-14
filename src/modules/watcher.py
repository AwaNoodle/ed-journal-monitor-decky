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
from src.modules.constants import AUXILIARY_FILES, DEDICATED_SCHEMA_EVENTS

if TYPE_CHECKING:
    from src.modules.parser import JournalParser, ParsedEvent
    from src.modules.settings import PluginSettings
    from src.modules.signal_batcher import SignalBatcher
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
        signal_batcher: SignalBatcher | None = None,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.validator = validator
        self.submitter = submitter
        self._signal_batcher = signal_batcher or self._create_batcher()
        self.is_running = False

        self._journal_path: str | None = None
        self._poll_interval: int = 10  # seconds
        self._poll_task: asyncio.Task | None = None
        self._file_positions: dict[str, int] = {}  # filepath -> last line number
        self._known_files: set[str] = set()

    @staticmethod
    def _create_batcher() -> SignalBatcher:
        from src.modules.signal_batcher import SignalBatcher  # noqa: PLC0415
        return SignalBatcher()

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
            try:
                await self._process_file(filepath)
            except Exception as e:
                # Per-file isolation: one bad file must not block others
                decky.logger.error(f"Error processing {filepath}: {e}")

    async def _process_file(self, filepath: str) -> None:
        """
        Process a journal file, reading only new lines from last position.

        Position is updated to the end of the file even if some events
        fail to process, to avoid duplicate submissions on the next poll.
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

        # Always update position to prevent reprocessing on next poll,
        # even if some events fail to process (avoids duplicate EDDN submissions).
        self._file_positions[filepath] = len(lines)

        for line in new_lines:
            try:
                event = self.parser.parse_line(line)
                if not event:
                    continue

                # Auto-detect commander name from LoadGame for uploader ID
                if event.event_type == "LoadGame" and self.parser.session_state.commander:
                    await decky.emit("commander_detected", {"commander": self.parser.session_state.commander})

                if self.parser.is_reportable(event):
                    await self._process_reportable_event(event, filepath)
            except Exception as e:
                # Per-event isolation: one bad event must not prevent
                # processing of subsequent events in the same file.
                decky.logger.error(f"Error processing event in {filepath}: {e}")

    async def _process_reportable_event(self, event: ParsedEvent, source_filepath: str | None = None) -> None:
        """Validate and submit a reportable event with schema-aware routing."""
        event_type = event.event_type

        # 1. FSSSignalDiscovered → batch (not immediate submit)
        if event_type == "FSSSignalDiscovered":
            self._signal_batcher.add_signal(event)
            return

        # 2. Check if this event should flush the signal batcher
        if self._signal_batcher.should_flush(event_type):
            batch = self._signal_batcher.flush(session_state=self.parser.session_state)
            if batch:
                message = self.validator.transform_fss_signal_discovered(batch, self.parser.session_state)
                if message:
                    await self._submit(message, event_name="FSSSignalDiscovered")

        # 3. Dedicated schema events (FSSDiscoveryScan, ApproachSettlement, CodexEntry)
        if event_type in DEDICATED_SCHEMA_EVENTS:
            await self._process_dedicated_schema_event(event)
            return

        # 4. Auxiliary file events (Market, Outfitting, Shipyard, NavRoute)
        if event_type in AUXILIARY_FILES:
            await self._process_auxiliary_event(event, source_filepath)
            return

        # 5. Journal/1 events (FSDJump, Scan, Location, Docked, CarrierJump, SAASignalsFound)
        validated = self.validator.validate(event, self.parser.session_state)
        if not validated:
            decky.logger.debug(f"Event validation failed: {event_type}")
            return
        message = self.validator.transform(event, self.parser.session_state)
        await self._submit(message)

    async def _process_dedicated_schema_event(self, event: ParsedEvent) -> None:
        """Process events with dedicated EDDN schemas (not journal/1)."""
        event_type = event.event_type
        validated = self.validator.validate(event, self.parser.session_state)
        if not validated:
            decky.logger.debug(f"Event validation failed: {event_type}")
            return

        # Dispatch to the appropriate transform method
        transform_dispatch = {
            "FSSDiscoveryScan": self.validator.transform_fss_discovery_scan,
            "ApproachSettlement": self.validator.transform_approach_settlement,
            "CodexEntry": self.validator.transform_codex_entry,
        }
        transformer = transform_dispatch.get(event_type)
        if transformer is None:
            decky.logger.debug(f"Unknown dedicated schema: {event_type}")
            return

        message = transformer(event, self.parser.session_state)
        if message:
            await self._submit(message, event_name=event_type)

    async def _process_auxiliary_event(self, event: ParsedEvent, source_filepath: str | None = None) -> None:
        """Process an event that requires an auxiliary JSON file."""
        auxiliary_info = AUXILIARY_FILES[event.event_type]
        auxiliary_filename = auxiliary_info["filename"]
        auxiliary_schema = auxiliary_info["schema"]

        auxiliary_data = await self._read_auxiliary_data(auxiliary_filename, source_filepath)
        if auxiliary_data is None:
            decky.logger.debug(f"Auxiliary file missing/invalid for {event.event_type}: {auxiliary_filename}")
            return

        if auxiliary_schema == "navroute":
            # NavRoute: transform directly using navroute/1 schema
            message = self.validator.transform_navroute(auxiliary_data, self.parser.session_state)
            if message is None:
                decky.logger.debug("NavRoute transform produced no data")
                return
            await self._submit(message, event_name=event.event_type)
            return

        # Other auxiliary schemas: use dedicated transform methods
        _, message = self._prepare_auxiliary_submission(event, auxiliary_data, auxiliary_schema)
        if message is None:
            return
        event_name_override = event.event_type
        await self._submit(message, event_name=event_name_override)

    async def _submit(self, message: dict, event_name: str | None = None) -> None:
        """Submit an EDDN message with game version info from session state."""
        await self.submitter.submit(
            message,
            event_name=event_name,
            game_version=self.parser.session_state.game_version,
            game_build=self.parser.session_state.game_build,
        )

    def _prepare_auxiliary_submission(
        self,
        event: ParsedEvent,
        auxiliary_data: dict,
        auxiliary_schema: str,
    ) -> tuple[ParsedEvent | None, dict | None]:
        """Prepare transformed message or replacement event for auxiliary-based events."""
        if auxiliary_schema == "journal":
            # Should no longer be used, but kept for safety
            auxiliary_timestamp = auxiliary_data.get("timestamp")
            if not auxiliary_timestamp:
                decky.logger.debug(f"{event.event_type} auxiliary data missing timestamp")
                return None, None
            return (
                type(event)(
                    raw=auxiliary_data,
                    event_type=event.event_type,
                    timestamp=auxiliary_timestamp,
                ),
                None,
            )

        # Non-journal auxiliary schemas: transform directly
        transformers = {
            "commodity": self.validator.transform_commodity,
            "outfitting": self.validator.transform_outfitting,
            "shipyard": self.validator.transform_shipyard,
        }
        transformer = transformers.get(auxiliary_schema)
        if transformer is None:
            decky.logger.debug(f"Unknown auxiliary schema: {auxiliary_schema}")
            return event, None

        message = transformer(auxiliary_data, self.parser.session_state)
        if message is None:
            decky.logger.debug(f"Auxiliary transform produced no data for {event.event_type}")
            return None, None
        return None, message

    async def _read_auxiliary_data(self, auxiliary_filename: str, source_filepath: str | None) -> dict | None:
        """Read an auxiliary JSON file from the journal directory.

        Elite Dangerous writes auxiliary files (Market.json, Outfitting.json,
        Shipyard.json, NavRoute.json) asynchronously after the corresponding
        journal event line appears.  We retry a few times with short delays
        so that we pick up the file once ED finishes writing it.
        """
        auxiliary_path = self._resolve_auxiliary_path(auxiliary_filename, source_filepath)
        if auxiliary_path is None:
            return None

        max_attempts = 5
        delay = 0.5  # seconds between attempts
        for attempt in range(max_attempts):
            data = self.parser.parse_auxiliary_file(str(auxiliary_path))
            if data is not None:
                return data
            if attempt < max_attempts - 1:
                decky.logger.debug(
                    f"Auxiliary file {auxiliary_filename} not available yet, "
                    f"retry {attempt + 1}/{max_attempts}"
                )
                await asyncio.sleep(delay)

        decky.logger.info(f"Auxiliary file {auxiliary_filename} still missing after {max_attempts} attempts")
        return None

    def _resolve_auxiliary_path(self, auxiliary_filename: str, source_filepath: str | None) -> Path | None:
        """Resolve an auxiliary filename to a full path in the journal directory."""
        if source_filepath:
            return Path(source_filepath).parent / auxiliary_filename
        if self._journal_path:
            return Path(self._journal_path) / auxiliary_filename
        return None

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
