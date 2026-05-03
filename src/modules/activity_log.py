from __future__ import annotations

"""
Activity log module.
Tracks recent upload attempts (success/failure) in a circular buffer.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Any

import decky

MAX_ENTRIES = 50


class ActivityLog:
    """In-memory circular buffer of recent upload activity entries."""

    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_entries)

    async def record_success(self, event_type: str) -> None:
        """Record a successful upload and emit activity_update."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "outcome": "success",
            "error_type": None,
            "error_message": None,
            "http_status": None,
        }
        self._entries.append(entry)
        await decky.emit("activity_update", entry)

    async def record_failure(
        self,
        event_type: str,
        error_type: str,
        error_message: str,
        http_status: int | None = None,
    ) -> None:
        """Record a failed upload and emit activity_update."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "outcome": "failure",
            "error_type": error_type,
            "error_message": error_message,
            "http_status": http_status,
        }
        self._entries.append(entry)
        await decky.emit("activity_update", entry)

    def get_recent(self, limit: int = 50, outcome: str | None = None) -> list[dict[str, Any]]:
        """Return recent entries newest-first, optionally filtered by outcome."""
        entries = list(self._entries)
        if outcome is not None:
            entries = [e for e in entries if e["outcome"] == outcome]
        # Return newest first
        entries.reverse()
        return entries[:limit]
