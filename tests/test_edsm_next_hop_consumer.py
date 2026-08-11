"""Tests for the EdsmNextHopConsumer (next-in-route hop preview).

Covers:
- Preview produced for the next hop: scoopability (+ verdict, + value when available)
- Cache reuse for the next system (no network when cached)
- Neutral states: disabled toggle, no next hop (final/off-route/no route)
- Scoopability survives an EDSM lookup failure (verdict/value neutral, chip kept)
- Non-blocking: observe()/on_nav_route() never raise
- Preview advances after a jump
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from conftest import MockSettings

from src.modules.edsm_next_hop import REASON_FINAL_HOP, REASON_HOP, REASON_NO_ROUTE, REASON_OFF_ROUTE
from src.modules.edsm_next_hop_consumer import EdsmNextHopConsumer
from src.modules.edsm_read_client import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    SystemBodiesResult,
    SystemValueResult,
)
from src.modules.edsm_system_cache import SystemLookupCache
from src.modules.parser import ParsedEvent


def _event(event_type: str, system: str, address: int | None = None) -> ParsedEvent:
    raw = {"event": event_type, "StarSystem": system, "timestamp": "2026-01-01T00:00:00Z"}
    if address is not None:
        raw["SystemAddress"] = address
    return ParsedEvent(raw=raw, event_type=event_type, timestamp="2026-01-01T00:00:00Z")


def _route() -> list[dict]:
    return [
        {"StarSystem": "Sol", "SystemAddress": 10477373803, "StarClass": "G"},
        {"StarSystem": "Alpha Centauri", "SystemAddress": 55230754, "StarClass": "B"},
        {"StarSystem": "Wolf 359", "SystemAddress": 33347, "StarClass": "N"},
    ]


def _make(client=None, cache=None, enabled=True):
    """Build a consumer with a capture callback; returns (consumer, captured)."""
    captured: list[dict] = []
    settings = MockSettings(initial_data={"edsm_lookups_enabled": enabled})
    consumer = EdsmNextHopConsumer(
        settings=settings,
        read_client=client or MagicMock(),
        cache=cache,
        on_next_hop=captured.append,
    )
    return consumer, captured


class TestPreviewProduced:
    def test_preview_has_scoopability_and_verdict(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="Alpha Centauri",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNKNOWN, system_name="Alpha Centauri",
        )
        consumer, captured = _make(client=client)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        assert len(captured) == 1
        payload = captured[-1]
        assert payload["system"] == "Alpha Centauri"
        assert payload["scoopable"] is True  # class B
        assert payload["starClass"] == "B"
        assert payload["verdict"] == "green"  # unknown system → worth scanning
        assert payload["source"] == "edsm"
        assert payload["totalValue"] is None
        assert payload["priorityBodies"] == []
        assert payload["reason"] == REASON_HOP

    def test_preview_includes_value_when_available(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_OK, system_name="Alpha Centauri", bodies=[], body_count=0,
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_OK,
            system_name="Alpha Centauri",
            total_value=1_500_000,
            valuable_bodies=[{"bodyName": "AC 1", "valueMax": 900_000}],
        )
        consumer, captured = _make(client=client)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        payload = captured[-1]
        assert payload["totalValue"] == 1_500_000
        assert payload["priorityBodies"] == [{"name": "AC 1", "value": 900_000}]


class TestCacheReuse:
    def test_next_hop_uses_cache_without_network(self):
        cache = SystemLookupCache()
        cache.set("Alpha Centauri", SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="Alpha Centauri",
        ))
        cache.set_value("Alpha Centauri", SystemValueResult(
            status=STATUS_UNKNOWN, system_name="Alpha Centauri",
        ))
        client = MagicMock()
        consumer, captured = _make(client=client, cache=cache)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        client.get_system_bodies.assert_not_called()
        client.get_estimated_value.assert_not_called()
        assert captured[-1]["system"] == "Alpha Centauri"
        assert captured[-1]["verdict"] == "green"


class TestNeutralStates:
    def test_disabled_toggle_emits_nothing(self):
        client = MagicMock()
        consumer, captured = _make(client=client, enabled=False)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        assert captured == []
        client.get_system_bodies.assert_not_called()

    def test_no_route_emits_neutral(self):
        consumer, captured = _make()
        consumer.observe(_event("FSDJump", "Sol"))
        assert len(captured) == 1
        assert captured[-1]["system"] is None
        assert captured[-1]["scoopable"] is None
        assert captured[-1]["verdict"] is None
        assert captured[-1]["reason"] == REASON_NO_ROUTE

    def test_final_hop_emits_neutral(self):
        consumer, captured = _make()
        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Wolf 359"))  # final hop
        assert captured[-1]["system"] is None
        assert captured[-1]["reason"] == REASON_FINAL_HOP

    def test_off_route_emits_neutral(self):
        consumer, captured = _make()
        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Betelgeuse"))
        assert captured[-1]["system"] is None
        assert captured[-1]["reason"] == REASON_OFF_ROUTE

    def test_repeated_neutral_not_re_emitted(self):
        consumer, captured = _make()
        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Wolf 359"))
        consumer.observe(_event("Location", "Wolf 359"))
        assert len(captured) == 1  # only one neutral emit


class TestFailureKeepsScoopability:
    def test_edsm_failure_keeps_scoopability_neutral_verdict(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNAVAILABLE, system_name="Alpha Centauri",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNAVAILABLE, system_name="Alpha Centauri",
        )
        consumer, captured = _make(client=client)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        payload = captured[-1]
        assert payload["system"] == "Alpha Centauri"
        assert payload["scoopable"] is True  # from the route, survives EDSM outage
        assert payload["verdict"] is None
        assert payload["totalValue"] is None

    def test_unavailable_result_not_cached(self):
        cache = SystemLookupCache()
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNAVAILABLE, system_name="Alpha Centauri",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNAVAILABLE, system_name="Alpha Centauri",
        )
        consumer, _ = _make(client=client, cache=cache)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))

        assert cache.get("Alpha Centauri") is None
        assert cache.get_value("Alpha Centauri") is None


class TestAdvanceAfterJump:
    def test_preview_advances_on_jump(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        consumer, captured = _make(client=client)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))
        consumer.observe(_event("FSDJump", "Alpha Centauri"))

        assert [p["system"] for p in captured] == ["Alpha Centauri", "Wolf 359"]

    def test_same_hop_not_re_looked_up(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        consumer, captured = _make(client=client)

        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))
        consumer.observe(_event("Location", "Sol"))  # same current → same hop

        assert len(captured) == 1


class TestNonBlocking:
    def test_observe_never_raises(self):
        consumer, _ = _make()
        consumer._reevaluate = lambda: (_ for _ in ()).throw(Exception("boom"))
        try:
            consumer.observe(_event("FSDJump", "Sol"))
        except Exception:
            pytest.fail("observe() propagated an exception")

    def test_on_nav_route_never_raises(self):
        consumer, _ = _make()
        consumer._reevaluate = lambda: (_ for _ in ()).throw(Exception("boom"))
        try:
            consumer.on_nav_route(_route())
        except Exception:
            pytest.fail("on_nav_route() propagated an exception")


class TestSessionLifecycle:
    def test_session_start_resets_state(self):
        consumer, captured = _make()
        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))
        captured.clear()

        consumer.on_session_start()
        # Route forgotten → an arrival now yields neutral, not a stale hop.
        consumer.observe(_event("FSDJump", "Sol"))
        assert captured[-1]["system"] is None

    def test_reevaluate_forces_fresh_emit(self):
        client = MagicMock()
        client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNKNOWN, system_name="",
        )
        consumer, captured = _make(client=client)
        consumer.on_nav_route(_route())
        consumer.observe(_event("FSDJump", "Sol"))
        assert len(captured) == 1

        consumer.reevaluate()  # e.g. after re-enabling lookups
        assert len(captured) == 2
        assert captured[-1]["system"] == "Alpha Centauri"


class TestCurrentSystemProperty:
    """current_system exposes the tracked location for the on-demand
    nearest-scoopable-star lookup."""

    def test_empty_before_first_arrival(self):
        consumer, _captured = _make()
        assert consumer.current_system == ""

    def test_reflects_last_arrival(self):
        consumer, _captured = _make()
        consumer.observe(_event("FSDJump", "Sol"))
        assert consumer.current_system == "Sol"
        consumer.observe(_event("FSDJump", "Alpha Centauri"))
        assert consumer.current_system == "Alpha Centauri"

    def test_reset_on_session_start(self):
        consumer, _captured = _make()
        consumer.observe(_event("FSDJump", "Sol"))
        consumer.on_session_start()
        assert consumer.current_system == ""
