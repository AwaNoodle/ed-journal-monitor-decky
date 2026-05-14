"""
Tests for the SignalBatcher module.
Tests FSSSignalDiscovered event batching, flush triggers, signal extraction,
and position data augmentation from session_state.
"""

import pytest

from src.modules.parser import ParsedEvent, SessionState


@pytest.fixture
def batcher():
    from src.modules.signal_batcher import SignalBatcher
    return SignalBatcher()


def _make_signal_event(**overrides):
    """Helper to create an FSSSignalDiscovered ParsedEvent."""
    raw = {
        "timestamp": "2026-01-12T14:03:00Z",
        "event": "FSSSignalDiscovered",
        "SystemAddress": 10477373803,
        "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;",
        "StarSystem": "Sol",
        "StarPos": [0.0, 0.0, 0.0],
        "TimeRemaining": 120.5,
        "IsStation": True,
        "USSType": "$USS_Type_Debris;",
        "SpawningState": "$FactionState_Boom;",
        "SpawningFaction": "Test Faction",
        "ThreatLevel": 2,
        "SignalType": "USS",
        "SpawningPower": "Aisling Duval",
        "OpposingPower": "Zachary Hudson",
        "SignalName_Localised": "Scenario 42",
        "USSType_Localised": "Debris",
        "SpawningState_Localised": "Boom",
    }
    raw.update(overrides)
    return ParsedEvent(
        raw=raw,
        event_type="FSSSignalDiscovered",
        timestamp=raw["timestamp"],
    )


def _make_session_state(**overrides):
    """Helper to create a SessionState with position data."""
    defaults = {
        "horizons": True,
        "odyssey": True,
        "game_version": "4.3.3.0",
        "game_build": "r327343/r0 ",
        "commander": "TestCommander",
        "star_pos": [0.0, 0.0, 0.0],
        "system_address": 10477373803,
        "star_system": "Sol",
    }
    defaults.update(overrides)
    return SessionState(**defaults)


class TestAddSignal:
    """Tests for add_signal method."""

    def test_accumulates_single_signal(self, batcher):
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is not None
        assert len(batch_data["signals"]) == 1

    def test_accumulates_multiple_signals(self, batcher):
        event1 = _make_signal_event(SignalName="Signal1", timestamp="2026-01-12T14:03:00Z")
        event2 = _make_signal_event(SignalName="Signal2", timestamp="2026-01-12T14:03:05Z")
        batcher.add_signal(event1)
        batcher.add_signal(event2)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is not None
        assert len(batch_data["signals"]) == 2
        assert batch_data["signals"][0]["SignalName"] == "Signal1"
        assert batch_data["signals"][1]["SignalName"] == "Signal2"

    def test_strips_time_remaining(self, batcher):
        """TimeRemaining is disallowed in fsssignaldiscovered/1 and must be stripped."""
        event = _make_signal_event(TimeRemaining=120.5)
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "TimeRemaining" not in batch_data["signals"][0]

    def test_strips_event_field(self, batcher):
        """The 'event' field must not appear in individual signals."""
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "event" not in batch_data["signals"][0]

    def test_preserves_timestamp_in_signal(self, batcher):
        """Timestamp must be preserved in each signal per fsssignaldiscovered/1 schema."""
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "timestamp" in batch_data["signals"][0]

    def test_strips_localised_keys(self, batcher):
        """_Localised keys must be stripped from individual signals."""
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        signal = batch_data["signals"][0]
        assert "SignalName_Localised" not in signal
        assert "USSType_Localised" not in signal
        assert "SpawningState_Localised" not in signal

    def test_preserves_signal_name(self, batcher):
        event = _make_signal_event(SignalName="$MULTIPLAYER_SCENARIO42_TITLE;")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["SignalName"] == "$MULTIPLAYER_SCENARIO42_TITLE;"

    def test_preserves_is_station(self, batcher):
        event = _make_signal_event(IsStation=True)
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["IsStation"] is True

    def test_preserves_uss_type(self, batcher):
        event = _make_signal_event(USSTType="$USS_Type_Debris;")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["USSType"] == "$USS_Type_Debris;"

    def test_preserves_spawning_state(self, batcher):
        event = _make_signal_event(SpawningState="$FactionState_Boom;")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["SpawningState"] == "$FactionState_Boom;"

    def test_preserves_spawning_faction(self, batcher):
        event = _make_signal_event(SpawningFaction="Test Faction")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["SpawningFaction"] == "Test Faction"

    def test_preserves_threat_level(self, batcher):
        event = _make_signal_event(ThreatLevel=2)
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["ThreatLevel"] == 2

    def test_preserves_signal_type(self, batcher):
        event = _make_signal_event(SignalType="USS")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["SignalType"] == "USS"

    def test_preserves_spawning_power(self, batcher):
        event = _make_signal_event(SpawningPower="Aisling Duval")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["SpawningPower"] == "Aisling Duval"

    def test_preserves_opposing_power(self, batcher):
        event = _make_signal_event(OpposingPower="Zachary Hudson")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["signals"][0]["OpposingPower"] == "Zachary Hudson"

    def test_strips_star_pos_from_individual_signal(self, batcher):
        """StarPos belongs at message level, not in individual signals."""
        event = _make_signal_event(StarPos=[0.0, 0.0, 0.0])
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "StarPos" not in batch_data["signals"][0]

    def test_strips_star_system_from_individual_signal(self, batcher):
        """StarSystem belongs at message level, not in individual signals."""
        event = _make_signal_event(StarSystem="Sol")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "StarSystem" not in batch_data["signals"][0]

    def test_strips_system_address_from_individual_signal(self, batcher):
        """SystemAddress belongs at message level, not in individual signals."""
        event = _make_signal_event(SystemAddress=10477373803)
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert "SystemAddress" not in batch_data["signals"][0]


class TestMetadata:
    """Tests for metadata tracking from FSSSignalDiscovered events."""

    def test_tracks_last_timestamp(self, batcher):
        event1 = _make_signal_event(timestamp="2026-01-12T14:03:00Z")
        event2 = _make_signal_event(timestamp="2026-01-12T14:03:05Z")
        batcher.add_signal(event1)
        batcher.add_signal(event2)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["last_timestamp"] == "2026-01-12T14:03:05Z"

    def test_tracks_system_address(self, batcher):
        event = _make_signal_event(SystemAddress=10477373803)
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["system_address"] == 10477373803

    def test_tracks_star_system(self, batcher):
        event = _make_signal_event(StarSystem="Sol")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["star_system"] == "Sol"

    def test_tracks_star_pos(self, batcher):
        event = _make_signal_event(StarPos=[0.0, 0.0, 0.0])
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["star_pos"] == [0.0, 0.0, 0.0]

    def test_metadata_updates_with_latest_signal(self, batcher):
        """Metadata should reflect the last signal added."""
        event1 = _make_signal_event(
            SystemAddress=10477373803,
            StarSystem="Sol",
            StarPos=[0.0, 0.0, 0.0],
            timestamp="2026-01-12T14:03:00Z",
        )
        event2 = _make_signal_event(
            SystemAddress=55230754,
            StarSystem="Alpha Centauri",
            StarPos=[1.0, 2.0, 3.0],
            timestamp="2026-01-12T14:03:05Z",
        )
        batcher.add_signal(event1)
        batcher.add_signal(event2)

        session_state = _make_session_state(
            system_address=55230754,
            star_system="Alpha Centauri",
            star_pos=[1.0, 2.0, 3.0],
        )
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data["system_address"] == 55230754
        assert batch_data["star_system"] == "Alpha Centauri"
        assert batch_data["star_pos"] == [1.0, 2.0, 3.0]
        assert batch_data["last_timestamp"] == "2026-01-12T14:03:05Z"


class TestFlush:
    """Tests for flush method with session_state augmentation."""

    def test_returns_none_when_empty(self, batcher):
        assert batcher.flush() is None

    def test_returns_batch_data(self, batcher):
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is not None
        assert "signals" in batch_data
        assert "last_timestamp" in batch_data
        assert "system_address" in batch_data
        assert "star_system" in batch_data
        assert "star_pos" in batch_data

    def test_clears_internal_state(self, batcher):
        event = _make_signal_event()
        batcher.add_signal(event)

        session_state = _make_session_state()
        batcher.flush(session_state=session_state)
        # Second flush should return None (state was cleared)
        assert batcher.flush() is None

    def test_second_flush_after_adding_more(self, batcher):
        """After flush, adding more signals should work."""
        event1 = _make_signal_event(SignalName="Signal1")
        batcher.add_signal(event1)
        session_state = _make_session_state()
        batch_data1 = batcher.flush(session_state=session_state)
        assert len(batch_data1["signals"]) == 1

        event2 = _make_signal_event(SignalName="Signal2")
        batcher.add_signal(event2)
        batch_data2 = batcher.flush(session_state=session_state)
        assert len(batch_data2["signals"]) == 1
        assert batch_data2["signals"][0]["SignalName"] == "Signal2"

    def test_uses_signal_data_when_available(self, batcher):
        """When signals have StarSystem/StarPos, use them directly."""
        event = _make_signal_event(StarSystem="Sol", StarPos=[0.0, 0.0, 0.0])
        batcher.add_signal(event)

        batch_data = batcher.flush()  # No session_state needed when data is in signal
        assert batch_data is not None
        assert batch_data["star_system"] == "Sol"
        assert batch_data["star_pos"] == [0.0, 0.0, 0.0]

    def test_augments_from_session_state_when_missing(self, batcher):
        """When signals lack StarSystem/StarPos, augment from session_state."""
        # FSSSignalDiscovered events in ED rarely have StarSystem/StarPos
        raw_no_pos = {
            "timestamp": "2026-01-12T14:03:00Z",
            "event": "FSSSignalDiscovered",
            "SystemAddress": 10477373803,
            "SignalName": "Test Signal",
            "SignalType": "USS",
        }
        event_no_pos = ParsedEvent(
            raw=raw_no_pos,
            event_type="FSSSignalDiscovered",
            timestamp="2026-01-12T14:03:00Z",
        )
        batcher.add_signal(event_no_pos)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is not None
        assert batch_data["star_system"] == "Sol"
        assert batch_data["star_pos"] == [0.0, 0.0, 0.0]

    def test_augments_from_session_state_with_matching_system_address(self, batcher):
        """When SystemAddress matches session_state, augment position data."""
        raw = {
            "timestamp": "2026-01-12T14:03:00Z",
            "event": "FSSSignalDiscovered",
            "SystemAddress": 10477373803,  # Matches session_state
            "SignalName": "Test Signal",
        }
        event = ParsedEvent(raw=raw, event_type="FSSSignalDiscovered", timestamp="2026-01-12T14:03:00Z")
        batcher.add_signal(event)

        session_state = _make_session_state()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is not None
        assert batch_data["star_system"] == "Sol"
        assert batch_data["star_pos"] == [0.0, 0.0, 0.0]

    def test_discards_batch_when_system_address_mismatches(self, batcher):
        """When SystemAddress doesn't match session_state and no position
        data in signals, the batch is discarded (can't submit valid data)."""
        raw = {
            "timestamp": "2026-01-12T14:03:00Z",
            "event": "FSSSignalDiscovered",
            "SystemAddress": 99999,  # Different from session_state
            "SignalName": "Test Signal",
        }
        event = ParsedEvent(raw=raw, event_type="FSSSignalDiscovered", timestamp="2026-01-12T14:03:00Z")
        batcher.add_signal(event)

        # session_state has SystemAddress=10477373803, batch has 99999
        session_state = _make_session_state(system_address=10477373803)
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is None  # Discarded because position data can't be determined

    def test_uses_signal_data_even_when_system_address_mismatches(self, batcher):
        """When signals have StarPos/StarSystem directly, SystemAddress mismatch
        doesn't matter - the data in the signal is authoritative."""
        event = _make_signal_event(
            SystemAddress=99999,  # Different from session_state
            StarSystem="Different System",
            StarPos=[10.0, 20.0, 30.0],
        )
        batcher.add_signal(event)

        session_state = _make_session_state()  # SystemAddress=10477373803
        batch_data = batcher.flush(session_state=session_state)
        # Signal has its own StarSystem/StarPos, so batch should succeed
        assert batch_data is not None
        assert batch_data["star_system"] == "Different System"
        assert batch_data["star_pos"] == [10.0, 20.0, 30.0]

    def test_discards_batch_when_no_position_data_at_all(self, batcher):
        """When there's no position data from signals or session_state,
        the batch is discarded."""
        raw = {
            "timestamp": "2026-01-12T14:03:00Z",
            "event": "FSSSignalDiscovered",
            "SystemAddress": 99999,
            "SignalName": "Test Signal",
        }
        event = ParsedEvent(raw=raw, event_type="FSSSignalDiscovered", timestamp="2026-01-12T14:03:00Z")
        batcher.add_signal(event)

        # session_state has no star_pos (default SessionState)
        session_state = SessionState()
        batch_data = batcher.flush(session_state=session_state)
        assert batch_data is None  # Discarded: no position data available

    def test_discards_batch_when_no_session_state(self, batcher):
        """When there's no session_state and signals lack position data,
        the batch is discarded."""
        raw = {
            "timestamp": "2026-01-12T14:03:00Z",
            "event": "FSSSignalDiscovered",
            "SystemAddress": 10477373803,
            "SignalName": "Test Signal",
        }
        event = ParsedEvent(raw=raw, event_type="FSSSignalDiscovered", timestamp="2026-01-12T14:03:00Z")
        batcher.add_signal(event)

        # No session_state passed, and signal has no StarSystem/StarPos
        batch_data = batcher.flush()  # No session_state
        assert batch_data is None  # Discarded: no position data available


class TestShouldFlush:
    """Tests for should_flush method."""

    @pytest.mark.parametrize("event_type", [
        "FSSDiscoveryScan",
        "SupercruiseEntry",
        "Location",
        "FSDJump",
        "CarrierJump",
        "Shutdown",
        "Music",
    ])
    def test_returns_true_for_trigger_events(self, batcher, event_type):
        assert batcher.should_flush(event_type) is True

    @pytest.mark.parametrize("event_type", [
        "Scan",
        "Docked",
        "FSSSignalDiscovered",
        "ApproachSettlement",
        "CodexEntry",
        "SAASignalsFound",
        "SupercruiseExit",
        "LoadGame",
    ])
    def test_returns_false_for_non_trigger_events(self, batcher, event_type):
        assert batcher.should_flush(event_type) is False
