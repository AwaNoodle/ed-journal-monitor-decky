"""
Nearest-scoopable-star computation from an EDSM sphere-systems result.

Pure logic — no I/O.  Given the raw system entries returned by a
sphere-systems query (each carrying ``name``, ``distance``, and a
``primaryStar`` dict with ``isScoopable``/``type``, as confirmed against a
live EDSM response — see ``edsm_read_client``), find the closest system
(other than the current one) whose primary star is fuel-scoopable.

Unlike route-derived scoopability (``edsm_next_hop.is_scoopable``, which
infers from a single-letter ``StarClass`` code), EDSM's sphere-systems
endpoint already reports ``isScoopable`` directly, so it is used as-is rather
than re-derived.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NearestScoopable:
    """The closest scoopable-primary-star system found within a sphere query."""

    system: str
    distance: float
    star_class: str


def find_nearest_scoopable(
    systems: list[dict], current_system: str,
) -> NearestScoopable | None:
    """Return the closest scoopable system other than ``current_system``.

    Returns None when no candidate has a confirmed-scoopable primary star
    (e.g. sparse coverage, or all non-scoopable/unknown within the queried
    systems).
    """
    current = (current_system or "").strip().lower()
    best: NearestScoopable | None = None
    for entry in systems:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or ""
        if not name or name.strip().lower() == current:
            continue
        distance = entry.get("distance")
        if not isinstance(distance, (int, float)):
            continue
        primary_star = entry.get("primaryStar")
        if not isinstance(primary_star, dict) or primary_star.get("isScoopable") is not True:
            continue
        if best is None or distance < best.distance:
            best = NearestScoopable(
                system=name, distance=float(distance), star_class=primary_star.get("type") or "",
            )
    return best
