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
    """Observes every parsed journal event before EDDN routing.

    Beyond ``observe``, consumers expose lifecycle hooks and per-target stats so
    ``main.py`` can drive them generically:

    - ``name``: a stable target key (e.g. ``"eddn"``, ``"edsm"``) under which
      this consumer's stats are reported.
    - ``get_stats()``: a snapshot of this consumer's stats as a plain dict.
    - ``on_session_start()``: called when ED transitions to running (new launch).
    - ``on_session_stop()``: called when the watcher stops (e.g. forced flush).
    """

    name: str

    def observe(self, event: ParsedEvent, session_state: SessionState) -> None:
        """Handle a single parsed event. Must not raise or block EDDN routing."""
        ...

    def get_stats(self) -> dict:
        """Return a snapshot of this consumer's stats as a plain dict."""
        ...

    def on_session_start(self) -> None:
        """Called when ED starts a new session (reset per-session state)."""
        ...

    def on_session_stop(self) -> None:
        """Called when the watcher stops (e.g. flush any buffered work)."""
        ...
