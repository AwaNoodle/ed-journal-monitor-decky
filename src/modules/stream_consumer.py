from __future__ import annotations

"""
Stream consumer protocol.

A thin seam over the parsed journal event stream. The watcher fans every
parsed event out to each registered consumer before the EDDN reportable
filter, so consumers (e.g. the session-stats accumulator, a future EDSM
forwarder) observe the raw stream without entangling with EDDN routing.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState


@runtime_checkable
class StreamConsumer(Protocol):
    """Observes every parsed journal event before EDDN routing."""

    def observe(self, event: ParsedEvent, session_state: SessionState) -> None:
        """Handle a single parsed event. Must not raise or block EDDN routing."""
        ...
