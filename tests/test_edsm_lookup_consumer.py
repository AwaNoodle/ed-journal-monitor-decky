"""Tests for the EdsmLookupConsumer (arrival-triggered EDSM system lookup).

Covers:
- One lookup per system entry (FSDJump/Location triggers a lookup)
- No duplicate for the same system (second FSDJump to same system is a no-op)
- Disabled toggle short-circuits before any network call
- Lookups never gate EDDN/EDSM-write (stream consumer doesn't block observe())
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from src.modules.edsm_lookup_consumer import EdsmLookupConsumer
from src.modules.edsm_read_client import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    SystemBodiesResult,
    SystemValueResult,
)
from src.modules.parser import ParsedEvent, SessionState


def _event(event_type: str, system: str) -> ParsedEvent:
    return ParsedEvent(
        raw={"event": event_type, "StarSystem": system, "timestamp": "2026-01-01T00:00:00Z"},
        event_type=event_type,
        timestamp="2026-01-01T00:00:00Z",
    )


def _session(system: str = "Sol") -> SessionState:
    s = SessionState()
    s.star_system = system
    return s


@pytest.fixture
def mock_read_client():
    client = MagicMock()
    client.get_system_bodies.return_value = SystemBodiesResult(
        status=STATUS_UNKNOWN, system_name="Sol"
    )
    client.get_estimated_value.return_value = SystemValueResult(
        status=STATUS_UNKNOWN, system_name="Sol"
    )
    return client


@pytest.fixture
def consumer(mock_read_client):
    settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
    return EdsmLookupConsumer(settings=settings, read_client=mock_read_client)


class TestOnePerArrival:
    @pytest.mark.asyncio
    async def test_fsdjump_triggers_lookup(self, consumer, mock_read_client):
        """FSDJump to a new system triggers exactly one lookup."""
        event = _event("FSDJump", "Wolf 359")
        session = _session("Wolf 359")

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.observe(event, session)

        mock_fire.assert_called_once_with("Wolf 359")

    @pytest.mark.asyncio
    async def test_location_triggers_lookup(self, consumer, mock_read_client):
        """Location event (login-time arrival) also triggers a lookup."""
        event = _event("Location", "Maia")
        session = _session("Maia")

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.observe(event, session)

        mock_fire.assert_called_once_with("Maia")

    def test_non_arrival_event_does_not_trigger_lookup(self, consumer):
        """Scan / FSSDiscoveryScan / etc. do not trigger a lookup."""
        event = _event("Scan", "Sol")
        session = _session("Sol")

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.observe(event, session)

        mock_fire.assert_not_called()


class TestNoDuplicateLookup:
    def test_no_duplicate_for_current_system(self, consumer):
        """Repeated FSDJump events for the same system fire only one lookup."""
        event = _event("FSDJump", "Sol")
        session = _session("Sol")

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.observe(event, session)
            consumer.observe(event, session)  # duplicate

        mock_fire.assert_called_once_with("Sol")

    def test_new_system_triggers_fresh_lookup(self, consumer):
        """After entering a different system, a new lookup fires."""
        e1 = _event("FSDJump", "Sol")
        e2 = _event("FSDJump", "Maia")
        s1 = _session("Sol")
        s2 = _session("Maia")

        calls: list[str] = []
        def record(s: str) -> None: calls.append(s)
        with patch.object(consumer, "_fire_lookup", side_effect=record):
            consumer.observe(e1, s1)
            consumer.observe(e2, s2)

        assert calls == ["Sol", "Maia"]

    def test_re_entering_same_system_after_different_triggers_new_lookup(self, consumer):
        """Sol → Maia → Sol should trigger Sol lookup again."""
        e_sol = _event("FSDJump", "Sol")
        e_maia = _event("FSDJump", "Maia")
        s_sol = _session("Sol")
        s_maia = _session("Maia")

        calls: list[str] = []
        def record(s: str) -> None: calls.append(s)
        with patch.object(consumer, "_fire_lookup", side_effect=record):
            consumer.observe(e_sol, s_sol)  # Sol #1
            consumer.observe(e_maia, s_maia)
            consumer.observe(e_sol, s_sol)  # Sol #2 (after Maia)

        assert calls == ["Sol", "Maia", "Sol"]


class TestDisabledToggle:
    def test_disabled_toggle_short_circuits_before_lookup(self):
        """When lookups are disabled, observe() must not trigger any lookup."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": False})
        mock_client = MagicMock()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_client)

        event = _event("FSDJump", "Sol")
        session = _session("Sol")

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.observe(event, session)

        mock_fire.assert_not_called()
        mock_client.get_system_bodies.assert_not_called()

    def test_disabled_makes_no_network_call(self):
        """The read client must never be called when lookups are off."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": False})
        mock_client = MagicMock()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_client)

        consumer.observe(_event("FSDJump", "Sol"), _session("Sol"))

        mock_client.get_system_bodies.assert_not_called()

    def test_disabled_consumer_does_not_clear_last_system(self):
        """When lookups are disabled, _last_system is preserved (force_lookup reads it on re-enable)."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": False})
        mock_client = MagicMock()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_client)
        consumer._last_system = "Sol"

        consumer.observe(_event("FSDJump", "Sol"), _session("Sol"))

        assert consumer._last_system == "Sol"


class TestForceLookup:
    def test_force_lookup_fires_lookup_for_named_system(self):
        """force_lookup triggers a lookup even if system matches _last_system."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_client = MagicMock()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_client)
        consumer._last_system = "Sol"  # same system — would be deduped by observe()

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.force_lookup("Sol")

        mock_fire.assert_called_once_with("Sol")
        assert consumer._last_system == "Sol"

    def test_force_lookup_noop_for_empty_system(self):
        """force_lookup("") must do nothing."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        consumer = EdsmLookupConsumer(settings=settings)

        with patch.object(consumer, "_fire_lookup") as mock_fire:
            consumer.force_lookup("")

        mock_fire.assert_not_called()


class TestNonBlocking:
    def test_observe_does_not_await_lookup(self, consumer):
        """observe() must return synchronously; the lookup is fire-and-forget."""
        event = _event("FSDJump", "Sol")
        session = _session("Sol")

        # If observe() blocks, the test would hang; patching _fire_lookup to be sync
        fired = []
        def sync_fire(system):
            fired.append(system)

        consumer._fire_lookup = sync_fire
        consumer.observe(event, session)  # must return without awaiting

        assert fired == ["Sol"]

    def test_lookup_failure_does_not_propagate(self, consumer):
        """A lookup error must never raise out of observe()."""
        event = _event("FSDJump", "Sol")
        session = _session("Sol")

        consumer._fire_lookup = lambda s: (_ for _ in ()).throw(Exception("boom"))
        # Should NOT raise
        try:
            consumer.observe(event, session)
        except Exception:
            pytest.fail("observe() propagated a lookup exception")


class TestStalenessGuard:
    def test_stale_lookup_does_not_update_verdict(self):
        """When _last_system changes before a lookup completes, its verdict is dropped."""
        from src.modules.edsm_read_client import STATUS_OK, SystemBodiesResult

        verdicts: list[tuple[str, str | None]] = []
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_client = MagicMock()
        # Simulate Sol returning a red result
        mock_client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_OK,
            system_name="Sol",
            bodies=[{"discovery": {"commander": "Jameson"}}],
            body_count=1,
        )
        consumer = EdsmLookupConsumer(
            settings=settings,
            read_client=mock_client,
            on_verdict=lambda s, v: verdicts.append((s, v)),
        )

        # Player is now in Maia (jumped away while Sol lookup was in flight)
        consumer._last_system = "Maia"

        # Sol's lookup result arrives (sync path simulates a completed async task)
        consumer._do_lookup_sync("Sol")

        # Verdict must be dropped — Sol is no longer the current system
        assert verdicts == []


class TestUnavailableResult:
    def test_unavailable_result_is_not_cached(self):
        """STATUS_UNAVAILABLE must not be written to the cache (so retry is possible)."""
        from src.modules.edsm_read_client import STATUS_UNAVAILABLE, SystemBodiesResult

        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_client = MagicMock()
        mock_client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNAVAILABLE, system_name="Sol"
        )
        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # cache miss
        consumer = EdsmLookupConsumer(
            settings=settings,
            read_client=mock_client,
            cache=mock_cache,
        )
        consumer._last_system = "Sol"  # Sol is current

        consumer._do_lookup_sync("Sol")

        mock_cache.set.assert_not_called()

    def test_unavailable_result_does_not_emit_verdict(self):
        """STATUS_UNAVAILABLE must not call on_verdict (chip stays absent, not stuck)."""
        from src.modules.edsm_read_client import STATUS_UNAVAILABLE, SystemBodiesResult

        verdicts: list[tuple[str, str | None]] = []
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_client = MagicMock()
        mock_client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNAVAILABLE, system_name="Sol"
        )
        consumer = EdsmLookupConsumer(
            settings=settings,
            read_client=mock_client,
            on_verdict=lambda s, v: verdicts.append((s, v)),
        )
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        assert verdicts == []


class TestSessionLifecycle:
    def test_on_session_start_clears_dedup_state(self, consumer):
        """Starting a new session resets the 'last system' so first arrival fires again."""
        event = _event("FSDJump", "Sol")
        session = _session("Sol")

        calls: list[str] = []
        def record(s: str) -> None: calls.append(s)
        with patch.object(consumer, "_fire_lookup", side_effect=record):
            consumer.observe(event, session)  # fires once
            consumer.on_session_start()       # reset
            consumer.observe(event, session)  # should fire again

        assert calls == ["Sol", "Sol"]

    def test_get_stats_does_not_report_upload_stats(self, consumer):
        """The lookup consumer is read-only; it must not appear in upload stats."""
        assert not getattr(consumer, "reports_upload_stats", False)


class TestValueFetch:
    """The arrival lookup also fetches estimated-value alongside bodies."""

    def _value_result(self, total=1500, bodies=None):
        return SystemValueResult(
            status=STATUS_OK,
            system_name="Sol",
            total_value=total,
            valuable_bodies=bodies or [{"bodyId": 1, "bodyName": "Earth", "valueMax": 900}],
        )

    def test_sync_lookup_fetches_value_alongside_bodies(self, mock_read_client):
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_read_client.get_estimated_value.return_value = self._value_result()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_read_client)
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        mock_read_client.get_estimated_value.assert_called_once_with("Sol")

    def test_on_value_callback_receives_summary(self, mock_read_client):
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_read_client.get_estimated_value.return_value = self._value_result()
        values: list[tuple[str, dict | None]] = []
        consumer = EdsmLookupConsumer(
            settings=settings,
            read_client=mock_read_client,
            on_value=lambda s, v: values.append((s, v)),
        )
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        assert len(values) == 1
        system, payload = values[0]
        assert system == "Sol"
        assert payload["totalValue"] == 1500
        assert payload["priorityBodies"] == [{"name": "Earth", "value": 900}]

    def test_value_fetch_failure_reports_neutral_via_on_value(self, mock_read_client):
        """A contained value-fetch failure must not raise and must report neutral."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        mock_read_client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="Sol"
        )
        mock_read_client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNAVAILABLE, system_name="Sol"
        )
        values: list[tuple[str, dict | None]] = []
        consumer = EdsmLookupConsumer(
            settings=settings,
            read_client=mock_read_client,
            on_value=lambda s, v: values.append((s, v)),
        )
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        assert values == [("Sol", None)]

    def test_value_result_cached_alongside_bodies(self, mock_read_client):
        """A cache hit for value must skip the network call, same as bodies."""
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        from src.modules.edsm_system_cache import SystemLookupCache

        cache = SystemLookupCache()
        cache.set_value("Sol", self._value_result())
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_read_client, cache=cache)
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        mock_read_client.get_estimated_value.assert_not_called()

    def test_unavailable_value_result_is_not_cached(self, mock_read_client):
        mock_read_client.get_estimated_value.return_value = SystemValueResult(
            status=STATUS_UNAVAILABLE, system_name="Sol"
        )
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        from src.modules.edsm_system_cache import SystemLookupCache

        cache = SystemLookupCache()
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_read_client, cache=cache)
        consumer._last_system = "Sol"

        consumer._do_lookup_sync("Sol")

        assert cache.get_value("Sol") is None

    @pytest.mark.asyncio
    async def test_async_lookup_emits_merged_verdict_and_value(self, mock_read_client):
        """The decky event for a live arrival carries both verdict and value fields."""
        mock_read_client.get_system_bodies.return_value = SystemBodiesResult(
            status=STATUS_UNKNOWN, system_name="Sol"
        )
        mock_read_client.get_estimated_value.return_value = self._value_result()
        settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        consumer = EdsmLookupConsumer(settings=settings, read_client=mock_read_client)
        consumer._last_system = "Sol"

        with patch("src.modules.edsm_lookup_consumer.decky.emit", new_callable=AsyncMock) as mock_emit:
            await consumer._lookup_async("Sol")

        mock_emit.assert_called_once()
        _event_name, payload = mock_emit.call_args.args
        assert payload["system"] == "Sol"
        assert payload["verdict"] == "green"
        assert payload["totalValue"] == 1500
        assert payload["priorityBodies"] == [{"name": "Earth", "value": 900}]
