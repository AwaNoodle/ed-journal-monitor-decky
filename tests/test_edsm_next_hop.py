"""Tests for next-in-route hop derivation (pure logic).

Covers:
- Mid-route next hop derived after the current system
- Final hop → no next hop
- No / empty route → no next hop
- Off-route current system → no next hop
- Advance-after-jump: the next hop follows the current system forward
- Scoopability from the route's StarClass (KGB FOAM)
- Matching the current system by SystemAddress (robust against name edge cases)
"""
from __future__ import annotations

import pytest

from src.modules.edsm_next_hop import (
    REASON_FINAL_HOP,
    REASON_HOP,
    REASON_NO_ROUTE,
    REASON_OFF_ROUTE,
    NextHopTracker,
    is_scoopable,
)


def _route() -> list[dict]:
    return [
        {"StarSystem": "Sol", "SystemAddress": 10477373803, "StarClass": "G"},
        {"StarSystem": "Alpha Centauri", "SystemAddress": 55230754, "StarClass": "B"},
        {"StarSystem": "Barnard's Star", "SystemAddress": 9530, "StarClass": "M"},
        {"StarSystem": "Wolf 359", "SystemAddress": 33347, "StarClass": "N"},
    ]


class TestNextHopDerivation:
    def test_mid_route_next_hop(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        hop, reason = tracker.next_hop("Sol")
        assert hop is not None
        assert hop.system == "Alpha Centauri"
        assert hop.system_address == 55230754
        assert hop.star_class == "B"
        assert hop.scoopable is True
        assert reason == REASON_HOP

    def test_final_hop_has_no_next(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        hop, reason = tracker.next_hop("Wolf 359")
        assert hop is None
        assert reason == REASON_FINAL_HOP

    def test_no_route(self):
        tracker = NextHopTracker()
        hop, reason = tracker.next_hop("Sol")
        assert hop is None
        assert reason == REASON_NO_ROUTE
        assert tracker.has_route is False

    def test_empty_route(self):
        tracker = NextHopTracker()
        tracker.set_route([])
        hop, reason = tracker.next_hop("Sol")
        assert hop is None
        assert reason == REASON_NO_ROUTE

    def test_off_route_current_system(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        hop, reason = tracker.next_hop("Betelgeuse")
        assert hop is None
        assert reason == REASON_OFF_ROUTE

    def test_advance_after_jump(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        assert tracker.next_hop("Sol")[0].system == "Alpha Centauri"
        # Player jumps to Alpha Centauri; the next hop advances.
        assert tracker.next_hop("Alpha Centauri")[0].system == "Barnard's Star"
        # And again.
        assert tracker.next_hop("Barnard's Star")[0].system == "Wolf 359"

    def test_next_hop_carries_non_scoopable_star(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        hop, _reason = tracker.next_hop("Barnard's Star")  # next is Wolf 359, class N
        assert hop.system == "Wolf 359"
        assert hop.scoopable is False

    def test_match_by_system_address(self):
        # Two systems share a name but not an address; address wins.
        tracker = NextHopTracker()
        tracker.set_route([
            {"StarSystem": "Dupe", "SystemAddress": 1, "StarClass": "G"},
            {"StarSystem": "Second", "SystemAddress": 2, "StarClass": "K"},
            {"StarSystem": "Dupe", "SystemAddress": 3, "StarClass": "M"},
        ])
        hop, _reason = tracker.next_hop("Dupe", current_address=1)
        assert hop.system == "Second"

    def test_clear_forgets_route(self):
        tracker = NextHopTracker()
        tracker.set_route(_route())
        tracker.clear()
        hop, reason = tracker.next_hop("Sol")
        assert hop is None
        assert reason == REASON_NO_ROUTE
        assert tracker.has_route is False

    def test_set_route_ignores_non_dict_entries(self):
        tracker = NextHopTracker()
        tracker.set_route([{"StarSystem": "Sol"}, "garbage", None, {"StarSystem": "Next"}])
        assert tracker.next_hop("Sol")[0].system == "Next"


class TestScoopability:
    @pytest.mark.parametrize("star_class", list("KGBFOAM"))
    def test_scoopable_classes(self, star_class):
        assert is_scoopable(star_class) is True

    @pytest.mark.parametrize("star_class", ["N", "D", "DA", "H", "TTS", "L", "T", "Y", "W"])
    def test_non_scoopable_classes(self, star_class):
        assert is_scoopable(star_class) is False

    def test_unknown_star_class_is_none(self):
        assert is_scoopable("") is None
        assert is_scoopable(None) is None

    def test_case_and_whitespace_insensitive(self):
        assert is_scoopable(" g ") is True
