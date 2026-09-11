"""Tests for the EdsmNextHopConsumer (next-in-route hop preview).

Covers:
- Preview produced for the next hop: scoopability (+ verdict, + value when available)
- Cache reuse for the next system (no network when cached)
- Neutral states: disabled toggle, no next hop (final/off-route/no route)
- Scoopability survives an EDSM lookup failure (verdict/value neutral, chip kept)
- Non-blocking: observe()/on_nav_route() never raise
- Preview advances after a jump
- Re-plotted routes hold MAX_CONCURRENT_EDSM_LOOKUPS hop lookups in flight by
  preempting the oldest, so the newest hop still gets its preview
"""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from conftest import MockSettings

from src.modules.constants import MAX_CONCURRENT_EDSM_LOOKUPS
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


class _BlockingReadClient:
    """Read client whose calls block until released; records calls thread-safely."""

    def __init__(self) -> None:
        self._release = threading.Event()
        self._lock = threading.Lock()
        self.bodies_calls: list[str] = []

    def release(self) -> None:
        self._release.set()

    def get_system_bodies(self, system_name: str) -> SystemBodiesResult:
        with self._lock:
            self.bodies_calls.append(system_name)
        self._release.wait(timeout=5)
        return SystemBodiesResult(status=STATUS_UNKNOWN, system_name=system_name)

    def get_estimated_value(self, system_name: str) -> SystemValueResult:
        self._release.wait(timeout=5)
        return SystemValueResult(status=STATUS_UNKNOWN, system_name=system_name)


def _route_to(hop_system: str) -> list[dict]:
    return [
        {"StarSystem": "Sol", "SystemAddress": 10477373803, "StarClass": "G"},
        {"StarSystem": hop_system, "SystemAddress": 55230754, "StarClass": "B"},
    ]


class TestConcurrencyCap:
    """Rapidly changing hops must not fan out one unbounded lookup pair per change."""

    @pytest.mark.asyncio
    async def test_burst_of_distinct_hops_previews_the_newest_hop(self):
        """Past the cap the oldest hop lookup is preempted, not the newest hop's.

        Dropping the newest hop instead produced no preview for it at all:
        ``_reevaluate()`` had already committed the dedup key, so the hop was
        never retried and every older in-flight result was discarded as stale.
        """
        client = _BlockingReadClient()
        consumer, captured = _make(client=client)
        consumer.observe(_event("FSDJump", "Sol", 10477373803))

        rounds = MAX_CONCURRENT_EDSM_LOOKUPS * 3
        preempted: list[asyncio.Task] = []
        for i in range(rounds):
            before = set(consumer._lookup_tasks)
            consumer.on_nav_route(_route_to(f"Hop {i}"))
            assert len(consumer._lookup_tasks) <= MAX_CONCURRENT_EDSM_LOOKUPS
            preempted.extend(before - set(consumer._lookup_tasks))

        newest = f"Hop {rounds - 1}"
        tasks = list(consumer._lookup_tasks)
        assert len(tasks) == MAX_CONCURRENT_EDSM_LOOKUPS
        assert len(preempted) == rounds - MAX_CONCURRENT_EDSM_LOOKUPS

        client.release()
        await asyncio.gather(*tasks, *preempted, return_exceptions=True)

        # Exactly one hop preview, for the hop the route now points at.
        # (The first entry is the neutral no-route emit from the arrival.)
        hop_previews = [p for p in captured if p["reason"] == REASON_HOP]
        assert [p["system"] for p in hop_previews] == [newest]
        assert hop_previews[-1]["scoopable"] is True  # class B, from the route
        assert all(task.cancelled() for task in preempted)
        assert consumer._lookup_tasks == {}

    @pytest.mark.asyncio
    async def test_preempted_in_flight_hop_lookup_emits_nothing(self):
        """A hop lookup preempted after its request started is cancelled and stays silent."""
        client = _BlockingReadClient()
        consumer, captured = _make(client=client)
        consumer.observe(_event("FSDJump", "Sol", 10477373803))
        consumer.on_nav_route(_route_to("Old Hop"))
        oldest = next(iter(consumer._lookup_tasks))
        for _ in range(200):  # let it reach the (blocking) read client
            if client.bodies_calls:
                break
            await asyncio.sleep(0.005)
        assert client.bodies_calls == ["Old Hop"]

        for i in range(MAX_CONCURRENT_EDSM_LOOKUPS):
            consumer.on_nav_route(_route_to(f"Hop {i}"))

        assert oldest not in consumer._lookup_tasks  # slot released at preemption
        assert len(consumer._lookup_tasks) == MAX_CONCURRENT_EDSM_LOOKUPS

        client.release()
        await asyncio.gather(*list(consumer._lookup_tasks), oldest, return_exceptions=True)

        assert oldest.cancelled()
        assert "Old Hop" not in [p["system"] for p in captured]

    @pytest.mark.asyncio
    async def test_pending_emits_do_not_consume_lookup_slots(self):
        """Neutral previews emit without a lookup, so they must not fill the lookup cap."""
        client = _BlockingReadClient()
        consumer, _captured = _make(client=client)
        consumer.observe(_event("FSDJump", "Sol", 10477373803))

        rounds = MAX_CONCURRENT_EDSM_LOOKUPS * 2
        for i in range(rounds):
            consumer.on_nav_route([])  # no route -> neutral emit, no lookup
            consumer.on_nav_route(_route_to(f"Hop {i}"))  # re-plotted -> lookup

        emits = list(consumer._tasks)
        lookups = list(consumer._lookup_tasks)
        assert len(emits) == rounds  # decky emits are queued, not capped
        assert len(lookups) == MAX_CONCURRENT_EDSM_LOOKUPS

        client.release()
        await asyncio.gather(*lookups, *emits)

        # Lookups still ran: the queued emits never occupied a lookup slot.
        assert len(client.bodies_calls) == MAX_CONCURRENT_EDSM_LOOKUPS

    @pytest.mark.asyncio
    async def test_session_stop_cancels_tracked_tasks_and_frees_slots(self):
        client = _BlockingReadClient()
        consumer, _captured = _make(client=client)
        consumer.observe(_event("FSDJump", "Sol", 10477373803))
        for i in range(MAX_CONCURRENT_EDSM_LOOKUPS):
            consumer.on_nav_route(_route_to(f"Hop {i}"))
        tasks = list(consumer._lookup_tasks)

        consumer.on_session_stop()

        assert consumer._lookup_tasks == {}
        await asyncio.gather(*tasks, return_exceptions=True)
        assert all(task.cancelled() for task in tasks)

        consumer.observe(_event("FSDJump", "Sol", 10477373803))
        consumer.on_nav_route(_route_to("Colonia"))
        assert len(consumer._lookup_tasks) == 1
        consumer.on_session_stop()
