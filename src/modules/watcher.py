from __future__ import annotations

"""
Journal watcher.
Polls the ED journal directory for new/changed files and processes events.
"""

import asyncio
import contextlib
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import decky
from src.modules.constants import (
    AUXILIARY_FILES,
    DEDICATED_SCHEMA_EVENTS,
    JOURNAL_READ_CHUNK_BYTES,
    MAX_JOURNAL_FILE_BYTES,
)
from src.modules.status_reader import read_status_body_name

if TYPE_CHECKING:
    from src.modules.parser import JournalParser, ParsedEvent
    from src.modules.settings import PluginSettings
    from src.modules.signal_batcher import SignalBatcher
    from src.modules.stream_consumer import StreamConsumer
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
        consumers: list[StreamConsumer] | None = None,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.validator = validator
        self.submitter = submitter
        self._signal_batcher = signal_batcher or self._create_batcher()
        # Stream consumers observe every parsed event before EDDN routing.
        self._consumers: list[StreamConsumer] = consumers or []
        self.is_running = False

        self._journal_path: str | None = None
        self._poll_interval: int = 10  # seconds
        self._poll_task: asyncio.Task | None = None
        # filepath -> byte offset of the first byte not yet dispatched
        self._file_positions: dict[str, int] = {}
        self._known_files: set[str] = set()
        # filepath -> reason it was last skipped, so a rejected directory entry
        # is logged once per reason instead of once per poll.
        self._skip_reasons: dict[str, str] = {}
        # True while start() is between its guard and its poll task, so a
        # concurrent start() cannot run a second scan while is_running is
        # still false; _stop_requested records a stop() that arrived in that
        # window.
        self._starting = False
        self._stop_requested = False

    @staticmethod
    def _create_batcher() -> SignalBatcher:
        from src.modules.signal_batcher import SignalBatcher  # noqa: PLC0415
        return SignalBatcher()

    async def start(self, journal_path: str) -> None:
        """Start the polling watcher."""
        if self.is_running or self._starting:
            return

        if not self.settings.get("enabled", True):
            decky.logger.info("Monitor is disabled, not starting watcher")
            return

        self._starting = True
        self._stop_requested = False
        try:
            self._journal_path = journal_path
            self._poll_interval = self.settings.get("poll_interval", 10)

            # Load persisted last-active timestamp for catch-up
            last_active = self._load_last_active()

            # Initial scan: process files from catch-up or current date.
            # A failing scan must not abort startup -- the poll loop is what
            # keeps the plugin alive, and it can recover on the next cycle.
            try:
                await self._initial_scan(last_active)
            except Exception as e:
                decky.logger.error(f"Initial journal scan failed: {e}")

            if self._stop_requested:
                # stop() arrived while the scan was awaiting: honour it rather
                # than leaving a poll loop nobody asked for.
                decky.logger.info("Journal watcher stopped during initial scan")
                return

            # Start periodic polling. is_running only becomes true once the
            # poll task exists, so no reader (UI status, diagnostics) can ever
            # see "monitoring" with nothing running.
            self._poll_task = asyncio.create_task(self._poll_loop())
            self.is_running = True
        finally:
            self._starting = False
        decky.logger.info(f"Journal watcher started on {journal_path}")

    async def stop(self) -> None:
        """Stop the watcher and persist state."""
        if self._starting:
            self._stop_requested = True
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
        """Process journal files on watcher start for catch-up.

        On first run (no last_active), processes the MOST RECENT journal file
        to capture Fileheader/LoadGame session state (game version, commander,
        horizons/odyssey flags), then tracks all other files for position only.
        On catch-up (with last_active), processes files modified after the
        last-active timestamp.
        """
        journal_dir = Path(self._journal_path)
        if not journal_dir.is_dir():
            return

        log_files = self._discover_log_files(journal_dir)

        if not log_files:
            return

        # Coalesce consumer emits during the replay burst so the panel sees
        # one settled value instead of flickering through every replayed event.
        self._suspend_consumers()
        try:
            await self._replay_initial_scan(log_files, last_active)
        finally:
            self._resume_consumers()

    async def _replay_initial_scan(self, log_files: list[Path], last_active: str | None) -> None:
        """Replay journal files on watcher start (see _initial_scan).

        Per-file isolation: a file that disappears mid-scan or carries an
        out-of-range mtime is skipped, never allowed to abort startup.

        A stop() that arrives while the replay is awaiting abandons the
        remaining files: a catch-up replay is long-lived (sidecar retries, real
        EDDN submissions), and stop_watcher/set_enabled(false) has already told
        the user uploading has ceased.
        """
        newest = log_files[-1]
        for log_file in log_files:
            if self._stop_requested:
                decky.logger.info("Initial scan interrupted by stop request")
                return
            try:
                await self._replay_one(log_file, last_active, is_newest=log_file == newest)
            except (OSError, ValueError, OverflowError) as e:
                decky.logger.warning(f"Initial scan skipping {log_file.name}: {e}")

    async def _replay_one(self, log_file: Path, last_active: str | None, is_newest: bool) -> None:
        """Replay a single journal file during the initial scan."""
        if last_active:
            # Catch-up: process files modified after last-active timestamp
            file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
            try:
                last_active_dt = datetime.fromisoformat(last_active)
            except ValueError:
                last_active_dt = None
            if last_active_dt is not None and file_mtime < last_active_dt:
                # File hasn't been modified since last session, skip
                # But still track it for position
                self._track_file_position(str(log_file))
                return
            await self._process_file(str(log_file))
        elif is_newest:
            # First run: process ONLY the most recent file to capture
            # Fileheader/LoadGame session state (game version, commander,
            # horizons/odyssey). Older files' events would be stale, but
            # the most recent file's Fileheader is essential for session
            # state that affects all subsequent submissions (game_version,
            # game_build, horizons, odyssey).
            await self._process_file(str(log_file))
        else:
            # First run: older files are not processed, but track their
            # position so the poll loop knows we've seen them.
            self._track_file_position(str(log_file))

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

        for log_file in self._discover_log_files(journal_dir):
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

    def _discover_log_files(self, journal_dir: Path) -> list[Path]:
        """Name-matched journal files that are safe to open.

        The watched directory is user-settable (the Steam library scan reaches
        removable media), so a name match alone is not enough: anything that is
        not a regular file of plausible size is rejected before it can be
        opened. A FIFO would otherwise block open() forever, on the single
        asyncio loop the whole plugin runs on.
        """
        return [p for p in sorted(journal_dir.glob("Journal*.log")) if self._is_usable_journal(p)]

    def _is_usable_journal(self, path: Path) -> bool:
        """Stat guard: regular file (symlinks followed) within the size cap."""
        filepath = str(path)
        try:
            info = path.stat()
        except OSError as e:
            self._log_skip(filepath, "unstattable", f"Skipping {path.name}: cannot stat it ({e})")
            return False

        if not stat.S_ISREG(info.st_mode):
            self._log_skip(filepath, "not-regular", f"Skipping {path.name}: not a regular file")
            return False

        if info.st_size > MAX_JOURNAL_FILE_BYTES:
            self._log_skip(
                filepath,
                "too-large",
                f"Skipping {path.name}: {info.st_size} bytes exceeds the "
                f"{MAX_JOURNAL_FILE_BYTES} byte journal limit",
            )
            return False

        self._skip_reasons.pop(filepath, None)
        return True

    def _log_skip(self, filepath: str, reason: str, message: str) -> None:
        """Warn about a skipped entry once per path per reason, not per poll."""
        if self._skip_reasons.get(filepath) == reason:
            return
        self._skip_reasons[filepath] = reason
        decky.logger.warning(message)

    async def _process_file(self, filepath: str) -> None:
        """
        Process a journal file, reading only new bytes from the last position.

        The read runs in a worker thread so pathological I/O cannot wedge the
        event loop, is capped at JOURNAL_READ_CHUNK_BYTES per poll, and yields
        only newline-terminated lines -- a partially written trailing line is
        left for the next poll instead of being parsed half-formed.

        The stored offset advances past every byte handed to the parser even if
        some events fail to process, to avoid duplicate submissions on the next
        poll. A stop() requested during the initial scan abandons the rest of
        the file for the same reason the replay loop abandons the rest of the
        scan: one catch-up file can be large and every reportable event awaits
        a real submission. The abandoned lines are covered by the stored offset
        and are not re-read on the next start -- the same forward-only contract
        a failed event already has.
        """
        loop = asyncio.get_running_loop()
        try:
            text, new_position = await loop.run_in_executor(None, self._read_new_lines, filepath)
        except OSError as e:
            decky.logger.error(f"Failed to read {filepath}: {e}")
            return

        self._file_positions[filepath] = new_position

        if not text:
            return

        self._known_files.add(filepath)

        # text always ends in the final newline consumed, so the trailing
        # split element is the empty remainder and never a real line.
        for line in text.split("\n")[:-1]:
            if self._stop_requested:
                decky.logger.info(f"Abandoning the rest of {Path(filepath).name}: stop requested")
                return
            try:
                event = self.parser.parse_line(line)
                if not event:
                    continue

                # Fan every parsed event out to stream consumers (session
                # stats, future EDSM forwarder) BEFORE the EDDN reportable
                # filter, so they see non-reportable events (e.g. LoadGame)
                # and never gate or alter EDDN routing.
                self._fan_out(event)

                # Auto-detect commander name from LoadGame for uploader ID
                if event.event_type == "LoadGame" and self.parser.session_state.commander:
                    await decky.emit("commander_detected", {"commander": self.parser.session_state.commander})

                if self.parser.is_reportable(event):
                    await self._process_reportable_event(event, filepath)
            except Exception as e:
                # Per-event isolation: one bad event must not prevent
                # processing of subsequent events in the same file.
                decky.logger.error(f"Error processing event in {filepath}: {e}")

    def _read_new_lines(self, filepath: str) -> tuple[str, int]:
        """Read complete new lines from the stored offset. Runs in a thread.

        Returns the decoded text (empty, or ending in a newline) plus the byte
        offset to store. OSError propagates to the caller, which logs it.
        """
        position = self._file_positions.get(filepath, 0)
        with Path(filepath).open("rb") as f:
            size = os.fstat(f.fileno()).st_size
            if size < position:
                # Rotated or truncated in place: start over from the top.
                decky.logger.info(
                    f"{Path(filepath).name} shrank to {size} bytes (was at {position}), re-reading from the start"
                )
                position = 0
            if size <= position:
                return "", position
            f.seek(position)
            chunk = f.read(JOURNAL_READ_CHUNK_BYTES)

        if not chunk:
            return "", position

        last_newline = chunk.rfind(b"\n")
        if last_newline < 0:
            if len(chunk) < JOURNAL_READ_CHUNK_BYTES:
                # A line ED is still writing: leave the offset where it is and
                # pick the line up complete on the next poll.
                return "", position
            # A full chunk with no line break at all is not a journal line.
            # Discard it and move on -- never re-read the same bytes forever.
            decky.logger.warning(
                f"Discarding {len(chunk)} bytes without a line break in {Path(filepath).name}"
            )
            return "", position + len(chunk)

        consumed = last_newline + 1
        # A newline byte never occurs inside a multi-byte UTF-8 sequence, so
        # cutting the chunk here can never split a character.
        return chunk[:consumed].decode("utf-8", errors="replace"), position + consumed

    def _suspend_consumers(self) -> None:
        """Pause emit on consumers that support coalescing (e.g. session stats)."""
        for consumer in self._consumers:
            suspend = getattr(consumer, "suspend", None)
            if callable(suspend):
                suspend()

    def _resume_consumers(self) -> None:
        """Resume consumers, flushing a single settled emit each."""
        for consumer in self._consumers:
            resume = getattr(consumer, "resume", None)
            if callable(resume):
                resume()

    def _fan_out(self, event: ParsedEvent) -> None:
        """Deliver a parsed event to every registered stream consumer.

        Per-consumer isolation: a misbehaving consumer must not block other
        consumers or the EDDN submission path.
        """
        for consumer in self._consumers:
            try:
                consumer.observe(event, self.parser.session_state)
            except Exception as e:
                decky.logger.error(f"Stream consumer error on {event.event_type}: {e}")

    def _fan_out_nav_route(self, auxiliary_data: dict) -> None:
        """Deliver the plotted route to consumers implementing ``on_nav_route``.

        NavRoute.json holds the ordered ``Route`` array; ``NavRouteClear`` content
        means the route was cleared (delivered as an empty route). Per-consumer
        isolation, same as ``_fan_out``.
        """
        if auxiliary_data.get("event") == "NavRouteClear":
            route: list = []
        else:
            route = auxiliary_data.get("Route")
            if not isinstance(route, list):
                route = []
        for consumer in self._consumers:
            hook = getattr(consumer, "on_nav_route", None)
            if callable(hook):
                try:
                    hook(route)
                except Exception as e:
                    decky.logger.error(f"Consumer on_nav_route error: {e}")

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
            await self._process_dedicated_schema_event(event, source_filepath)
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

    async def _process_dedicated_schema_event(self, event: ParsedEvent, source_filepath: str | None = None) -> None:
        """Process events with dedicated EDDN schemas (not journal/1)."""
        event_type = event.event_type
        validated = self.validator.validate(event, self.parser.session_state)
        if not validated:
            decky.logger.debug(f"Event validation failed: {event_type}")
            return

        # Read Status.json's current BodyName on demand, only for CodexEntry
        # (the only schema the README ties to Status.json) -- never on every
        # poll cycle. See design.md's "Read Status.json on demand" decision.
        if event_type == "CodexEntry":
            await self._refresh_status_body_name(event, source_filepath)

        # Dispatch to the appropriate transform method
        transform_dispatch = {
            "FSSDiscoveryScan": self.validator.transform_fss_discovery_scan,
            "ApproachSettlement": self.validator.transform_approach_settlement,
            "CodexEntry": self.validator.transform_codex_entry,
            "NavBeaconScan": self.validator.transform_navbeacon_scan,
            "FSSAllBodiesFound": self.validator.transform_fss_all_bodies_found,
            "ScanBaryCentre": self.validator.transform_scan_bary_centre,
            "FSSBodySignals": self.validator.transform_fss_body_signals,
            "DockingGranted": self.validator.transform_docking_granted,
            "DockingDenied": self.validator.transform_docking_denied,
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
            # Feed the plotted route to route-aware consumers (next-hop preview)
            # before EDDN routing — independent of whether it is EDDN-submittable.
            self._fan_out_nav_route(auxiliary_data)
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
            "fcmaterials": self.validator.transform_fc_materials,
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

    async def _refresh_status_body_name(self, event: ParsedEvent, source_filepath: str | None) -> None:
        """Set session_state.status_body_name from Status.json before a
        CodexEntry transform. read_status_body_name() never raises -- every
        failure mode (missing file, stale timestamp, torn read exhausted)
        resolves to None, which the transform gate treats as unavailable
        without blocking submission of the rest of the message.
        """
        journal_dir = self._resolve_journal_dir(source_filepath)
        if journal_dir is None:
            self.parser.session_state.status_body_name = None
            return
        self.parser.session_state.status_body_name = await read_status_body_name(journal_dir, event.timestamp)

    def _resolve_journal_dir(self, source_filepath: str | None) -> str | None:
        """Resolve the journal directory Status.json lives in."""
        if source_filepath:
            return str(Path(source_filepath).parent)
        if self._journal_path:
            return self._journal_path
        return None

    def _track_file_position(self, filepath: str) -> None:
        """Track a file's byte offset without reading it (catch-up skipping)."""
        try:
            self._file_positions[filepath] = Path(filepath).stat().st_size
        except OSError:
            return
        self._known_files.add(filepath)

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
