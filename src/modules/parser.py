from __future__ import annotations

"""
Journal parser.
Parses Elite Dangerous journal JSON lines and filters EDDN-reportable events.
"""

import json
import stat
from dataclasses import dataclass
from pathlib import Path

import decky
from src.modules.constants import (
    MAX_AUXILIARY_FILE_BYTES,
    MAX_COMMANDER_NAME_LENGTH,
    REPORTABLE_EVENTS,
)


@dataclass
class SessionState:
    """Tracks state from the current ED session (LoadGame/Fileheader)."""
    horizons: bool | None = None
    odyssey: bool | None = None
    game_version: str = ""
    game_build: str = ""
    commander: str = ""
    star_pos: list[float] | None = None
    system_address: int | None = None
    star_system: str = ""
    # Current body tracked from ApproachBody/Location/CarrierJump journal
    # events; cleared on LeaveBody/FSDJump/Fileheader, left untouched by
    # SupercruiseEntry. Set by JournalParser.parse_line() -- see
    # codexentry-README.md's "BodyID and BodyName" section (issue #39).
    journal_body_name: str = ""
    journal_body_id: int | None = None
    # Populated by JournalWatcher (not the parser) from Status.json
    # immediately before a CodexEntry transform -- the one externally-set
    # SessionState field. See status_reader.py.
    status_body_name: str | None = None


@dataclass
class ParsedEvent:
    """A parsed journal event with metadata."""
    raw: dict
    event_type: str
    timestamp: str


def is_parseable_sidecar(path: Path) -> bool:
    """Whether ``path`` is a regular file small enough to parse in-process.

    Anything else -- a directory, a FIFO, a device node, a file above
    MAX_AUXILIARY_FILE_BYTES, or a path that cannot be stat()ed at all --
    is refused before it is opened: the watched directory is only assumed
    to be where Elite writes its sidecars, never that everything in it is
    one. Shared with status_reader.py, which guards Status.json the same
    way.
    """
    try:
        st = path.stat()
    except OSError:
        return False

    if not stat.S_ISREG(st.st_mode):
        decky.logger.debug(f"Refusing to parse non-regular file {path}")
        return False

    if st.st_size > MAX_AUXILIARY_FILE_BYTES:
        decky.logger.debug(
            f"Refusing to parse {path}: {st.st_size} bytes exceeds "
            f"the {MAX_AUXILIARY_FILE_BYTES}-byte auxiliary file limit"
        )
        return False

    return True


def _is_plausible_commander(value: object) -> bool:
    """Whether a journal ``Commander`` value may become the EDDN uploaderID."""
    return isinstance(value, str) and 0 < len(value.strip()) <= MAX_COMMANDER_NAME_LENGTH


class JournalParser:
    """Parses Elite Dangerous journal lines and filters reportable events."""

    def __init__(self) -> None:
        self.session_state = SessionState()

    def parse_line(self, line: str) -> ParsedEvent | None:
        """
        Parse a single journal line.
        Returns ParsedEvent or None if the line is invalid/empty.
        """
        trimmed = line.strip()
        if not trimmed:
            return None

        try:
            data = json.loads(trimmed)
        except json.JSONDecodeError:
            return None

        timestamp = data.get("timestamp")
        event_type = data.get("event")

        if not timestamp or not event_type:
            return None

        # Handle special events that update session state
        if event_type == "Fileheader":
            self._handle_fileheader(data)
            self._clear_journal_body()
            return ParsedEvent(raw=data, event_type=event_type, timestamp=timestamp)

        if event_type == "LoadGame":
            self._handle_loadgame(data)
            return ParsedEvent(raw=data, event_type=event_type, timestamp=timestamp)

        # Cache star position from events that contain it
        if event_type in ("Location", "FSDJump", "CarrierJump"):
            self._update_star_pos(data)

        # Track the current body (codexentry-README.md's "BodyID and
        # BodyName" section, issue #39). SupercruiseEntry deliberately does
        # NOT clear: a player can re-descend without a fresh ApproachBody.
        if event_type in ("ApproachBody", "Location", "CarrierJump"):
            self._update_journal_body(data)
        elif event_type in ("LeaveBody", "FSDJump"):
            self._clear_journal_body()

        return ParsedEvent(raw=data, event_type=event_type, timestamp=timestamp)

    def is_reportable(self, event: ParsedEvent) -> bool:
        """Check if an event should be reported to EDDN."""
        return event.event_type in REPORTABLE_EVENTS

    def parse_auxiliary_file(self, filepath: str) -> dict | None:
        """Parse an auxiliary JSON file (Market/Outfitting/Shipyard/NavRoute).

        Returns None on any failure -- the watcher's retry loop depends on
        that contract, so nothing here may raise.

        The watched directory is only assumed to be where Elite writes its
        sidecars, never that everything in it is one, so the path is
        stat()ed before it is opened: anything that is not a regular file
        (a FIFO would block the plugin's single event loop on open) or is
        larger than MAX_AUXILIARY_FILE_BYTES is refused unparsed. Real
        sidecars are a few hundred KB.
        """
        path = Path(filepath)
        if not is_parseable_sidecar(path):
            return None

        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        return data

    def _handle_fileheader(self, data: dict) -> None:
        """Extract game version from Fileheader event."""
        self.session_state.game_version = data.get("gameversion", "")
        self.session_state.game_build = data.get("build", "")

    def _handle_loadgame(self, data: dict) -> None:
        """Extract commander name, horizons/odyssey flags from LoadGame event.

        Only set horizons/odyssey when the LoadGame event actually carries the
        key: EDDN requires omitting them entirely when unknown, never guessing.

        The commander name becomes the public EDDN ``uploaderID``, so it is
        accepted only as a plausible name -- a str of 1..
        MAX_COMMANDER_NAME_LENGTH non-blank characters. Anything else (a
        planted journal's dict, list, or multi-MB string) leaves the
        previously known commander in place. The accepted value is stored
        verbatim, never trimmed: it must reach EDDN exactly as Elite wrote
        it.
        """
        if "Horizons" in data:
            self.session_state.horizons = data.get("Horizons")
        if "Odyssey" in data:
            self.session_state.odyssey = data.get("Odyssey")
        commander = data.get("Commander", "")
        if _is_plausible_commander(commander):
            self.session_state.commander = commander
        elif commander:
            decky.logger.debug(
                f"LoadGame Commander rejected (type {type(commander).__name__}); "
                "keeping the previous commander name"
            )

    def _update_journal_body(self, data: dict) -> None:
        """Track the current body from ApproachBody/Location/CarrierJump.

        The journal key is ``Body``, not ``BodyName`` -- the README names
        the concept, the game writes ``Body``. Fall back to ``BodyName`` in
        case a future game version renames it. A missing body key leaves
        the tracked state untouched (e.g. Location at a station).
        """
        body_name = data.get("Body", data.get("BodyName"))
        if body_name:
            self.session_state.journal_body_name = body_name
        body_id = data.get("BodyID")
        if body_id is not None:
            self.session_state.journal_body_id = body_id

    def _clear_journal_body(self) -> None:
        """Clear the tracked body (LeaveBody, FSDJump, or a new session)."""
        self.session_state.journal_body_name = ""
        self.session_state.journal_body_id = None

    def _update_star_pos(self, data: dict) -> None:
        """Cache star position from events that contain it (Location, FSDJump, CarrierJump)."""
        star_pos = data.get("StarPos")
        if star_pos and isinstance(star_pos, list):
            self.session_state.star_pos = star_pos
        system_address = data.get("SystemAddress")
        if system_address is not None:
            self.session_state.system_address = system_address
        star_system = data.get("StarSystem")
        if star_system:
            self.session_state.star_system = star_system
