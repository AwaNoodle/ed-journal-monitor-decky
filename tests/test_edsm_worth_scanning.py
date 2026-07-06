"""Tests for the worth-scanning verdict derivation.

Covers all verdict states (green/yellow/red) from body-list fixtures, plus the
neutral/None state for disabled/in-flight/failed lookups.

EDSM field names confirmed against live API (2026-07-06):
  - ``discovery``: dict {commander, date} if body was FSS-scanned; absent = not discovered
  - ``bodyCount``: total bodies per honk scan (int or None)
  - Verdict logic: len(bodies)==0 → green; all==bodyCount → red; partial → yellow
"""
from __future__ import annotations

from src.modules.edsm_read_client import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    SystemBodiesResult,
)
from src.modules.edsm_worth_scanning import derive_verdict

DISCOVERY = {"commander": "CmdrTest", "date": "2026-01-01 00:00:00"}


def _body(discovered: bool) -> dict:
    b = {"id": 1, "name": "Body", "type": "Planet"}
    if discovered:
        b["discovery"] = DISCOVERY
    return b


def _ok(bodies: list[dict], body_count: int | None = None, infer_count: bool = True) -> SystemBodiesResult:
    """Build an OK result. body_count defaults to len(bodies) unless body_count is
    explicitly passed or infer_count=False (to test the no-body_count path)."""
    bc = body_count if (body_count is not None or not infer_count) else len(bodies)
    return SystemBodiesResult(
        status=STATUS_OK,
        system_name="Test System",
        bodies=bodies,
        body_count=bc,
    )


class TestGreenVerdict:
    def test_unknown_system_is_green(self):
        result = SystemBodiesResult(status=STATUS_UNKNOWN, system_name="Virgin System")
        assert derive_verdict(result) == "green"

    def test_system_with_no_bodies_and_zero_body_count_is_green(self):
        result = _ok([], body_count=0)
        assert derive_verdict(result) == "green"

    def test_system_with_no_bodies_and_none_body_count_is_green(self):
        """No body data at all → treat as unexplored (green)."""
        result = _ok([], body_count=None)
        assert derive_verdict(result) == "green"

    def test_all_bodies_undiscovered_is_green(self):
        """Bodies in EDSM but none with discovery data → green."""
        bodies = [_body(discovered=False), _body(discovered=False)]
        result = _ok(bodies, body_count=2)
        assert derive_verdict(result) == "green"


class TestYellowVerdict:
    def test_partial_discovery_is_yellow(self):
        """Some bodies discovered, some not → yellow."""
        bodies = [_body(discovered=True), _body(discovered=False)]
        result = _ok(bodies, body_count=2)
        assert derive_verdict(result) == "yellow"

    def test_fewer_bodies_than_body_count_is_yellow(self):
        """EDSM knows fewer bodies than the system scan suggests → undiscovered exist → yellow."""
        bodies = [_body(discovered=True)]
        result = _ok(bodies, body_count=5)
        assert derive_verdict(result) == "yellow"

    def test_some_bodies_known_no_body_count_is_yellow(self):
        """Bodies submitted but no honk-count to confirm completion → yellow (uncertain)."""
        bodies = [_body(discovered=True)]
        result = _ok(bodies, infer_count=False)  # body_count=None
        assert derive_verdict(result) == "yellow"


class TestRedVerdict:
    def test_all_bodies_discovered_and_count_matches_is_red(self):
        bodies = [_body(discovered=True), _body(discovered=True), _body(discovered=True)]
        result = _ok(bodies, body_count=3)
        assert derive_verdict(result) == "red"

    def test_single_discovered_body_matching_count_is_red(self):
        bodies = [_body(discovered=True)]
        result = _ok(bodies, body_count=1)
        assert derive_verdict(result) == "red"


class TestNeutralVerdict:
    def test_unavailable_is_neutral(self):
        result = SystemBodiesResult(status=STATUS_UNAVAILABLE, system_name="Sol")
        assert derive_verdict(result) is None

    def test_none_result_is_neutral(self):
        """Passing None (in-flight or disabled) produces neutral."""
        assert derive_verdict(None) is None


class TestFixtureBodies:
    """Verify verdict logic against the real Wolf 359 fixture (all 3 bodies discovered)."""

    def test_wolf_359_fixture_is_red(self, load_fixture):
        data = load_fixture("edsm_bodies_known.json")
        result = SystemBodiesResult(
            status=STATUS_OK,
            system_name="Wolf 359",
            bodies=data["bodies"],
            body_count=data["bodyCount"],
        )
        assert derive_verdict(result) == "red"
