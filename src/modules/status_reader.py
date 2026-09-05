from __future__ import annotations

"""
Status.json reader.

Elite Dangerous rewrites Status.json many times per second while the
commander is in flight, non-atomically -- a read can land mid-write and fail
to parse. Read only when a CodexEntry is being processed (see
codexentry-README.md's "BodyID and BodyName" section), never on every poll
cycle: see design.md's "Read Status.json on demand" decision.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import decky
from src.modules.constants import STATUS_BODY_MAX_SKEW_SECONDS, STATUS_JSON_FILENAME

_RETRY_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 0.1


async def read_status_body_name(journal_dir: str, event_timestamp: str) -> str | None:
    """Read the current ``BodyName`` from Status.json, gated by timestamp skew.

    Returns ``None`` -- never raises -- for every failure mode: missing or
    unreadable file, non-dict JSON, a missing/unparseable ``timestamp``, an
    empty or non-string ``BodyName``, or a ``Status.json`` timestamp more
    than ``STATUS_BODY_MAX_SKEW_SECONDS`` away from ``event_timestamp`` in
    either direction (catch-up replay, a stalled poll, resume-from-suspend).
    """
    status_path = Path(journal_dir) / STATUS_JSON_FILENAME

    data = await _read_with_retry(status_path)
    if data is None:
        return None

    body_name = data.get("BodyName")
    if not isinstance(body_name, str) or not body_name:
        decky.logger.debug("Status.json has no usable BodyName")
        return None

    status_dt = _parse_iso_timestamp(data.get("timestamp"))
    event_dt = _parse_iso_timestamp(event_timestamp)
    if status_dt is None or event_dt is None:
        decky.logger.debug("Status.json or event timestamp missing/unparseable")
        return None

    skew = abs((status_dt - event_dt).total_seconds())
    if skew > STATUS_BODY_MAX_SKEW_SECONDS:
        decky.logger.debug(f"Status.json timestamp skew {skew:.1f}s exceeds freshness window")
        return None

    return body_name


async def _read_with_retry(status_path: Path) -> dict | None:
    """Read and parse Status.json, retrying on torn reads (see module docstring)."""
    for attempt in range(_RETRY_ATTEMPTS):
        data = _try_read(status_path)
        if data is not None:
            return data
        if attempt < _RETRY_ATTEMPTS - 1:
            await asyncio.sleep(_RETRY_DELAY_SECONDS)

    decky.logger.debug(f"Status.json unreadable after {_RETRY_ATTEMPTS} attempts")
    return None


def _try_read(status_path: Path) -> dict | None:
    try:
        with status_path.open(encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    return data


def _parse_iso_timestamp(value: object) -> datetime | None:
    """Parse a journal/Status.json ISO timestamp as an aware datetime.

    Both files write UTC (``...Z``), so a value that carries no offset is
    read as UTC rather than left naive: subtracting a naive datetime from an
    aware one raises ``TypeError``, which would drop the codex entry
    entirely instead of submitting it without body keys.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
