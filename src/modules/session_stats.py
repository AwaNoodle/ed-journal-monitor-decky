from __future__ import annotations

"""
Session stats accumulator.

Observes the parsed journal event stream in parallel to EDDN routing and
maintains player-facing running totals for the current ED game launch
(current system/commander, jumps, distance, bodies scanned, first discoveries).

The accumulator does not touch, gate, or depend on the EDDN submission path.
"""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState

# Events whose StarSystem updates the displayed current system without
# necessarily counting as a jump.
_LOCATION_EVENTS = ("Location", "CarrierJump")


@dataclass
class SessionStats:
    """Running totals for a single ED game launch."""

    commander: str = ""
    star_system: str = ""
    jumps: int = 0
    distance_ly: float = 0.0
    bodies_scanned: int = 0
    first_discoveries: int = 0


class SessionStatsAccumulator:
    """Accumulates session stats from the parsed journal event stream.

    Satisfies the StreamConsumer protocol: ``observe(event, session_state)``.
    Emits via an optional ``on_change`` callback whenever the stats change,
    with suspend/resume support to coalesce a burst of changes (e.g. the
    watcher's initial-scan replay) into a single settled emit.
    """

    def __init__(self, on_change: Callable[[dict], None] | None = None) -> None:
        self.stats = SessionStats()
        self.on_change = on_change
        self._suspended = False
        self._dirty = False

    def observe(self, event: ParsedEvent, session_state: SessionState | None = None) -> None:  # noqa: ARG002
        """Observe a parsed event and update running totals.

        ``session_state`` is accepted for the StreamConsumer protocol but is
        unused here — everything needed is read off the event itself.
        """
        event_type = event.event_type
        changed = False

        if event_type == "FSDJump":
            changed = self._observe_jump(event)
        elif event_type == "Scan":
            changed = self._observe_scan(event)
        elif event_type == "LoadGame":
            changed = self._observe_loadgame(event)
        elif event_type in _LOCATION_EVENTS:
            changed = self._observe_location(event)

        if changed:
            self._notify()

    def reset(self) -> None:
        """Zero all counters (new game launch) and emit the reset state."""
        self.stats = SessionStats()
        self._notify()

    def get_stats(self) -> dict:
        """Return a snapshot of the current stats as a plain dict."""
        return asdict(self.stats)

    def suspend(self) -> None:
        """Defer emits; changes are coalesced until ``resume``."""
        self._suspended = True

    def resume(self) -> None:
        """Resume emits, firing a single settled emit if anything changed."""
        self._suspended = False
        if self._dirty:
            self._dirty = False
            self._emit()

    # --- internal ---

    def _observe_jump(self, event: ParsedEvent) -> bool:
        self.stats.jumps += 1
        jump_dist = event.raw.get("JumpDist")
        if isinstance(jump_dist, (int, float)) and not isinstance(jump_dist, bool):
            self.stats.distance_ly += jump_dist
        star_system = event.raw.get("StarSystem")
        if star_system:
            self.stats.star_system = star_system
        return True

    def _observe_scan(self, event: ParsedEvent) -> bool:
        self.stats.bodies_scanned += 1
        # Missing WasDiscovered is treated as not-first.
        if event.raw.get("WasDiscovered") is False:
            self.stats.first_discoveries += 1
        return True

    def _observe_loadgame(self, event: ParsedEvent) -> bool:
        commander = event.raw.get("Commander", "")
        if not commander:
            return False
        if self.stats.commander and commander != self.stats.commander:
            # Soft reset: a different commander started a session.
            self.stats = SessionStats(commander=commander)
            return True
        if commander != self.stats.commander:
            # First commander seen this session.
            self.stats.commander = commander
            return True
        # Same-commander relog/mode switch: preserve stats, no change.
        return False

    def _observe_location(self, event: ParsedEvent) -> bool:
        star_system = event.raw.get("StarSystem")
        if star_system and star_system != self.stats.star_system:
            self.stats.star_system = star_system
            return True
        return False

    def _notify(self) -> None:
        if self._suspended:
            self._dirty = True
        else:
            self._emit()

    def _emit(self) -> None:
        if self.on_change is not None:
            self.on_change(self.get_stats())
