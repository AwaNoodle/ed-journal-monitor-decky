from __future__ import annotations

"""
Journal parser.
Parses Elite Dangerous journal JSON lines and filters EDDN-reportable events.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.modules.constants import REPORTABLE_EVENTS


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
        """Parse an auxiliary JSON file (Market/Outfitting/Shipyard/NavRoute)."""
        try:
            with Path(filepath).open(encoding="utf-8", errors="replace") as f:
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
        """
        if "Horizons" in data:
            self.session_state.horizons = data.get("Horizons")
        if "Odyssey" in data:
            self.session_state.odyssey = data.get("Odyssey")
        commander = data.get("Commander", "")
        if commander:
            self.session_state.commander = commander

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
