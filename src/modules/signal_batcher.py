from __future__ import annotations

"""
Signal batcher for FSSSignalDiscovered events.
Accumulates individual FSSSignalDiscovered journal events and batches them
into a single fsssignaldiscovered/1 EDDN message on flush triggers.

ED FSSSignalDiscovered events rarely include StarSystem/StarPos fields.
These are message-level fields required by the fsssignaldiscovered/1 schema,
so the batcher stores them from whatever source is available:
- From the signal event itself (rare but possible in older ED versions)
- From the parser's session_state during flush (preferred, always current)

When session_state has position data (populated by FSDJump/Location/CarrierJump),
the batch uses it. This ensures correct coordinates even when signals arrive
before system-position events in the journal order.
"""

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState

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
        self._reset()

    def _reset(self) -> None:
        """Clear every per-batch field, including the system metadata.

        StarSystem/StarPos/SystemAddress are latched from whichever signal
        first carries them, so they MUST NOT survive a flush: a later batch
        would otherwise keep a previous system's coordinates, skip the
        session_state augmentation (its guard only fires when position data
        is missing) and publish signals under the wrong system.
        """
        self._signals: list[dict] = []
        self._first_timestamp: str | None = None
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

        # Filter out mission target signals — these have no statistical value
        # and are only useful to the Cmdr with the active mission.
        if raw.get("USSType") == "$USS_Type_MissionTarget;":
            return

        # Extract signal data: keep everything except _Localised and
        # message-level fields. The gateway's own allow-list, applied at
        # transform time (`_project_allowed` in validator.py against
        # fsssignaldiscovered/1's `signals[]` allow-list), is what excludes
        # remaining unlisted fields (e.g. TimeRemaining, event) -- this loop
        # only needs to keep message-level fields out of the per-signal dict.
        signal: dict = {}
        for key, value in raw.items():
            if key in _MESSAGE_LEVEL_FIELDS:
                continue
            if key.endswith("_Localised"):
                continue
            signal[key] = value

        self._signals.append(signal)

        # Record the first signal's timestamp for the batch (per the
        # fsssignaldiscovered/1 README: the top-level timestamp duplicates
        # the first signal's, not the last). Stays stable until flush.
        if raw.get("timestamp") and self._first_timestamp is None:
            self._first_timestamp = raw["timestamp"]
        if raw.get("SystemAddress") is not None:
            self._system_address = raw["SystemAddress"]
        if raw.get("StarSystem"):
            self._star_system = raw["StarSystem"]
        if raw.get("StarPos") and isinstance(raw["StarPos"], list):
            self._star_pos = raw["StarPos"]

    def should_flush(self, event_type: str) -> bool:
        """Check if an incoming event should trigger a flush."""
        return event_type in self.FLUSH_TRIGGER_EVENTS

    def flush(self, session_state: SessionState | None = None) -> dict | None:
        """Return accumulated batch data for transform, or None if empty.

        Uses session_state to fill in StarSystem/StarPos when the batch
        doesn't have them from the signal events themselves. This is needed
        because ED FSSSignalDiscovered events rarely include StarSystem/StarPos,
        so the batcher relies on session_state (populated by FSDJump/Location/
        CarrierJump) to provide the required message-level coordinates.

        The SystemAddress from the signals is used to verify that session_state
        position data matches the correct star system. If SystemAddress doesn't
        match, the batch is discarded (signals from a system we no longer have
        coordinates for cannot be submitted with valid data).

        Returns dict with: signals, first_timestamp, system_address,
        star_system, star_pos. Clears all internal state, so the next batch
        derives its position solely from its own signals or from the
        session_state passed to its own flush.
        """
        if not self._signals:
            return None

        star_system = self._star_system
        star_pos = self._star_pos
        system_address = self._system_address

        # Augment from session_state if batch is missing position data.
        # FSSSignalDiscovered events rarely include StarSystem/StarPos,
        # so session_state (from a preceding FSDJump/Location/CarrierJump)
        # is the primary source.
        if session_state is not None and (not star_system or not star_pos):
            state_addr = session_state.system_address
            # Only use session_state if SystemAddress matches (prevents
            # stale coordinates from a different star system) or if the
            # batch has no SystemAddress at all
            if system_address is None or state_addr is None or system_address == state_addr:
                if not star_pos and session_state.star_pos:
                    star_pos = session_state.star_pos
                if not star_system and session_state.star_system:
                    star_system = session_state.star_system
                # SystemAddress is a required message field. A batch whose
                # signals never carried one takes it from the same
                # session_state the position came from, rather than emitting
                # null (real FSSSignalDiscovered events always carry it).
                if system_address is None and state_addr is not None:
                    system_address = state_addr

        # If we still don't have StarPos/StarSystem after augmentation,
        # discard the batch — we can't submit valid fsssignaldiscovered/1
        # messages without required positional data.
        if not star_pos or not star_system:
            self._reset()
            return None

        result = {
            "signals": self._signals,
            "first_timestamp": self._first_timestamp,
            "system_address": system_address,
            "star_system": star_system,
            "star_pos": star_pos,
        }
        self._reset()
        return result
