"""Tests for the EdsmLookupConsumer (arrival-triggered EDSM system lookup).

Covers:
- One lookup per system entry (FSDJump/Location triggers a lookup)
- No duplicate for the same system (second FSDJump to same system is a no-op)
- Disabled toggle short-circuits before any network call
- Lookups never gate EDDN/EDSM-write (stream consumer doesn't block observe())
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from conftest import MockSettings

from src.modules.edsm_lookup_consumer import EdsmLookupConsumer
from src.modules.edsm_read_client import STATUS_UNKNOWN, SystemBodiesResult
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
