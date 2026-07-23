"""Tests for the nearest-scoopable-star computation (pure logic).

Covers:
- Nearest scoopable system found among a mix of scoopable/non-scoopable
- The current system itself is excluded (it's returned by EDSM at distance 0)
- None found when no candidate is confirmed-scoopable
- Entries with missing/empty primaryStar data are treated as unknown, not scoopable
- Malformed entries (non-dict, missing fields) are skipped rather than raising
"""
from __future__ import annotations

from src.modules.edsm_nearest_scoopable import find_nearest_scoopable


def _entry(name: str, distance: float, star_type: str | None, scoopable: bool | None) -> dict:
    primary_star = {} if star_type is None else {"type": star_type, "isScoopable": scoopable}
    return {"name": name, "distance": distance, "primaryStar": primary_star}


class TestNearestScoopableFound:
    def test_picks_closest_scoopable_candidate(self):
        systems = [
            _entry("Sol", 0, "G (White-Yellow) Star", True),
            _entry("WISE 1506+7027", 10.52, "T (Brown dwarf) Star", False),
            _entry("Ross 154", 9.69, "M (Red dwarf) Star", True),
            _entry("Barnard's Star", 5.95, "M (Red dwarf) Star", True),
        ]

        result = find_nearest_scoopable(systems, current_system="Sol")

        assert result is not None
        assert result.system == "Barnard's Star"
        assert result.distance == 5.95
        assert result.star_class == "M (Red dwarf) Star"

    def test_excludes_current_system_even_though_scoopable(self):
        systems = [
            _entry("Sol", 0, "G (White-Yellow) Star", True),
            _entry("Tau Ceti", 11.94, "G (White-Yellow) Star", True),
        ]

        result = find_nearest_scoopable(systems, current_system="Sol")

        assert result is not None
        assert result.system == "Tau Ceti"

    def test_current_system_match_is_case_insensitive(self):
        systems = [
            _entry("sol", 0, "G (White-Yellow) Star", True),
            _entry("Tau Ceti", 11.94, "G (White-Yellow) Star", True),
        ]

        result = find_nearest_scoopable(systems, current_system="Sol")

        assert result is not None
        assert result.system == "Tau Ceti"


class TestNoneFound:
    def test_no_scoopable_candidates_returns_none(self):
        systems = [
            _entry("Sol", 0, "G (White-Yellow) Star", True),
            _entry("WISE 1506+7027", 10.52, "T (Brown dwarf) Star", False),
            _entry("van Maanen's Star", 13.91, "White Dwarf (D) Star", False),
        ]

        assert find_nearest_scoopable(systems, current_system="Sol") is None

    def test_empty_systems_list_returns_none(self):
        assert find_nearest_scoopable([], current_system="Sol") is None

    def test_unknown_primary_star_is_not_scoopable(self):
        """An empty primaryStar dict (EDSM has no data) must not count as scoopable."""
        systems = [_entry("AssetViewerSystem", 2, None, None)]

        assert find_nearest_scoopable(systems, current_system="Sol") is None


class TestMalformedEntries:
    def test_non_dict_entries_are_skipped(self):
        systems = ["not a dict", _entry("Tau Ceti", 11.94, "G (White-Yellow) Star", True)]

        result = find_nearest_scoopable(systems, current_system="Sol")

        assert result is not None
        assert result.system == "Tau Ceti"

    def test_missing_distance_is_skipped(self):
        systems = [{"name": "Tau Ceti", "primaryStar": {"type": "G", "isScoopable": True}}]

        assert find_nearest_scoopable(systems, current_system="Sol") is None

    def test_missing_name_is_skipped(self):
        systems = [{"distance": 5, "primaryStar": {"type": "G", "isScoopable": True}}]

        assert find_nearest_scoopable(systems, current_system="Sol") is None
