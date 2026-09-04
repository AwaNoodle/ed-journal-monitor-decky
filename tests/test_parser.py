"""
Tests for the JournalParser module.
"""

from pathlib import Path

import pytest

from src.modules.parser import JournalParser, ParsedEvent


@pytest.fixture
def parser():
    return JournalParser()


class TestParseLine:
    """Tests for parse_line method."""

    def test_valid_fsdjump(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump",'
            '"StarSystem":"Sol","SystemAddress":10477373803,'
            '"StarPos":[0.0,0.0,0.0],"JumpDist":15.123,'
            '"FuelUsed":2.345,"FuelLevel":28.655}'
        )
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "FSDJump"
        assert result.timestamp == "2026-01-12T12:05:30Z"
        assert result.raw["StarSystem"] == "Sol"

    def test_valid_scan(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:10:45Z","event":"Scan",'
            '"ScanType":"Detailed","BodyName":"Sol","BodyID":0,'
            '"StarSystem":"Sol","SystemAddress":10477373803,'
            '"DistanceFromArrivalLS":0.0}'
        )
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "Scan"

    def test_valid_location(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:50:00Z","event":"Location",'
            '"StarSystem":"Sol","SystemAddress":10477373803,'
            '"StarPos":[0.0,0.0,0.0]}'
        )
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "Location"

    def test_valid_docked(self, parser):
        line = (
            '{"timestamp":"2026-01-12T13:00:00Z","event":"Docked",'
            '"StationName":"Jameson Memorial",'
            '"StarSystem":"Shinrarta Dezhra","SystemAddress":10477373803}'
        )
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "Docked"

    def test_valid_fssdiscoveryscan(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:15:00Z","event":"FSSDiscoveryScan",'
            '"Progress":0.95,"BodyCount":21,"NonBodyCount":42,'
            '"SystemName":"Sol","SystemAddress":10477373803}'
        )
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "FSSDiscoveryScan"

    def test_blank_line(self, parser):
        assert parser.parse_line("") is None
        assert parser.parse_line("   ") is None

    def test_invalid_json(self, parser):
        assert parser.parse_line("not json") is None
        assert parser.parse_line("{broken") is None

    def test_missing_timestamp(self, parser):
        line = '{"event":"FSDJump","StarSystem":"Sol"}'
        assert parser.parse_line(line) is None

    def test_missing_event(self, parser):
        line = '{"timestamp":"2026-01-12T12:00:00Z","StarSystem":"Sol"}'
        assert parser.parse_line(line) is None

    def test_non_reportable_event(self, parser):
        line = '{"timestamp":"2026-01-12T12:00:00Z","event":"SupercruiseEntry"}'
        result = parser.parse_line(line)
        assert result is not None
        assert result.event_type == "SupercruiseEntry"


class TestIsReportable:
    """Tests for is_reportable method."""

    def test_reportable_events(self, parser):
        reportable_events = [
            "FSDJump",
            "Scan",
            "Location",
            "Docked",
            "FSSDiscoveryScan",
            "Market",
            "Outfitting",
            "Shipyard",
            "NavRoute",
            "ApproachSettlement",
            "CarrierJump",
            "FSSSignalDiscovered",
            "SAASignalsFound",
            "CodexEntry",
        ]
        for event_type in reportable_events:
            event = ParsedEvent(raw={}, event_type=event_type, timestamp="2026-01-12T12:00:00Z")
            assert parser.is_reportable(event) is True

    def test_removed_events_not_reportable(self, parser):
        """ApproachBody, LeaveBody, SAAScanComplete have no EDDN schema."""
        for event_type in ["ApproachBody", "LeaveBody", "SAAScanComplete"]:
            event = ParsedEvent(raw={}, event_type=event_type, timestamp="2026-01-12T12:00:00Z")
            assert parser.is_reportable(event) is False

    def test_non_reportable_events(self, parser):
        for event_type in ["SupercruiseEntry", "ShieldState", "HullDamage", "Music", "Shutdown"]:
            event = ParsedEvent(raw={}, event_type=event_type, timestamp="2026-01-12T12:00:00Z")
            assert parser.is_reportable(event) is False


class TestSessionState:
    """Tests for LoadGame and Fileheader handling."""

    def test_fileheader_extracts_version(self, parser):
        line = '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.0.0.1","build":"r293895/r0 "}'
        parser.parse_line(line)
        assert parser.session_state.game_version == "4.0.0.1"
        assert parser.session_state.game_build == "r293895/r0 "

    def test_loadgame_extracts_horizons_odyssey(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame",'
            '"Commander":"TestCmdr","Horizons":true,"Odyssey":true}'
        )
        parser.parse_line(line)
        assert parser.session_state.horizons is True
        assert parser.session_state.odyssey is True

    def test_loadgame_horizons_only(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame",'
            '"Commander":"TestCmdr","Horizons":true,"Odyssey":false}'
        )
        parser.parse_line(line)
        assert parser.session_state.horizons is True
        assert parser.session_state.odyssey is False

    def test_default_session_state(self, parser):
        """Before any LoadGame is observed, horizons/odyssey are unknown (None), not guessed."""
        assert parser.session_state.horizons is None
        assert parser.session_state.odyssey is None

    def test_loadgame_without_odyssey_key_leaves_odyssey_unknown(self, parser):
        """A 3.8-era LoadGame has no Odyssey key; EDDN says omit rather than guess."""
        line = (
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame",'
            '"Commander":"TestCmdr","Horizons":true}'
        )
        parser.parse_line(line)
        assert parser.session_state.horizons is True
        assert parser.session_state.odyssey is None


class TestJournalBodyTracking:
    """Tests for ApproachBody/Location/CarrierJump/LeaveBody/FSDJump/SupercruiseEntry/
    Fileheader body tracking in SessionState (issue #39), per
    codexentry-README.md's "BodyID and BodyName" section."""

    def test_approach_body_sets_name_and_id(self, parser):
        line = (
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(line)
        assert parser.session_state.journal_body_name == "Earth"
        assert parser.session_state.journal_body_id == 3

    def test_location_sets_name_and_id(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Location",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0.0,0.0,0.0],'
            '"Body":"Sol A","BodyID":1}'
        )
        parser.parse_line(line)
        assert parser.session_state.journal_body_name == "Sol A"
        assert parser.session_state.journal_body_id == 1

    def test_carrier_jump_sets_name_and_id(self, parser):
        line = (
            '{"timestamp":"2026-01-12T12:00:00Z","event":"CarrierJump",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0.0,0.0,0.0],'
            '"Body":"Sol A","BodyID":1}'
        )
        parser.parse_line(line)
        assert parser.session_state.journal_body_name == "Sol A"
        assert parser.session_state.journal_body_id == 1

    def test_body_name_falls_back_when_body_key_absent(self, parser):
        """The journal key is Body; fall back to BodyName for a future rename."""
        line = (
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"BodyName":"Earth","BodyID":3}'
        )
        parser.parse_line(line)
        assert parser.session_state.journal_body_name == "Earth"
        assert parser.session_state.journal_body_id == 3

    def test_leave_body_clears(self, parser):
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:05:00Z","event":"LeaveBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        assert parser.session_state.journal_body_name == ""
        assert parser.session_state.journal_body_id is None

    def test_fsdjump_clears(self, parser):
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:10:00Z","event":"FSDJump",'
            '"StarSystem":"Alpha Centauri","SystemAddress":10477373804,"StarPos":[3.0,0.0,0.0]}'
        )
        assert parser.session_state.journal_body_name == ""
        assert parser.session_state.journal_body_id is None

    def test_supercruise_entry_does_not_clear(self, parser):
        """A player can re-descend to the same body without a fresh ApproachBody."""
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:03:00Z","event":"SupercruiseEntry",'
            '"StarSystem":"Sol","SystemAddress":10477373803}'
        )
        assert parser.session_state.journal_body_name == "Earth"
        assert parser.session_state.journal_body_id == 3

    def test_fileheader_clears(self, parser):
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(
            '{"timestamp":"2026-01-13T09:00:00Z","event":"Fileheader",'
            '"gameversion":"4.0.0.1","build":"r293895/r0 "}'
        )
        assert parser.session_state.journal_body_name == ""
        assert parser.session_state.journal_body_id is None

    def test_event_without_body_key_leaves_state_untouched(self, parser):
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody",'
            '"StarSystem":"Sol","SystemAddress":10477373803,"Body":"Earth","BodyID":3}'
        )
        parser.parse_line(
            '{"timestamp":"2026-01-12T14:02:00Z","event":"Music","MusicTrack":"Exploration"}'
        )
        assert parser.session_state.journal_body_name == "Earth"
        assert parser.session_state.journal_body_id == 3

    def test_default_journal_body_state(self, parser):
        assert parser.session_state.journal_body_name == ""
        assert parser.session_state.journal_body_id is None
        assert parser.session_state.status_body_name is None


class TestParseAuxiliaryFile:
    def test_parse_market_file(self, parser):
        fixture = Path(__file__).parent / "fixtures" / "Market.json"
        data = parser.parse_auxiliary_file(str(fixture))

        assert data is not None
        assert data["event"] == "Market"
        assert data["StationName"] == "Jameson Memorial"

    def test_parse_outfitting_file(self, parser):
        fixture = Path(__file__).parent / "fixtures" / "Outfitting.json"
        data = parser.parse_auxiliary_file(str(fixture))

        assert data is not None
        assert data["event"] == "Outfitting"
        assert len(data["Items"]) == 2

    def test_parse_shipyard_file(self, parser):
        fixture = Path(__file__).parent / "fixtures" / "Shipyard.json"
        data = parser.parse_auxiliary_file(str(fixture))

        assert data is not None
        assert data["event"] == "Shipyard"
        assert len(data["PriceList"]) == 2

    def test_parse_navroute_file(self, parser):
        fixture = Path(__file__).parent / "fixtures" / "NavRoute.json"
        data = parser.parse_auxiliary_file(str(fixture))

        assert data is not None
        assert data["event"] == "NavRoute"
        assert len(data["Route"]) == 2

    def test_missing_auxiliary_file(self, parser):
        fixture = Path(__file__).parent / "fixtures" / "DoesNotExist.json"
        assert parser.parse_auxiliary_file(str(fixture)) is None

    def test_invalid_auxiliary_json(self, parser, tmp_path):
        invalid_file = tmp_path / "broken.json"
        invalid_file.write_text("{broken", encoding="utf-8")

        assert parser.parse_auxiliary_file(str(invalid_file)) is None
