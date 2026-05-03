"""
Tests for the EDDNValidator module.
"""

import pytest

from src.modules.parser import ParsedEvent, SessionState
from src.modules.validator import EDDN_JOURNAL_1_SCHEMA_REF, EDDNValidator


@pytest.fixture
def validator():
    return EDDNValidator()


class TestValidate:
    """Tests for validate method."""

    def test_valid_fsdjump(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "JumpDist": 15.123,
                "FuelUsed": 2.345,
                "FuelLevel": 28.655,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        assert validator.validate(event) is True

    def test_fsdjump_missing_starpos(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                # Missing StarPos
                "JumpDist": 15.123,
                "FuelUsed": 2.345,
                "FuelLevel": 28.655,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        assert validator.validate(event) is False

    def test_valid_scan(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:10:45Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "Sol",
                "DistanceFromArrivalLS": 0.0,
            },
            event_type="Scan",
            timestamp="2026-01-12T12:10:45Z",
        )
        assert validator.validate(event) is True

    def test_valid_location(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:50:00Z",
                "event": "Location",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="Location",
            timestamp="2026-01-12T12:50:00Z",
        )
        assert validator.validate(event) is True

    def test_valid_docked(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T13:00:00Z",
                "event": "Docked",
                "StationName": "Jameson Memorial",
                "StarSystem": "Shinrarta Dezhra",
                "SystemAddress": 10477373803,
            },
            event_type="Docked",
            timestamp="2026-01-12T13:00:00Z",
        )
        assert validator.validate(event) is True

    def test_valid_fssdiscoveryscan(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        assert validator.validate(event) is True

    def test_unknown_event_type(self, validator):
        event = ParsedEvent(
            raw={"timestamp": "2026-01-12T12:00:00Z", "event": "SupercruiseEntry"},
            event_type="SupercruiseEntry",
            timestamp="2026-01-12T12:00:00Z",
        )
        assert validator.validate(event) is False


class TestTransform:
    """Tests for transform method."""

    def test_strips_disallowed_fields(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "JumpDist": 15.123,
                "FuelUsed": 2.345,
                "FuelLevel": 28.655,
                "ActiveFine": True,
                "Crew": ["NPC1"],
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)

        assert "ActiveFine" not in message["message"]
        assert "Crew" not in message["message"]
        assert message["message"]["StarSystem"] == "Sol"

    def test_augments_horizons_odyssey(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "JumpDist": 15.123,
                "FuelUsed": 2.345,
                "FuelLevel": 28.655,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform(event, session_state)

        assert message["message"]["horizons"] is True
        assert message["message"]["odyssey"] is False

    def test_message_structure(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        assert "$schemaRef" in message
        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF
        assert "header" in message
        assert "message" in message
