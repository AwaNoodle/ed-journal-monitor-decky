"""
System value summary derivation from EDSM estimated-value data.

Derives a compact summary — total estimated scan value plus a ranked list of
the highest-value "priority" bodies — from a raw ``SystemValueResult``.

The total is EDSM's scan-only ``estimatedValue`` (not ``estimatedValueMapped``):
it is a floor, since it excludes any mapping bonus and in particular the
player's own first-mapped bonus, which EDSM cannot know in advance.

Neutral (``None``) for anything other than a known system with data: disabled,
in-flight, failed, or a system EDSM has never seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.edsm_read_client import SystemValueResult

from src.modules.edsm_read_client import STATUS_OK

DEFAULT_TOP_N = 3


@dataclass
class SystemValueSummary:
    """Compact, frontend-ready system value summary."""

    total_value: int
    priority_bodies: list[dict] = field(default_factory=list)  # [{"name": str, "value": int}, ...]


def derive_value_summary(
    result: SystemValueResult | None, top_n: int = DEFAULT_TOP_N,
) -> SystemValueSummary | None:
    """Derive a system value summary from an EDSM estimated-value result.

    Returns None (neutral) unless the result is a known system with data.
    """
    if result is None or result.status != STATUS_OK:
        return None

    ranked = sorted(
        result.valuable_bodies,
        key=lambda b: b.get("valueMax") or 0,
        reverse=True,
    )
    priority_bodies = [
        {"name": b.get("bodyName", ""), "value": int(b.get("valueMax") or 0)}
        for b in ranked[:top_n]
    ]

    return SystemValueSummary(
        total_value=result.total_value or 0,
        priority_bodies=priority_bodies,
    )
