"""
On-demand nearest-scoopable-star lookup.

Given the current system, runs a bounded-radius EDSM sphere-systems query and
returns the closest system with a confirmed-scoopable primary star. This is a
user-initiated (button-triggered) lookup, not part of the per-arrival
``observe()`` stream — it does not share the per-arrival system cache, since a
radius query is point-in-time and only needed when the player asks for it.

Gated by the same ``edsm_lookups_enabled`` toggle as the other EDSM read
features; the caller passes the current toggle value and current system so
this stays pure request/response with no consumer-protocol state of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.modules.edsm_nearest_scoopable import find_nearest_scoopable
from src.modules.edsm_read_client import STATUS_UNAVAILABLE as SPHERE_UNAVAILABLE

if TYPE_CHECKING:
    from src.modules.edsm_read_client import EdsmReadClient

STATUS_OK = "ok"
STATUS_NONE_FOUND = "none_found"
STATUS_UNAVAILABLE = "unavailable"
STATUS_DISABLED = "disabled"


@dataclass
class NearestScoopableLookupResult:
    """Result of an on-demand nearest-scoopable-star lookup."""

    status: str  # STATUS_OK | STATUS_NONE_FOUND | STATUS_UNAVAILABLE | STATUS_DISABLED
    system: str | None = None
    distance: float | None = None
    star_class: str | None = None


def lookup_nearest_scoopable(
    read_client: EdsmReadClient,
    current_system: str,
    lookups_enabled: bool,
    radius: int | None = None,
) -> NearestScoopableLookupResult:
    """Run the on-demand nearest-scoopable-star lookup.

    Synchronous — performs a blocking network call via the read client;
    callers running under asyncio should offload it to an executor.

    A sphere query that reports the current system as unknown to EDSM is
    folded into "none found": there's no data to identify a nearby scoopable
    star, which reads the same as a searched-and-found-nothing result to the
    player, rather than a distinct error state.
    """
    if not lookups_enabled:
        return NearestScoopableLookupResult(status=STATUS_DISABLED)
    if not current_system:
        return NearestScoopableLookupResult(status=STATUS_UNAVAILABLE)

    if radius is None:
        result = read_client.get_sphere_systems(current_system)
    else:
        result = read_client.get_sphere_systems(current_system, radius=radius)

    if result.status == SPHERE_UNAVAILABLE:
        return NearestScoopableLookupResult(status=STATUS_UNAVAILABLE)

    nearest = find_nearest_scoopable(result.systems, current_system)
    if nearest is None:
        return NearestScoopableLookupResult(status=STATUS_NONE_FOUND)
    return NearestScoopableLookupResult(
        status=STATUS_OK,
        system=nearest.system,
        distance=nearest.distance,
        star_class=nearest.star_class,
    )
