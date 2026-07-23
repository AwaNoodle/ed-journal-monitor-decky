"""Tests for the on-demand nearest-scoopable-star lookup orchestration.

Covers:
- Disabled toggle short-circuits: no EDSM request made
- No known current system: no request made, reported as unavailable
- Found: nearest scoopable system/distance/class returned
- None found within radius (sphere query ok, no scoopable candidate)
- Sphere query reports the current system as unknown to EDSM -> folded into
  "none found" (there's no data to identify a nearby scoopable star, which
  reads the same as none-found to the player)
- Sphere query genuinely unavailable (network/timeout/malformed) -> unavailable
- A custom radius is forwarded to the read client
"""
from __future__ import annotations

from unittest.mock import MagicMock

from src.modules.edsm_nearest_scoopable_lookup import (
    STATUS_DISABLED,
    STATUS_NONE_FOUND,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    lookup_nearest_scoopable,
)
from src.modules.edsm_read_client import STATUS_OK as SPHERE_OK
from src.modules.edsm_read_client import STATUS_UNAVAILABLE as SPHERE_UNAVAILABLE
from src.modules.edsm_read_client import STATUS_UNKNOWN as SPHERE_UNKNOWN
from src.modules.edsm_read_client import SphereSystemsResult


def _sphere(status: str, systems: list[dict] | None = None) -> SphereSystemsResult:
    return SphereSystemsResult(status=status, system_name="Sol", radius=25, systems=systems or [])


class TestDisabled:
    def test_disabled_makes_no_request(self):
        client = MagicMock()

        result = lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=False)

        assert result.status == STATUS_DISABLED
        client.get_sphere_systems.assert_not_called()


class TestNoCurrentSystem:
    def test_unknown_current_system_makes_no_request(self):
        client = MagicMock()

        result = lookup_nearest_scoopable(client, current_system="", lookups_enabled=True)

        assert result.status == STATUS_UNAVAILABLE
        client.get_sphere_systems.assert_not_called()


class TestFound:
    def test_returns_nearest_scoopable_system(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_OK, systems=[
            {"name": "Sol", "distance": 0, "primaryStar": {"type": "G", "isScoopable": True}},
            {
                "name": "Barnard's Star", "distance": 5.95,
                "primaryStar": {"type": "M (Red dwarf) Star", "isScoopable": True},
            },
        ])

        result = lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=True)

        assert result.status == STATUS_OK
        assert result.system == "Barnard's Star"
        assert result.distance == 5.95
        assert result.star_class == "M (Red dwarf) Star"


class TestNoneFound:
    def test_no_scoopable_candidate_in_radius(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_OK, systems=[
            {"name": "Sol", "distance": 0, "primaryStar": {"type": "G", "isScoopable": True}},
            {"name": "WISE 1506+7027", "distance": 10.52, "primaryStar": {"type": "T", "isScoopable": False}},
        ])

        result = lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=True)

        assert result.status == STATUS_NONE_FOUND
        assert result.system is None

    def test_current_system_unknown_to_edsm_is_none_found(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_UNKNOWN)

        result = lookup_nearest_scoopable(client, current_system="Newly Discovered", lookups_enabled=True)

        assert result.status == STATUS_NONE_FOUND


class TestUnavailable:
    def test_sphere_query_failure_is_unavailable(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_UNAVAILABLE)

        result = lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=True)

        assert result.status == STATUS_UNAVAILABLE


class TestRadius:
    def test_custom_radius_is_forwarded(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_OK)

        lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=True, radius=10)

        client.get_sphere_systems.assert_called_once_with("Sol", radius=10)

    def test_default_radius_uses_client_default(self):
        client = MagicMock()
        client.get_sphere_systems.return_value = _sphere(SPHERE_OK)

        lookup_nearest_scoopable(client, current_system="Sol", lookups_enabled=True)

        client.get_sphere_systems.assert_called_once_with("Sol")
