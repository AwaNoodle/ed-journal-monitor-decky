from __future__ import annotations

"""
Signal batcher for FSSSignalDiscovered events.
Accumulates individual FSSSignalDiscovered journal events and batches them
into a single fsssignaldiscovered/1 EDDN message on flush triggers.
"""

from typing import TYPE_CHECKING, ClassVar

from src.modules.constants import FSS_SIGNAL_DISALLOWED_FIELDS

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent

# Fields that belong at message level, not in individual signals
_MESSAGE_LEVEL_FIELDS = {"StarSystem", "StarPos", "SystemAddress"}


class SignalBatcher:
    """Batches FSSSignalDiscovered events and flushes on trigger events."""

    FLUSH_TRIGGER_EVENTS: ClassVar[set[str]] = {
        "FSSDiscoveryScan",
        "SupercruiseEntry",
        "Location",
        "FSDJump",
        "CarrierJump",
        "Shutdown",
        "Music",
    }

    def __init__(self) -> None:
        self._signals: list[dict] = []
        self._last_timestamp: str | None = None
        self._system_address: int | None = None
        self._star_system: str | None = None
        self._star_pos: list[float] | None = None

    def add_signal(self, event: ParsedEvent) -> None:
        """Add a FSSSignalDiscovered event to the batch.

        Extracts signal-level fields from event.raw, stripping disallowed
        fields, _Localised keys, and message-level fields.
        Updates metadata (timestamp, system info) from the event.
        """
        raw = event.raw

        # Extract signal data: keep everything except disallowed, _Localised,
        # and message-level fields
        signal: dict = {}
        for key, value in raw.items():
            if key in FSS_SIGNAL_DISALLOWED_FIELDS:
                continue
            if key in _MESSAGE_LEVEL_FIELDS:
                continue
            if key.endswith("_Localised"):
                continue
            signal[key] = value

        self._signals.append(signal)

        # Update metadata from the event
        if raw.get("timestamp"):
            self._last_timestamp = raw["timestamp"]
        if raw.get("SystemAddress") is not None:
            self._system_address = raw["SystemAddress"]
        if raw.get("StarSystem"):
            self._star_system = raw["StarSystem"]
        if raw.get("StarPos") and isinstance(raw["StarPos"], list):
            self._star_pos = raw["StarPos"]

    def should_flush(self, event_type: str) -> bool:
        """Check if an incoming event should trigger a flush."""
        return event_type in self.FLUSH_TRIGGER_EVENTS

    def flush(self) -> dict | None:
        """Return accumulated batch data for transform, or None if empty.

        Returns dict with: signals, last_timestamp, system_address,
        star_system, star_pos. Clears internal state.
        """
        if not self._signals:
            return None
        result = {
            "signals": self._signals,
            "last_timestamp": self._last_timestamp,
            "system_address": self._system_address,
            "star_system": self._star_system,
            "star_pos": self._star_pos,
        }
        self._signals = []
        self._last_timestamp = None
        return result
