"""
Tests for the EDDNValidator module.
"""

import pytest

from src.modules.constants import (
    EDDN_COMMODITY_3_SCHEMA_REF,
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

    @pytest.mark.parametrize(
        ("event_type", "required_field", "complete_raw"),
        [
            ("ApproachBody", "SystemAddress", {
                "timestamp": "2026-01-12T14:01:00Z",
                "event": "ApproachBody",
                "StarSystem": "Sol",
                "BodyName": "Earth",
            }),
            ("LeaveBody", "BodyName", {
                "timestamp": "2026-01-12T14:01:10Z",
                "event": "LeaveBody",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
            }),
            ("ApproachSettlement", "StationName", {
                "timestamp": "2026-01-12T14:01:20Z",
                "event": "ApproachSettlement",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
            }),
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
            ("SAAScanComplete", "SystemAddress", {
                "timestamp": "2026-01-12T14:04:00Z",
                "event": "SAAScanComplete",
                "BodyName": "Earth",
            }),
        ],
    )
    def test_new_events_missing_required_field(self, validator, event_type, required_field, complete_raw):
        """Each new event must fail validation when a required field is missing."""
        event = ParsedEvent(raw=complete_raw, event_type=event_type, timestamp=complete_raw["timestamp"])
        assert validator.validate(event) is False


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
                "ApproachBody",
                {
                    "timestamp": "2026-01-12T14:01:00Z",
                    "event": "ApproachBody",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "BodyName": "Earth",
                },
            ),
            (
                "LeaveBody",
                {
                    "timestamp": "2026-01-12T14:01:10Z",
                    "event": "LeaveBody",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "BodyName": "Earth",
                },
            ),
            (
                "ApproachSettlement",
                {
                    "timestamp": "2026-01-12T14:01:20Z",
                    "event": "ApproachSettlement",
                    "StarSystem": "Sol",
                    "SystemAddress": 10477373803,
                    "StationName": "Galileo",
                },
            ),
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
                "FSSSignalDiscovered",
                {
                    "timestamp": "2026-01-12T14:03:00Z",
                    "event": "FSSSignalDiscovered",
                    "SystemAddress": 10477373803,
                    "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;",
                },
            ),
            (
                "SAAScanComplete",
                {
                    "timestamp": "2026-01-12T14:04:00Z",
                    "event": "SAAScanComplete",
                    "BodyName": "Earth",
                    "SystemAddress": 10477373803,
                },
            ),
        ],
    )
    def test_valid_new_journal_events(self, validator, event_type, raw):
        event = ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])
        assert validator.validate(event) is True


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
        """_Localised keys inside arrays (e.g. Factions[], StationEconomies[]) are stripped."""
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

        # Factions array
        for faction in message["message"]["Factions"]:
            assert "Government_Localised" not in faction
            assert "Happiness_Localised" not in faction
            assert "Government" in faction
        # StationEconomies array
        for economy in message["message"]["StationEconomies"]:
            assert "Name_Localised" not in economy
            assert "Name" in economy

    def test_strips_disallowed_in_nested_structures(self, validator):
        """Disallowed fields are stripped at all nesting levels."""
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

    def test_transform_new_journal_event(self, validator):
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

        # First fixture item has stock/demand bracket both 0, should be filtered out
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
            "name": "drones",
            "meanPrice": 99,
            "buyPrice": 101,
            "stock": 9999,
            "stockBracket": 3,
            "sellPrice": 95,
            "demand": 0,
            "demandBracket": 0,
        }

    def test_transform_commodity_empty_returns_none(self, validator):
        """All items with stockBracket=0 and demandBracket=0 → None."""
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
        """Items key present but empty → None."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_missing_starsystem_returns_none(self, validator):
        """Missing StarSystem → None (EDDN requires non-empty systemName)."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_missing_marketid_returns_none(self, validator):
        """Missing MarketID → None (EDDN requires non-zero marketId)."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None

    def test_transform_commodity_empty_stationname_returns_none(self, validator):
        """Empty StationName → None (EDDN requires non-empty stationName)."""
        market_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "",
            "MarketID": 123,
            "Items": [{"Name": "test", "StockBracket": 1, "DemandBracket": 0}],
        }
        assert validator.transform_commodity(market_data, SessionState()) is None


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
        # EDDN outfitting/2 schema: modules is an array of strings
        assert payload["modules"] == [
            "int_cargo_rack_size6_class1",
            "int_shieldgenerator_size8_class5_fast",
        ]
        assert payload["horizons"] is False
        assert payload["odyssey"] is True

    def test_transform_outfitting_empty_returns_none(self, validator):
        """No modules → None."""
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "Modules": [],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None

    def test_transform_outfitting_missing_starsystem_returns_none(self, validator):
        """Missing StarSystem → None."""
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "Modules": [{"Name": "test_module"}],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None

    def test_transform_outfitting_zero_marketid_returns_none(self, validator):
        """MarketID=0 → None."""
        outfitting_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 0,
            "Modules": [{"Name": "test_module"}],
        }
        assert validator.transform_outfitting(outfitting_data, SessionState()) is None


class TestTransformShipyard:
    def test_transform_shipyard_data(self, validator, load_fixture):
        shipyard_data = load_fixture("Shipyard.json")

        message = validator.transform_shipyard(shipyard_data, SessionState())

        assert message is not None
        assert message["$schemaRef"] == EDDN_SHIPYARD_2_SCHEMA_REF
        payload = message["message"]
        assert payload["timestamp"] == "2026-01-12T13:05:00Z"
        assert payload["systemName"] == "Shinrarta Dezhra"
        assert payload["stationName"] == "Jameson Memorial"
        assert payload["marketId"] == 128666762
        # EDDN shipyard/2 schema: ships is an array of strings
        assert payload["ships"] == ["sidey", "eagle"]
        assert payload["horizons"] is True
        assert payload["odyssey"] is True

    def test_transform_shipyard_empty_returns_none(self, validator):
        """No ships → None."""
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StarSystem": "Sol",
            "StationName": "Test",
            "MarketID": 123,
            "PriceList": [],
        }
        assert validator.transform_shipyard(shipyard_data, SessionState()) is None

    def test_transform_shipyard_missing_starsystem_returns_none(self, validator):
        """Missing StarSystem → None."""
        shipyard_data = {
            "timestamp": "2026-01-12T13:05:00Z",
            "StationName": "Test",
            "MarketID": 123,
            "PriceList": [{"ShipType": "sidewinder"}],
        }
        assert validator.transform_shipyard(shipyard_data, SessionState()) is None

    def test_transform_shipyard_zero_marketid_returns_none(self, validator):
        """MarketID=0 → None."""
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
