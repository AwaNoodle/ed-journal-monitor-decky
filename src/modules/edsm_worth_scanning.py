from __future__ import annotations

"""
Worth-scanning verdict derivation from EDSM body data.

Three verdicts:
  - "green"  — system unknown to EDSM (high-confidence virgin), or no discovered bodies
  - "yellow" — EDSM has data but system is not fully explored
  - "red"    — all bodies EDSM knows are discovered (len(bodies) == bodyCount)
  - None     — neutral: lookup disabled, in-flight, or failed

Source caveat: EDSM only reflects uploaded body data.  The verdict is labelled
as EDSM-sourced and is not ground truth — bodies EDSM doesn't know about are
invisible to this verdict.

EDSM API notes (confirmed 2026-07-06):
  - ``bodies``: list of body dicts that have been FSS-scanned and submitted
  - ``bodyCount``: total bodies per honk-scan (may be None if not submitted)
  - Discovery status per body: ``discovery`` dict present → discovered
  - No ``isMapped`` / ``mapped`` field exists on this endpoint
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.edsm_read_client import SystemBodiesResult

from src.modules.edsm_read_client import STATUS_OK, STATUS_UNKNOWN

_GREEN = "green"
_YELLOW = "yellow"
_RED = "red"


def _bodies_verdict(bodies: list[dict], body_count: int | None) -> str:
    """Compute green/yellow/red given a non-empty bodies list."""
    discovered = sum(1 for b in bodies if b.get("discovery"))
    if discovered == 0:
        return _GREEN

    total_submitted = len(bodies)
    if body_count is not None and body_count > 0:
        # Full coverage: all expected bodies are discovered
        if total_submitted == body_count == discovered:
            return _RED
        return _YELLOW

    # No honk-count → can't confirm completeness; any partial is yellow
    return _YELLOW


def derive_verdict(result: SystemBodiesResult | None) -> str | None:
    """Derive a worth-scanning verdict from an EDSM system-bodies result.

    Returns "green", "yellow", "red", or None (neutral).
    """
    if result is None or result.status not in (STATUS_OK, STATUS_UNKNOWN):
        return None

    if result.status == STATUS_UNKNOWN:
        return _GREEN

    if not result.bodies:
        return _GREEN

    return _bodies_verdict(result.bodies, result.body_count)
