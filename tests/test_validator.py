"""Tests for the EDDNValidator module — updated for EDDN schema fix."""

import pytest

from src.modules.constants import (
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
    EDDN_CODEXENTRY_1_SCHEMA_REF,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF,
    EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF,
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF,
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)
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
                "JumpDist": 15.123,
                "FuelUsed": 2.345,
                "FuelLevel": 28.655,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        assert validator.validate(event) is False

    def test_valid_scan_with_session_state(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:10:45Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "Sol",
                "DistanceFromArrivalLS": 0.0,
                "SystemAddress": 10477373803,
            },
            event_type="Scan",
            timestamp="2026-01-12T12:10:45Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is True

    def test_scan_rejected_without_session_state(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:10:45Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "Sol",
                "DistanceFromArrivalLS": 0.0,
                "SystemAddress": 10477373803,
            },
            event_type="Scan",
            timestamp="2026-01-12T12:10:45Z",
        )
        assert validator.validate(event) is False

    def test_scan_rejected_with_wrong_system(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:10:45Z",
                "event": "Scan",
                "ScanType": "Detailed",
                "BodyName": "Sol",
                "DistanceFromArrivalLS": 0.0,
                "SystemAddress": 99999,
            },
            event_type="Scan",
            timestamp="2026-01-12T12:10:45Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is False

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

    def test_valid_docked_with_session_state(self, validator):
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
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is True

    def test_docked_rejected_without_session_state(self, validator):
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
        assert validator.validate(event) is False

    def test_unknown_event_type(self, validator):
        event = ParsedEvent(
            raw={"timestamp": "2026-01-12T12:00:00Z", "event": "SupercruiseEntry"},
            event_type="SupercruiseEntry",
            timestamp="2026-01-12T12:00:00Z",
        )
        assert validator.validate(event) is False

    def test_saa_signals_found_valid(self, validator):
        """SAASignalsFound is a journal/1 event requiring StarSystem and SystemAddress."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:05:00Z",
                "event": "SAASignalsFound",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
            },
            event_type="SAASignalsFound",
            timestamp="2026-01-12T14:05:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is True

    def test_saa_signals_found_missing_starsystem(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:05:00Z",
                "event": "SAASignalsFound",
                "SystemAddress": 10477373803,
            },
            event_type="SAASignalsFound",
            timestamp="2026-01-12T14:05:00Z",
        )
        assert validator.validate(event) is False

    @pytest.mark.parametrize(
        ("event_type", "required_field", "complete_raw"),
        [
            ("CarrierJump", "StarPos", {
                "timestamp": "2026-01-12T14:02:00Z",
                "event": "CarrierJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
            }),
            ("FSSSignalDiscovered", "SignalName", {
                "timestamp": "2026-01-12T14:03:00Z",
                "event": "FSSSignalDiscovered",
                "SystemAddress": 10477373803,
            }),
            ("FSSDiscoveryScan", "SystemAddress", {
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "StarSystem": "Sol",
                "BodyCount": 21,
                "NonBodyCount": 42,
            }),
            ("CodexEntry", "Name", {
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "Region": "TestRegion",
                "EntryID": 123,
                "SystemAddress": 10477373803,
            }),
        ],
    )
    def test_missing_required_field_rejected(self, validator, event_type, required_field, complete_raw):
        """Each event must fail validation when a required field is missing."""
        event = ParsedEvent(raw=complete_raw, event_type=event_type, timestamp=complete_raw["timestamp"])
        assert validator.validate(event) is False

    def test_approach_settlement_requires_station_name_or_name(self, validator):
        """ApproachSettlement requires StationName (journal) or Name (after rename)."""
        raw = {
            "timestamp": "2026-01-12T14:01:20Z",
            "event": "ApproachSettlement",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "BodyID": 1,
            "BodyName": "Earth",
            "MarketID": 128666762,
            "Latitude": 42.0,
            "Longitude": -7.0,
        }
        event = ParsedEvent(raw=raw, event_type="ApproachSettlement", timestamp=raw["timestamp"])
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        # Neither StationName nor Name present - should fail
        assert validator.validate(event, session_state) is False

    def test_approach_settlement_valid_with_station_name(self, validator):
        """ApproachSettlement with StationName (from journal) should validate."""
        raw = {
            "timestamp": "2026-01-12T14:01:20Z",
            "event": "ApproachSettlement",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "StationName": "Galileo",
            "BodyID": 1,
            "BodyName": "Earth",
            "MarketID": 128666762,
            "Latitude": 42.0,
            "Longitude": -7.0,
        }
        event = ParsedEvent(raw=raw, event_type="ApproachSettlement", timestamp=raw["timestamp"])
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is True

    def test_approach_settlement_valid_with_name(self, validator):
        """ApproachSettlement with Name (already renamed) should also validate."""
        raw = {
            "timestamp": "2026-01-12T14:01:20Z",
            "event": "ApproachSettlement",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "Name": "Galileo",
            "BodyID": 1,
            "BodyName": "Earth",
            "MarketID": 128666762,
            "Latitude": 42.0,
            "Longitude": -7.0,
        }
        event = ParsedEvent(raw=raw, event_type="ApproachSettlement", timestamp=raw["timestamp"])
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is True


class TestValidateNewJournalEvents:
    def test_valid_navroute(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:00:00Z",
                "event": "NavRoute",
                "Route": [{"StarSystem": "Sol", "SystemAddress": 10477373803}],
            },
            event_type="NavRoute",
            timestamp="2026-01-12T14:00:00Z",
        )
        assert validator.validate(event) is True

    def test_navroute_requires_systemaddress_in_route(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:00:00Z",
                "event": "NavRoute",
                "Route": [{"StarSystem": "Sol"}],
            },
            event_type="NavRoute",
            timestamp="2026-01-12T14:00:00Z",
        )
        assert validator.validate(event) is False

    def test_navroute_empty_route_rejected(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:00:00Z",
                "event": "NavRoute",
                "Route": [],
            },
            event_type="NavRoute",
            timestamp="2026-01-12T14:00:00Z",
        )
        assert validator.validate(event) is False

    @pytest.mark.parametrize(
        ("event_type", "raw"),
        [
            (
                "CarrierJump",
                {
                    "timestamp": "2026-01-12T14:02:00Z",
                    "event": "CarrierJump",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "StarPos": [0.0, 0.0, 0.0],
                },
            ),
            (
                "SAASignalsFound",
                {
                    "timestamp": "2026-01-12T14:05:00Z",
                    "event": "SAASignalsFound",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                },
            ),
        ],
    )
    def test_valid_journal1_events_with_session_state(self, validator, event_type, raw):
        """Journal/1 events lacking StarPos need session_state for validation."""
        event = ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        assert validator.validate(event, session_state) is True

    def test_valid_navbeaconscan_with_session_state(self, validator):
        """NavBeaconScan requires timestamp and NumBodies; StarPos augmented from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        assert validator.validate(event, session_state) is True

    def test_navbeaconscan_rejected_without_num_bodies(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        assert validator.validate(event) is False

    def test_navbeaconscan_rejected_without_session_state(self, validator):
        """NavBeaconScan needs StarPos augmentation from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        assert validator.validate(event) is False

    def test_navbeaconscan_rejected_wrong_system(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 99999,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is False

    @pytest.mark.parametrize(
        ("event_type", "raw"),
        [
            (
                "FSSSignalDiscovered",
                {
                    "timestamp": "2026-01-12T14:03:00Z",
                    "event": "FSSSignalDiscovered",
                    "SystemAddress": 10477373803,
                    "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;",
                },
            ),
            (
                "FSSDiscoveryScan",
                {
                    "timestamp": "2026-01-12T12:15:00Z",
                    "event": "FSSDiscoveryScan",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "BodyCount": 21,
                    "NonBodyCount": 42,
                },
            ),
            (
                "ApproachSettlement",
                {
                    "timestamp": "2026-01-12T14:01:20Z",
                    "event": "ApproachSettlement",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "Name": "Galileo",
                    "BodyID": 1,
                    "BodyName": "Earth",
                    "MarketID": 128666762,
                    "Latitude": 42.0,
                    "Longitude": -7.0,
                },
            ),
            (
                "CodexEntry",
                {
                    "timestamp": "2026-01-12T15:00:00Z",
                    "event": "CodexEntry",
                    "SystemAddress": 10477373803,
                    "Name": "$Codex_Ent_Name_1;",
                    "Region": "TestRegion",
                    "EntryID": 123,
                    "BodyID": 1,
                    "BodyName": "Earth",
                },
            ),
            (
                "FSSAllBodiesFound",
                {
                    "timestamp": "2026-01-12T16:00:00Z",
                    "event": "FSSAllBodiesFound",
                    "SystemName": "Sol",
                    "SystemAddress": 10477373803,
                    "Count": 21,
                },
            ),
        ],
    )
    def test_valid_dedicated_schema_events_with_session_state(self, validator, event_type, raw):
        """Dedicated schema events needing StarPos require session_state."""
        event = ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        assert validator.validate(event, session_state) is True


class TestTransform:
    """Tests for journal/1 transform method."""

    def test_strips_disallowed_fields(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "ActiveFine": True,
                "Wanted": True,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)

        assert "ActiveFine" not in message["message"]
        assert "Wanted" not in message["message"]
        assert message["message"]["StarSystem"] == "Sol"

    def test_strips_localised_fields_top_level(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "Docked",
                "StationName": "Jameson Memorial",
                "StarSystem": "Shinrarta Dezhra",
                "SystemAddress": 10477373803,
                "StationGovernment": "$government_Democracy;",
                "StationGovernment_Localised": "Democracy",
            },
            event_type="Docked",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        assert "StationGovernment_Localised" not in message["message"]
        assert "StationGovernment" in message["message"]

    def test_strips_localised_fields_in_nested_dict(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "Docked",
                "StationName": "Test",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StationFaction": {
                    "Name": "Test Faction",
                    "FactionState": "Boom",
                    "Happiness_Localised": "Happy",
                },
            },
            event_type="Docked",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        faction = message["message"]["StationFaction"]
        assert "Happiness_Localised" not in faction
        assert "Name" in faction

    def test_strips_localised_fields_in_array(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:50:00Z",
                "event": "Location",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Factions": [
                    {
                        "Name": "Federation",
                        "Government": "$government_Democracy;",
                        "Government_Localised": "Democracy",
                        "Happiness": "$Faction_HappinessBand2;",
                        "Happiness_Localised": "Happy",
                    },
                    {
                        "Name": "Alliance",
                        "Government": "$government_Cooperative;",
                        "Government_Localised": "Cooperative",
                    },
                ],
                "StationEconomies": [
                    {
                        "Name": "$economy_Industrial;",
                        "Name_Localised": "Industrial",
                        "Proportion": 4.2,
                    },
                ],
            },
            event_type="Location",
            timestamp="2026-01-12T12:50:00Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        for faction in message["message"]["Factions"]:
            assert "Government_Localised" not in faction
            assert "Happiness_Localised" not in faction
            assert "Government" in faction
        for economy in message["message"]["StationEconomies"]:
            assert "Name_Localised" not in economy
            assert "Name" in economy

    def test_strips_disallowed_in_nested_structures(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "Docked",
                "StationName": "Test",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StationFaction": {
                    "Name": "Test Faction",
                    "ActiveFine": True,
                    "Wanted": False,
                },
            },
            event_type="Docked",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        faction = message["message"]["StationFaction"]
        assert "ActiveFine" not in faction
        assert "Wanted" not in faction
        assert "Name" in faction

    def test_strips_factions_disallowed_fields(self, validator):
        """MyReputation and other Factions-specific disallowed fields are stripped."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:50:00Z",
                "event": "Location",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Factions": [
                    {
                        "Name": "Piegua Rats",
                        "FactionState": "None",
                        "Government": "Anarchy",
                        "Influence": 0.04,
                        "Allegiance": "Independent",
                        "Happiness": "$Faction_HappinessBand2;",
                        "MyReputation": 56.52,
                        "HappiestSystem": "Sol",
                        "HomeSystem": "Sol",
                        "SquadronFaction": "Yes",
                    },
                    {
                        "Name": "The Forge",
                        "FactionState": "Expansion",
                        "Government": "Cooperative",
                        "Influence": 0.65,
                        "Allegiance": "Independent",
                        "MyReputation": 100.0,
                    },
                ],
            },
            event_type="Location",
            timestamp="2026-01-12T12:50:00Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        for faction in message["message"]["Factions"]:
            assert "MyReputation" not in faction
            assert "HappiestSystem" not in faction
            assert "HomeSystem" not in faction
            assert "SquadronFaction" not in faction
            assert "Name" in faction
            assert "Influence" in faction

    def test_augments_starpos_from_session_state(self, validator):
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
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Shinrarta Dezhra",
        )
        message = validator.transform(event, session_state)

        assert message["message"]["StarPos"] == [0.0, 0.0, 0.0]
        assert message["message"]["StarSystem"] == "Shinrarta Dezhra"

    def test_does_not_augment_starpos_if_system_mismatch(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T13:00:00Z",
                "event": "Docked",
                "StationName": "Jameson Memorial",
                "StarSystem": "Sol",
                "SystemAddress": 99999,
            },
            event_type="Docked",
            timestamp="2026-01-12T13:00:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        message = validator.transform(event, session_state)

        assert "StarPos" not in message["message"]

    def test_augments_horizons_odyssey(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform(event, session_state)

        assert message["message"]["horizons"] is True
        assert message["message"]["odyssey"] is False

    def test_omits_horizons_odyssey_when_unknown(self, validator):
        """No LoadGame observed yet: EDDN requires omitting the keys, never guessing."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState()
        message = validator.transform(event, session_state)

        assert "horizons" not in message["message"]
        assert "odyssey" not in message["message"]

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

    def test_transform_carrier_jump(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:02:00Z",
                "event": "CarrierJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="CarrierJump",
            timestamp="2026-01-12T14:02:00Z",
        )
        message = validator.transform(event, SessionState(horizons=True, odyssey=True))

        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF
        assert message["message"]["event"] == "CarrierJump"
        assert message["message"]["StarSystem"] == "Sol"

    def test_latitude_longitude_stripped_in_journal1(self, validator):
        """Latitude and Longitude must be stripped in journal/1 context."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Latitude": 42.0,
                "Longitude": -7.0,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)

        assert "Latitude" not in message["message"]
        assert "Longitude" not in message["message"]

    def test_voucher_amount_stripped_in_journal1(self, validator):
        """VoucherAmount must be stripped in journal/1 context."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "VoucherAmount": 5000,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)

        assert "VoucherAmount" not in message["message"]

    def test_traits_stripped_in_journal1(self, validator):
        """Traits must be stripped in journal/1 context."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:05:30Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Traits": ["trait1"],
                "IsNewEntry": True,
                "NewTraitsDiscovered": False,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:05:30Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)

        assert "Traits" not in message["message"]
        assert "IsNewEntry" not in message["message"]
        assert "NewTraitsDiscovered" not in message["message"]


class TestTransformFSSSignalDiscovered:
    """Tests for transform_fss_signal_discovered method."""

    def _make_batch(self, signals=None, **kwargs):
        """Helper to build a batch dict for the transform."""
        batch = {
            "signals": signals if signals is not None else [{"SignalName": "TestSignal"}],
            "last_timestamp": kwargs.get("last_timestamp", "2026-01-12T14:03:05Z"),
            "system_address": kwargs.get("system_address", 10477373803),
            "star_system": kwargs.get("star_system", "Sol"),
            "star_pos": kwargs.get("star_pos", [0.0, 0.0, 0.0]),
        }
        return batch  # noqa: RET504

    def test_valid_batch(self, validator):
        batch = self._make_batch(signals=[
            {"SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;"},
            {"SignalName": "TestSignal", "IsStation": True},
        ])
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_signal_discovered(batch, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF
        assert len(message["message"]["signals"]) == 2
        assert message["message"]["signals"][0]["SignalName"] == "$MULTIPLAYER_SCENARIO42_TITLE;"
        assert message["message"]["signals"][1]["SignalName"] == "TestSignal"
        assert message["message"]["signals"][1]["IsStation"] is True

    def test_empty_batch_returns_none(self, validator):
        batch = self._make_batch(signals=[])
        session_state = SessionState()
        assert validator.transform_fss_signal_discovered(batch, session_state) is None

    def test_schema_ref(self, validator):
        batch = self._make_batch()
        session_state = SessionState()
        message = validator.transform_fss_signal_discovered(batch, session_state)
        assert message["$schemaRef"] == EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF

    def test_preserves_signal_fields(self, validator):
        signals = [{
            "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;",
            "IsStation": True,
            "USSType": "$USS_Type_Debris;",
            "SpawningState": "$FactionState_Boom;",
            "SpawningFaction": "Test Faction",
            "ThreatLevel": 2,
            "SignalType": "USS",
            "SpawningPower": "Aisling Duval",
            "OpposingPower": "Zachary Hudson",
        }]
        batch = self._make_batch(signals=signals)
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_fss_signal_discovered(batch, session_state)

        signal = message["message"]["signals"][0]
        assert signal["SignalName"] == "$MULTIPLAYER_SCENARIO42_TITLE;"
        assert signal["IsStation"] is True
        assert signal["USSType"] == "$USS_Type_Debris;"
        assert signal["SpawningState"] == "$FactionState_Boom;"
        assert signal["SpawningFaction"] == "Test Faction"
        assert signal["ThreatLevel"] == 2
        assert signal["SignalType"] == "USS"
        assert signal["SpawningPower"] == "Aisling Duval"
        assert signal["OpposingPower"] == "Zachary Hudson"

    def test_augments_star_pos_from_session_state(self, validator):
        """When batch has star_pos=None, the transform uses whatever the batch provides."""
        # Note: As of the batcher refactor, the batcher handles augmentation.
        # The transform now simply uses the values from the batch.
        batch = self._make_batch(star_pos=[1.0, 2.0, 3.0])
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_fss_signal_discovered(batch, session_state)
        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]

    def test_message_level_fields(self, validator):
        batch = self._make_batch()
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_fss_signal_discovered(batch, session_state)

        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T14:03:05Z"
        assert payload["event"] == "FSSSignalDiscovered"
        assert payload["StarSystem"] == "Sol"
        assert payload["SystemAddress"] == 10477373803
        assert payload["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["horizons"] is True
        assert payload["odyssey"] is False

    def test_localised_keys_stripped_from_signals(self, validator):
        signals = [{
            "SignalName": "$Test;",
            "SignalName_Localised": "Test",
            "SpawningState": "$Boom;",
            "SpawningState_Localised": "Boom",
        }]
        batch = self._make_batch(signals=signals)
        session_state = SessionState()
        message = validator.transform_fss_signal_discovered(batch, session_state)

        signal = message["message"]["signals"][0]
        assert "SignalName_Localised" not in signal
        assert "SpawningState_Localised" not in signal
        assert signal["SignalName"] == "$Test;"
        assert signal["SpawningState"] == "$Boom;"


class TestTransformFSSDiscoveryScan:
    """Tests for transform_fss_discovery_scan method."""

    def test_valid_event(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "BodyCount": 21,
                "NonBodyCount": 42,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T12:15:00Z"
        assert payload["SystemName"] == "Sol"
        assert "StarSystem" not in payload
        assert payload["SystemAddress"] == 10477373803
        assert payload["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["BodyCount"] == 21
        assert payload["NonBodyCount"] == 42
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "BodyCount": 1,
                "NonBodyCount": 0,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        message = validator.transform_fss_discovery_scan(event, session_state)
        assert message["$schemaRef"] == EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF

    def test_augments_star_pos_from_session_state(self, validator):
        """FSSDiscoveryScan often lacks StarPos; should be augmented from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "BodyCount": 21,
                "NonBodyCount": 42,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]

    def test_augments_system_name_from_session_state(self, validator):
        """If event lacks SystemName, it should be augmented from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemAddress": 10477373803,
                "BodyCount": 21,
                "NonBodyCount": 42,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert message["message"]["SystemName"] == "Sol"
        assert "StarSystem" not in message["message"]

    def test_does_not_inject_star_system(self, validator):
        """fssdiscoveryscan/1 uses SystemName, not StarSystem."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "BodyCount": 21,
                "NonBodyCount": 42,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(
            star_system="Sol",
        )
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert "StarSystem" not in message["message"]
        assert message["message"]["SystemName"] == "Sol"
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "BodyCount": 21,
                "NonBodyCount": 42,
                "ActiveFine": True,
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert "ActiveFine" not in message["message"]

    def test_preserves_system_name(self, validator):
        """EDDN fssdiscoveryscan/1 schema uses SystemName (same as journal), not StarSystem."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "BodyCount": 21,
                "NonBodyCount": 42,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert message is not None
        payload = message["message"]
        assert payload["SystemName"] == "Sol"
        assert "StarSystem" not in payload

    def test_strips_progress_personal_data(self, validator):
        """Progress contains personal scan data and must be stripped per fssdiscoveryscan/1 schema."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:15:00Z",
                "event": "FSSDiscoveryScan",
                "SystemAddress": 10477373803,
                "SystemName": "Sol",
                "BodyCount": 8,
                "NonBodyCount": 42,
                "StarPos": [0.0, 0.0, 0.0],
                "Progress": {
                    "TotalScans": 50,
                    "ScannedBodies": ["Sol A", "Sol B"],
                },
            },
            event_type="FSSDiscoveryScan",
            timestamp="2026-01-12T12:15:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_discovery_scan(event, session_state)

        assert message is not None
        assert "Progress" not in message["message"]


class TestTransformNavRoute:
    """Tests for transform_navroute method."""

    def test_valid_data(self, validator, load_fixture):
        navroute_data = load_fixture("NavRoute.json")
        session_state = SessionState(horizons=True, odyssey=True)

        message = validator.transform_navroute(navroute_data, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_NAVROUTE_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T14:00:00Z"
        assert payload["event"] == "NavRoute"
        assert len(payload["Route"]) == 2
        # Route entries should have StarClass and StarPos
        assert payload["Route"][0]["StarClass"] == "G"
        assert payload["Route"][0]["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["Route"][1]["StarClass"] == "B"
        assert payload["Route"][1]["StarPos"] == [-3.09375, -0.09375, 3.03125]
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator, load_fixture):
        navroute_data = load_fixture("NavRoute.json")
        session_state = SessionState()
        message = validator.transform_navroute(navroute_data, session_state)
        assert message["$schemaRef"] == EDDN_NAVROUTE_1_SCHEMA_REF

    def test_no_message_level_star_system_star_pos_system_address(self, validator, load_fixture):
        """NavRoute/1 schema only allows timestamp, event, Route, horizons, odyssey at message level.
        StarSystem/StarPos/SystemAddress must only be in Route entries, not at message level."""
        navroute_data = load_fixture("NavRoute.json")
        # Even if session_state has these, they should NOT be augmented at message level
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_navroute(navroute_data, session_state)

        payload = message["message"]
        assert "StarSystem" not in payload
        assert "StarPos" not in payload
        assert "SystemAddress" not in payload
        # But Route entries should still have them
        assert payload["Route"][0]["StarSystem"] == "Sol"
        assert payload["Route"][0]["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["Route"][0]["SystemAddress"] == 10477373803

    def test_strips_localised_from_route_entries(self, validator):
        """_Localised keys in Route entries should be stripped."""
        navroute_data = {
            "timestamp": "2026-01-12T14:00:00Z",
            "event": "NavRoute",
            "Route": [
                {
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "StarPos": [0.0, 0.0, 0.0],
                    "StarClass": "G",
                    "StarSystem_Localised": "Sol",
                },
            ],
        }
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_navroute(navroute_data, session_state)

        route_entry = message["message"]["Route"][0]
        assert "StarSystem_Localised" not in route_entry
        assert "StarSystem" in route_entry

    def test_navroute_clear_returns_none(self, validator):
        """NavRouteClear should be skipped — it's not a valid NavRoute submission."""
        navroute_clear_data = {
            "timestamp": "2026-01-12T14:00:00Z",
            "event": "NavRouteClear",
            "Route": [],
        }
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_navroute(navroute_clear_data, session_state)

        assert message is None


class TestTransformApproachSettlement:
    """Tests for transform_approach_settlement method."""

    def test_preserves_latitude_longitude(self, validator):
        """Latitude and Longitude must be preserved for approachsettlement/1."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "Name": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        payload = message["message"]
        assert payload["Latitude"] == 42.0
        assert payload["Longitude"] == -7.0

    def test_renames_station_name_to_name(self, validator):
        """StationName should be renamed to Name in approachsettlement/1 schema."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StationName": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        payload = message["message"]
        assert "StationName" not in payload
        assert payload["Name"] == "Galileo"

    def test_drops_station_name_when_name_present(self, validator):
        """If both StationName and Name exist, keep Name and drop StationName."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StationName": "Galileo",
                "Name": "Galileo Base",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        payload = message["message"]
        assert "StationName" not in payload
        assert payload["Name"] == "Galileo Base"

    def test_schema_ref(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "Name": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        assert message["$schemaRef"] == EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF

    def test_augments_star_pos_from_session_state(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "Name": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_approach_settlement(event, session_state)

        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]

    def test_strips_other_disallowed_fields(self, validator):
        """Fields like ActiveFine should still be stripped even though Latitude/Longitude are kept."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "Name": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
                "ActiveFine": True,
                "Wanted": True,
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        assert "ActiveFine" not in message["message"]
        assert "Wanted" not in message["message"]
        assert message["message"]["Latitude"] == 42.0
        assert message["message"]["Longitude"] == -7.0

    def test_strips_localised_keys(self, validator):
        """_Localised keys should be stripped from approachsettlement/1 messages."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "Name": "Galileo",
                "BodyID": 1,
                "BodyName": "Earth",
                "MarketID": 128666762,
                "Latitude": 42.0,
                "Longitude": -7.0,
                "StarPos": [0.0, 0.0, 0.0],
                "BodyName_Localised": "Earth",
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T14:01:20Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)

        assert "BodyName_Localised" not in message["message"]


class TestTransformCodexEntry:
    """Tests for transform_codex_entry method."""

    def test_valid_event(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_CODEXENTRY_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T15:00:00Z"
        assert payload["Name"] == "$Codex_Ent_Name_1;"
        assert payload["Region"] == "TestRegion"
        assert payload["EntryID"] == 123
        assert payload["BodyID"] == 1
        assert payload["BodyName"] == "Earth"
        assert payload["StarSystem"] == "Sol"
        assert payload["SystemAddress"] == 10477373803
        assert payload["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_codex_entry(event, session_state)
        assert message["$schemaRef"] == EDDN_CODEXENTRY_1_SCHEMA_REF

    def test_preserves_voucher_amount(self, validator):
        """VoucherAmount is valid in codexentry/1 but disallowed in journal/1."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
                "VoucherAmount": 5000,
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert message["message"]["VoucherAmount"] == 5000

    def test_preserves_traits(self, validator):
        """Traits is valid in codexentry/1 but disallowed in journal/1."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
                "Traits": ["trait1", "trait2"],
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert message["message"]["Traits"] == ["trait1", "trait2"]

    def test_strips_is_new_entry(self, validator):
        """IsNewEntry is disallowed in codexentry/1 (personal data)."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
                "IsNewEntry": True,
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert "IsNewEntry" not in message["message"]

    def test_strips_new_traits_discovered(self, validator):
        """NewTraitsDiscovered is disallowed in codexentry/1 (personal data)."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
                "NewTraitsDiscovered": False,
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert "NewTraitsDiscovered" not in message["message"]

    def test_augments_star_pos_from_session_state(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_codex_entry(event, session_state)

        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]
        assert message["message"]["StarSystem"] == "Sol"

    def test_strips_localised_keys(self, validator):
        """_Localised keys should be stripped from codexentry/1 messages."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "Name": "$Codex_Ent_Name_1;",
                "Name_Localised": "Some Name",
                "Region": "TestRegion",
                "EntryID": 123,
                "BodyID": 1,
                "BodyName": "Earth",
                "StarSystem": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)

        assert "Name_Localised" not in message["message"]
        assert message["message"]["Name"] == "$Codex_Ent_Name_1;"


class TestTransformCommodity:
    def test_transform_market_data(self, validator, load_fixture):
        market_data = load_fixture("Market.json")
        session_state = SessionState(horizons=True, odyssey=False)

        message = validator.transform_commodity(market_data, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_COMMODITY_3_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T13:05:00Z"
        assert payload["systemName"] == "Shinrarta Dezhra"
        assert payload["stationName"] == "Jameson Memorial"
        assert payload["marketId"] == 128666762
        assert payload["horizons"] is True
        assert payload["odyssey"] is False
        assert len(payload["commodities"]) == 2
        assert payload["commodities"][0] == {
            "name": "hydrogenfuel",
            "meanPrice": 87,
            "buyPrice": 90,
            "stock": 1234567,
            "stockBracket": 3,
            "sellPrice": 85,
            "demand": 0,
            "demandBracket": 0,
        }
        assert payload["commodities"][1] == {
            "name": "gold",
            "meanPrice": 47113,
            "buyPrice": 0,
            "stock": 0,
            "stockBracket": 0,
            "sellPrice": 48632,
            "demand": 166200,
            "demandBracket": 3,
            "statusFlags": ["powerplay"],
        }

    def test_transform_commodity_deduplicates_status_flags(self, validator):
        """EDDN commodity/3 declares uniqueItems on each commodity's statusFlags."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {
                    "Name": "$gold_name;",
                    "MeanPrice": 47113,
                    "SellPrice": 48632,
                    "Demand": 166200,
                    "DemandBracket": 3,
                    "StatusFlags": ["powerplay", "producer", "powerplay"],
                },
            ],
        }

        message = validator.transform_commodity(market_data, SessionState())

        assert message is not None
        assert message["message"]["commodities"][0]["statusFlags"] == ["powerplay", "producer"]

    def test_transform_commodity_includes_station_type_and_carrier_docking_access(self, validator):
        """EDDN commodity/3 now allows stationType and carrierDockingAccess (both optional)."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Carrier",
            "StationType": "FleetCarrier",
            "MarketID": 123,
            "CarrierDockingAccess": "all",
            "Items": [
                {
                    "Name": "$gold_name;",
                    "MeanPrice": 47113,
                    "SellPrice": 48632,
                    "Demand": 166200,
                    "DemandBracket": 3,
                },
            ],
        }

        message = validator.transform_commodity(market_data, SessionState())

        assert message is not None
        assert message["message"]["stationType"] == "FleetCarrier"
        assert message["message"]["carrierDockingAccess"] == "all"

    def test_transform_commodity_omits_station_type_and_carrier_docking_access_when_absent(self, validator):
        """Neither field has any journal-side source when not present on the entry."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {
                    "Name": "$gold_name;",
                    "MeanPrice": 47113,
                    "SellPrice": 48632,
                    "Demand": 166200,
                    "DemandBracket": 3,
                },
            ],
        }

        message = validator.transform_commodity(market_data, SessionState())

        assert message is not None
        assert "stationType" not in message["message"]
        assert "carrierDockingAccess" not in message["message"]

    def test_transform_commodity_survives_unhashable_status_flags(self, validator):
        """A malformed StatusFlags entry must not crash the transform.

        Deduping uses a set, so a non-hashable entry would raise where the
        old pass-through could not.  A journal this malformed will be
        rejected by EDDN on its own merits; losing the rest of the batch to
        a TypeError would be worse.
        """
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {
                    "Name": "$gold_name;",
                    "SellPrice": 48632,
                    "DemandBracket": 3,
                    "StatusFlags": ["powerplay", {"unexpected": "object"}, "powerplay"],
                },
            ],
        }

        message = validator.transform_commodity(market_data, SessionState())

        assert message is not None
        assert message["message"]["commodities"][0]["statusFlags"] == [
            "powerplay",
            {"unexpected": "object"},
        ]

    def test_transform_commodity_empty_returns_none(self, validator):
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [
                {"Name": "junk", "StockBracket": 0, "DemandBracket": 0},
            ],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_no_items_returns_none(self, validator):
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_missing_starsystem_returns_none(self, validator):
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_missing_marketid_returns_none(self, validator):
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_empty_stationname_returns_none(self, validator):
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "",
            "MarketID": 123,
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_nonmarketable_category_filtered(self, validator):
        """NonMarketable items must be excluded per EDDN commodity-README."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                # NonMarketable with high stock bracket — should be filtered
                {
                    "Name": "$drones_name;",
                    "Category": "$u16_nondeMarketable_name;",
                    "BuyPrice": 101,
                    "SellPrice": 95,
                    "MeanPrice": 99,
                    "Stock": 9999,
                    "Demand": 0,
                    "StockBracket": 3,
                    "DemandBracket": 0,
                },
                # Normal commodity — should pass through
                {
                    "Name": "$hydrogenfuel_name;",
                    "Category": "$u17_chemicals_name;",
                    "BuyPrice": 90,
                    "SellPrice": 85,
                    "MeanPrice": 87,
                    "Stock": 1234,
                    "Demand": 0,
                    "StockBracket": 3,
                    "DemandBracket": 0,
                },
            ],
        }
        message = validator.transform_commodity(market_data, SessionState())
        assert message is not None
        assert len(message["message"]["commodities"]) == 1
        assert message["message"]["commodities"][0]["name"] == "hydrogenfuel"

    def test_nonmarketable_all_items_filtered(self, validator):
        """If all items are NonMarketable, transform returns None."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {
                    "Name": "$drones_name;",
                    "Category": "$u16_nondeMarketable_name;",
                    "BuyPrice": 101, "SellPrice": 95,
                    "MeanPrice": 99, "Stock": 9999, "Demand": 0,
                    "StockBracket": 3, "DemandBracket": 0,
                },
            ],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_commodity_name_sanitization(self, validator):
        """Commodity names with $..._name; format should be sanitized."""
        from src.modules.validator import _sanitize_eddn_name

        # Commodity names: strip $..._name; format
        assert _sanitize_eddn_name("$platinum_name;") == "platinum"
        assert _sanitize_eddn_name("$lowtemperaturediamond_name;") == "lowtemperaturediamond"
        assert _sanitize_eddn_name("$fruitandvegetables_name;") == "fruitandvegetables"
        assert _sanitize_eddn_name("$metaalloys_name;") == "metaalloys"
        # Ship types: strip $..._name; format
        assert _sanitize_eddn_name("$SideWinder_name;") == "SideWinder"
        assert _sanitize_eddn_name("$eagle_name;") == "eagle"
        # Already-clean names pass through unchanged
        assert _sanitize_eddn_name("hydrogenfuel") == "hydrogenfuel"
        assert _sanitize_eddn_name("drones") == "drones"
        assert _sanitize_eddn_name("int_cargo_rack_size6_class1") == "int_cargo_rack_size6_class1"
        # Names with $ prefix but only trailing ; (e.g. rare format)
        assert _sanitize_eddn_name("$something;") == "something"


class TestTransformOutfitting:
    def test_transform_outfitting_data(self, validator, load_fixture):
        outfitting_data = load_fixture("Outfitting.json")
        session_state = SessionState(horizons=False, odyssey=True)

        message = validator.transform_outfitting(outfitting_data, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_OUTFITTING_2_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T13:05:00Z"
        assert payload["systemName"] == "Shinrarta Dezhra"
        assert payload["stationName"] == "Jameson Memorial"
        assert payload["marketId"] == 128666762
        assert payload["modules"] == [
            "int_cargo_rack_size6_class1",
            "int_shieldgenerator_size8_class5_fast",
        ]
        assert payload["horizons"] is False
        assert payload["odyssey"] is True

    def test_transform_outfitting_deduplicates_module_names(self, validator):
        """EDDN outfitting/2 declares uniqueItems on `modules`.

        Elite lists the same module under several `id`s when it is purchasable
        with both credits and Powerplay merc coins.  Those entries differ only
        in fields EDDN does not carry, so they collapse into duplicate names.
        """
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {"id": 128049489, "Name": "hpt_railgun_fixed_medium", "BuyPrice": 402480},
                {"id": 128666724, "Name": "int_cargo_rack_size6_class1", "BuyPrice": 1000},
                {"id": 129044375, "Name": "hpt_railgun_fixed_medium", "BuyMercCoinsPrice": 950},
            ],
        }

        message = validator.transform_outfitting(outfitting_data, SessionState())

        assert message is not None
        assert message["message"]["modules"] == [
            "hpt_railgun_fixed_medium",
            "int_cargo_rack_size6_class1",
        ]

    def test_transform_outfitting_elides_planet_approach_suite(self, validator):
        """EDDN outfitting-README Elisions: Int_PlanetApproachSuite must be
        removed 'for historical reasons'. Match EDMC: exact, case-insensitive
        match on the sanitised module name — the _advanced variant is kept.
        """
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {"Name": "Int_PlanetApproachSuite"},
                {"Name": "int_planetapproachsuite_advanced"},
                {"Name": "int_cargo_rack_size6_class1"},
            ],
        }

        message = validator.transform_outfitting(outfitting_data, SessionState())

        assert message is not None
        assert message["message"]["modules"] == [
            "int_planetapproachsuite_advanced",
            "int_cargo_rack_size6_class1",
        ]

    def test_transform_outfitting_elided_module_only_returns_none(self, validator):
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [{"Name": "int_planetapproachsuite"}],
        }

        assert validator.transform_outfitting(outfitting_data, SessionState()) is None

    def test_transform_outfitting_deduplicates_after_name_sanitisation(self, validator):
        """Two raw names that sanitise to the same EDDN name are one module."""
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "Items": [
                {"Name": "$hpt_railgun_fixed_medium_name;"},
                {"Name": "hpt_railgun_fixed_medium"},
            ],
        }

        message = validator.transform_outfitting(outfitting_data, SessionState())

        assert message is not None
        assert message["message"]["modules"] == ["hpt_railgun_fixed_medium"]

    def test_transform_outfitting_empty_returns_none(self, validator):
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None

    def test_transform_outfitting_missing_starsystem_returns_none(self, validator):
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [{"Name": "test_module"}],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None

    def test_transform_outfitting_zero_marketid_returns_none(self, validator):
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 0,
            "Items": [{"Name": "test_module"}],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None


class TestTransformShipyard:
    def test_transform_shipyard_data(self, validator, load_fixture):
        shipyard_data = load_fixture("Shipyard.json")

        message = validator.transform_shipyard(shipyard_data, SessionState(horizons=True, odyssey=True))

        assert message is not None
        assert message["$schemaRef"] == EDDN_SHIPYARD_2_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T13:05:00Z"
        assert payload["systemName"] == "Shinrarta Dezhra"
        assert payload["stationName"] == "Jameson Memorial"
        assert payload["marketId"] == 128666762
        assert payload["ships"] == ["sidewinder", "eagle"]
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_transform_shipyard_deduplicates_ship_types(self, validator):
        """EDDN shipyard/2 declares uniqueItems on `ships`."""
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test Station",
            "MarketID": 123,
            "PriceList": [
                {"id": 128049249, "ShipType": "sidewinder", "ShipPrice": 32000},
                {"id": 128049255, "ShipType": "eagle", "ShipPrice": 44800},
                {"id": 128672138, "ShipType": "sidewinder", "ShipPrice": 32000},
            ],
        }

        message = validator.transform_shipyard(shipyard_data, SessionState())

        assert message is not None
        assert message["message"]["ships"] == ["sidewinder", "eagle"]

    def test_transform_shipyard_empty_returns_none(self, validator):
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "PriceList": [],
        }
        assert validator.transform_shipyard(shipyard_data, SessionState()) is None

    def test_transform_shipyard_missing_starsystem_returns_none(self, validator):
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "PriceList": [{"ShipType": "sidewinder"}],
        }
        assert validator.transform_shipyard(shipyard_data, SessionState()) is None

    def test_transform_shipyard_zero_marketid_returns_none(self, validator):
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 0,
            "PriceList": [{"ShipType": "sidewinder"}],
        }
        assert validator.transform_shipyard(shipyard_data, SessionState()) is None


class TestAsDictList:
    """Tests for the _as_dict_list helper function."""

    def test_normal_list(self):
        from src.modules.validator import _as_dict_list
        result = _as_dict_list([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_filters_non_dicts(self):
        from src.modules.validator import _as_dict_list
        result = _as_dict_list([{"a": 1}, "string", 42, None, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_non_list_returns_empty(self):
        from src.modules.validator import _as_dict_list
        assert _as_dict_list(None) == []
        assert _as_dict_list("not a list") == []
        assert _as_dict_list(42) == []

    def test_empty_list(self):
        from src.modules.validator import _as_dict_list
        assert _as_dict_list([]) == []


class TestTransformNavBeaconScan:
    """Tests for transform_navbeacon_scan method."""

    def test_valid_event(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
            horizons=True,
            odyssey=True,
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_NAVBEACONSCAN_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T12:20:00Z"
        assert payload["event"] == "NavBeaconScan"
        assert payload["SystemAddress"] == 10477373803
        assert payload["NumBodies"] == 21
        assert payload["StarSystem"] == "Sol"
        assert payload["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 8,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        message = validator.transform_navbeacon_scan(event, session_state)
        assert message["$schemaRef"] == EDDN_NAVBEACONSCAN_1_SCHEMA_REF

    def test_augments_star_pos_from_session_state(self, validator):
        """NavBeaconScan lacks StarPos; should be augmented from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]

    def test_augments_star_system_from_session_state(self, validator):
        """NavBeaconScan lacks StarSystem; should be augmented from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Alpha Centauri",
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert message["message"]["StarSystem"] == "Alpha Centauri"

    def test_does_not_augment_if_system_mismatch(self, validator):
        """StarPos/StarSystem should not be augmented if SystemAddress doesn't match."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 99999,
                "NumBodies": 21,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert "StarPos" not in message["message"]
        assert "StarSystem" not in message["message"]

    def test_strips_localised_keys(self, validator):
        """_Localised keys should be stripped from navbeaconscan/1 messages."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
                "SomeField_Localised": "Should be stripped",
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert "SomeField_Localised" not in message["message"]

    def test_preserves_disallowed_fields(self, validator):
        """Fields like ActiveFine should be stripped by _strip_disallowed."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:20:00Z",
                "event": "NavBeaconScan",
                "SystemAddress": 10477373803,
                "NumBodies": 21,
                "ActiveFine": True,
                "Wanted": False,
            },
            event_type="NavBeaconScan",
            timestamp="2026-01-12T12:20:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_navbeacon_scan(event, session_state)

        assert "ActiveFine" not in message["message"]
        assert "Wanted" not in message["message"]


class TestTransformFCMaterials:
    """Tests for transform_fc_materials method."""

    def _make_fc_materials_data(self, **overrides):
        """Helper to build valid FCMaterials.json data."""
        data = {
            "timestamp": "2026-01-12T16:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3706117376,
            "CarrierName": "Test Carrier",
            "CarrierID": "ABC-12345",
            "Items": [
                {
                    "id": 1,
                    "Name": "hydrogenfuel",
                    "Price": 90,
                    "Stock": 5000,
                    "Demand": 0,
                },
                {
                    "id": 2,
                    "Name": "metallic_alloy",
                    "Price": 1200,
                    "Stock": 200,
                    "Demand": 150,
                },
            ],
        }
        data.update(overrides)
        return data

    def test_transform_basic(self, validator):
        fc_data = self._make_fc_materials_data()
        session_state = SessionState(horizons=True, odyssey=True)

        message = validator.transform_fc_materials(fc_data, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T16:00:00Z"
        assert payload["event"] == "FCMaterials"
        assert payload["MarketID"] == 3706117376
        assert payload["CarrierName"] == "Test Carrier"
        assert payload["CarrierID"] == "ABC-12345"
        assert len(payload["Items"]) == 2
        assert payload["Items"][0]["Name"] == "hydrogenfuel"
        assert payload["Items"][0]["Price"] == 90
        assert payload["Items"][0]["Stock"] == 5000
        assert payload["Items"][0]["Demand"] == 0
        assert payload["Items"][1]["Name"] == "metallic_alloy"
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator):
        fc_data = self._make_fc_materials_data()
        session_state = SessionState()
        message = validator.transform_fc_materials(fc_data, session_state)
        assert message["$schemaRef"] == EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF

    def test_strips_localised_from_items(self, validator):
        fc_data = self._make_fc_materials_data(
            Items=[
                {
                    "id": 1,
                    "Name": "hydrogenfuel",
                    "Name_Localised": "Hydrogen Fuel",
                    "Price": 90,
                    "Stock": 5000,
                    "Demand": 0,
                },
            ],
        )
        session_state = SessionState()
        message = validator.transform_fc_materials(fc_data, session_state)

        item = message["message"]["Items"][0]
        assert "Name_Localised" not in item
        assert item["Name"] == "hydrogenfuel"

    def test_empty_items_returns_none(self, validator):
        fc_data = self._make_fc_materials_data(Items=[])
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_no_items_key_returns_none(self, validator):
        fc_data = self._make_fc_materials_data()
        del fc_data["Items"]
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_missing_marketid_returns_none(self, validator):
        fc_data = self._make_fc_materials_data()
        del fc_data["MarketID"]
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_missing_carriername_returns_none(self, validator):
        fc_data = self._make_fc_materials_data()
        del fc_data["CarrierName"]
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_missing_carrierid_returns_none(self, validator):
        fc_data = self._make_fc_materials_data()
        del fc_data["CarrierID"]
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_empty_carriername_returns_none(self, validator):
        fc_data = self._make_fc_materials_data(CarrierName="")
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_empty_carrierid_returns_none(self, validator):
        fc_data = self._make_fc_materials_data(CarrierID="")
        session_state = SessionState()
        assert validator.transform_fc_materials(fc_data, session_state) is None

    def test_augments_horizons_odyssey(self, validator):
        fc_data = self._make_fc_materials_data()
        session_state = SessionState(horizons=False, odyssey=True)
        message = validator.transform_fc_materials(fc_data, session_state)

        assert message["message"]["horizons"] is False
        assert message["message"]["odyssey"] is True

    def test_preserves_item_fields(self, validator):
        """All required item fields (id, Name, Price, Stock, Demand) must be preserved."""
        fc_data = self._make_fc_materials_data(
            Items=[
                {
                    "id": 42,
                    "Name": "tritium",
                    "Price": 4500,
                    "Stock": 1000,
                    "Demand": 500,
                },
            ],
        )
        session_state = SessionState()
        message = validator.transform_fc_materials(fc_data, session_state)

        item = message["message"]["Items"][0]
        assert item["id"] == 42
        assert item["Name"] == "tritium"
        assert item["Price"] == 4500
        assert item["Stock"] == 1000
        assert item["Demand"] == 500

    def test_strips_disallowed_from_items(self, validator):
        """Disallowed fields (e.g. ActiveFine) should be stripped from Items."""
        fc_data = self._make_fc_materials_data(
            Items=[
                {
                    "id": 1,
                    "Name": "hydrogenfuel",
                    "Price": 90,
                    "Stock": 5000,
                    "Demand": 0,
                    "ActiveFine": True,
                    "Wanted": False,
                },
            ],
        )
        session_state = SessionState()
        message = validator.transform_fc_materials(fc_data, session_state)

        item = message["message"]["Items"][0]
        assert "ActiveFine" not in item
        assert "Wanted" not in item
        assert "id" in item
        assert "Name" in item


class TestValidateFSSAllBodiesFound:
    """Tests for FSSAllBodiesFound validation."""

    def test_valid_event_with_native_starpos(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        assert validator.validate(event) is True

    def test_valid_event_with_session_state_augmentation(self, validator):
        """StarPos augmented from session_state when not in the journal event."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        assert validator.validate(event, session_state) is True

    def test_rejected_without_session_state(self, validator):
        """No StarPos in journal, no session_state — validation fails."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        assert validator.validate(event) is False

    def test_rejected_system_address_mismatch(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Alpha Centauri",
                "SystemAddress": 99999,
                "Count": 7,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
        )
        assert validator.validate(event, session_state) is False

    def test_rejected_missing_system_name(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        assert validator.validate(event) is False

    def test_rejected_missing_system_address(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        assert validator.validate(event) is False

    def test_rejected_missing_count(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        assert validator.validate(event) is False


class TestTransformFSSAllBodiesFound:
    """Tests for transform_fss_all_bodies_found method."""

    def test_valid_transform(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert message is not None
        assert message["$schemaRef"] == EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T16:00:00Z"
        assert payload["event"] == "FSSAllBodiesFound"
        assert payload["SystemName"] == "Sol"
        assert payload["SystemAddress"] == 10477373803
        assert payload["StarPos"] == [0.0, 0.0, 0.0]
        assert payload["Count"] == 21
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_schema_ref(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(
            star_pos=[0.0, 0.0, 0.0],
            system_address=10477373803,
        )
        message = validator.transform_fss_all_bodies_found(event, session_state)
        assert message["$schemaRef"] == EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF

    def test_augments_starpos_from_session_state(self, validator):
        """StarPos is not in the journal event; must come from session_state."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(
            star_pos=[1.0, 2.0, 3.0],
            system_address=10477373803,
            star_system="Sol",
        )
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert message["message"]["StarPos"] == [1.0, 2.0, 3.0]

    def test_count_passthrough(self, validator):
        """Count passes through unchanged from journal to EDDN message."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Col 285 Sector ZZ-P b21-3",
                "SystemAddress": 987654321,
                "StarPos": [10.5, -20.3, 100.0],
                "Count": 47,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert message["message"]["Count"] == 47

    def test_augments_horizons_odyssey(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(horizons=False, odyssey=True)
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert message["message"]["horizons"] is False
        assert message["message"]["odyssey"] is True

    def test_strips_disallowed_fields(self, validator):
        """Disallowed fields like ActiveFine should be stripped."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
                "ActiveFine": True,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert "ActiveFine" not in message["message"]

    def test_strips_localised_keys(self, validator):
        """_Localised keys should be stripped from the payload."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T16:00:00Z",
                "event": "FSSAllBodiesFound",
                "SystemName": "Sol",
                "SystemName_Localised": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "Count": 21,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T16:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_all_bodies_found(event, session_state)

        assert "SystemName_Localised" not in message["message"]
        assert message["message"]["SystemName"] == "Sol"
