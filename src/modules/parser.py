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
    horizons: bool = True
    odyssey: bool = True
    game_version: str = ""
    game_build: str = ""
    commander: str = ""


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
            return ParsedEvent(raw=data, event_type=event_type, timestamp=timestamp)

        if event_type == "LoadGame":
            self._handle_loadgame(data)
            return ParsedEvent(raw=data, event_type=event_type, timestamp=timestamp)

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
        """Extract commander name, horizons/odyssey flags from LoadGame event."""
        self.session_state.horizons = data.get("Horizons", True)
        self.session_state.odyssey = data.get("Odyssey", True)
        commander = data.get("Commander", "")
        if commander:
            self.session_state.commander = commander
