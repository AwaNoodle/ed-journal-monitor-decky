"""
Next-in-route hop derivation from a plotted NavRoute.

Pure logic — no I/O.  Given the plotted route (the ``Route`` array from
NavRoute.json) and the player's current system, determine the *next* system in
the route and its primary-star scoopability.

Scoopability is derived from the plotted route's ``StarClass`` (the fuel-scoop
classes are the "KGB FOAM" set), which the game already provides per hop — no
lookup needed.  The EDSM per-system read (worth-scanning verdict / value) is
layered on separately by the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fuel-scoopable primary-star classes (the "KGB FOAM" mnemonic).
SCOOPABLE_CLASSES = frozenset("KGBFOAM")

# Reason discriminators for the "no next hop" state, returned alongside a
# ``None`` hop so a permanent UI block can state which condition applies.
REASON_HOP = "hop"
REASON_NO_ROUTE = "no_route"
REASON_FINAL_HOP = "final_hop"
REASON_OFF_ROUTE = "off_route"


def is_scoopable(star_class: str | None) -> bool | None:
    """Whether a primary star of ``star_class`` is fuel-scoopable.

    Returns True/False when the class is known, or None when it is unknown
    (empty/missing) so the caller can render a neutral state rather than a
    misleading "not scoopable".
    """
    if not star_class:
        return None
    return star_class.strip()[:1].upper() in SCOOPABLE_CLASSES


@dataclass
class NextHop:
    """The next system in the plotted route, relative to the current system."""

    system: str
    system_address: int | None = None
    star_class: str | None = None
    scoopable: bool | None = None


class NextHopTracker:
    """Tracks the plotted route and derives the next hop from the current system.

    The route is the ordered ``Route`` array from NavRoute.json; each entry
    carries ``StarSystem`` / ``SystemAddress`` / ``StarClass``.  The "next hop"
    is the entry immediately after the current system.  The current system is
    matched by ``SystemAddress`` first (robust against name edge cases), then by
    name.
    """

    def __init__(self) -> None:
        self._route: list[dict] = []

    def set_route(self, route: list[dict] | None) -> None:
        """Replace the tracked route (from a NavRoute update)."""
        self._route = [entry for entry in (route or []) if isinstance(entry, dict)]

    def clear(self) -> None:
        """Forget the route (e.g. NavRouteClear or a new session)."""
        self._route = []

    @property
    def has_route(self) -> bool:
        return bool(self._route)

    def next_hop(
        self, current_system: str, current_address: int | None = None,
    ) -> tuple[NextHop | None, str]:
        """Return the next hop after the current system, alongside a reason.

        The hop is ``None`` when there is no route, the current system is not
        on the route (off-route), or the current system is the final hop; the
        accompanying reason (``REASON_NO_ROUTE`` / ``REASON_OFF_ROUTE`` /
        ``REASON_FINAL_HOP``) identifies which. When a hop exists, the reason
        is ``REASON_HOP``.
        """
        if not self._route:
            return None, REASON_NO_ROUTE
        index = self._current_index(current_system, current_address)
        if index is None:
            return None, REASON_OFF_ROUTE
        if index + 1 >= len(self._route):
            return None, REASON_FINAL_HOP
        entry = self._route[index + 1]
        star_class = entry.get("StarClass")
        hop = NextHop(
            system=entry.get("StarSystem", "") or "",
            system_address=entry.get("SystemAddress"),
            star_class=star_class,
            scoopable=is_scoopable(star_class),
        )
        return hop, REASON_HOP

    def _current_index(self, current_system: str, current_address: int | None) -> int | None:
        """Index of the current system in the route, by address then by name."""
        if current_address is not None:
            for i, entry in enumerate(self._route):
                if entry.get("SystemAddress") == current_address:
                    return i
        if current_system:
            for i, entry in enumerate(self._route):
                if entry.get("StarSystem") == current_system:
                    return i
        return None
