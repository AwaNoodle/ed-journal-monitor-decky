"""Unknown-future-field coverage for every strict (allow-list-projected) EDDN schema.

Simulates FDev adding a brand-new field to a covered event: injects an invented key
(``FDevFutureField``) at message level, and inside each strict nested container, then
asserts the transform's output never carries it while the fields we actually send
survive untouched. This is the regression test for the failure mode issue #27 fixes --
a blacklist would let an unrecognised field straight through; the allow-list projection
must drop it instead.
"""

from __future__ import annotations

import pytest

from src.modules.constants import EDDN_COMMODITY_3_SCHEMA_REF
from src.modules.eddn_allowed_fields import ALLOW_LISTS
from src.modules.parser import ParsedEvent, SessionState
from src.modules.validator import EDDNValidator, _project_allowed

FUTURE_FIELD = "FDevFutureField"


@pytest.fixture
def validator():
    return EDDNValidator()


# Each case: (id, build(validator, extra) -> message_payload dict).
# `extra` is merged into the raw/aux top-level payload before the transform runs, so it
# lands exactly where a real unrecognised journal field would.

def _approach_settlement(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:05:00Z",
            "event": "ApproachSettlement",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "StarPos": [0.0, 0.0, 0.0],
            "StationName": "Galileo",
            "BodyID": 1,
            "BodyName": "Earth",
            "MarketID": 123456,
            "Latitude": 12.5,
            "Longitude": -45.25,
            **extra,
        },
        event_type="ApproachSettlement",
        timestamp="2026-01-12T12:05:00Z",
    )
    return validator.transform_approach_settlement(event, SessionState(horizons=True, odyssey=True))["message"]


def _codex_entry(validator, extra):
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
            "System": "Sol",
            "StarPos": [0.0, 0.0, 0.0],
            **extra,
        },
        event_type="CodexEntry",
        timestamp="2026-01-12T15:00:00Z",
    )
    return validator.transform_codex_entry(event, SessionState(horizons=True, odyssey=True))["message"]


def _commodity(validator, extra):
    market_data = {
        "timestamp": "2026-01-12T13:05:00Z",
        "StarSystem": "Sol",
        "StationName": "Test Station",
        "MarketID": 123,
        "Items": [{"Name": "gold", "StockBracket": 1, "DemandBracket": 0, "MeanPrice": 100,
                   "BuyPrice": 100, "Stock": 10, "SellPrice": 90, "Demand": 0}],
        **extra,
    }
    return validator.transform_commodity(market_data, SessionState(horizons=True, odyssey=False))["message"]


def _outfitting(validator, extra):
    outfitting_data = {
        "timestamp": "2026-01-12T13:05:00Z",
        "StarSystem": "Sol",
        "StationName": "Test Station",
        "MarketID": 123,
        "Items": [{"Name": "hpt_pulselaser_fixed_small"}],
        **extra,
    }
    return validator.transform_outfitting(outfitting_data, SessionState(horizons=True, odyssey=False))["message"]


def _shipyard(validator, extra):
    shipyard_data = {
        "timestamp": "2026-01-12T13:05:00Z",
        "StarSystem": "Sol",
        "StationName": "Test Station",
        "MarketID": 123,
        "PriceList": [{"ShipType": "sidewinder"}],
        **extra,
    }
    return validator.transform_shipyard(shipyard_data, SessionState(horizons=True, odyssey=False))["message"]


def _navroute(validator, extra):
    navroute_data = {
        "timestamp": "2026-01-12T14:00:00Z",
        "event": "NavRoute",
        "Route": [{"StarSystem": "Sol", "SystemAddress": 10477373803,
                    "StarPos": [0.0, 0.0, 0.0], "StarClass": "G"}],
        **extra,
    }
    return validator.transform_navroute(navroute_data, SessionState(horizons=True, odyssey=False))["message"]


def _fss_discovery_scan(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:15:00Z",
            "event": "FSSDiscoveryScan",
            "SystemAddress": 10477373803,
            "BodyCount": 21,
            "NonBodyCount": 42,
            **extra,
        },
        event_type="FSSDiscoveryScan",
        timestamp="2026-01-12T12:15:00Z",
    )
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_fss_discovery_scan(event, session_state)["message"]


def _navbeacon_scan(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:20:00Z",
            "event": "NavBeaconScan",
            "SystemAddress": 10477373803,
            "NumBodies": 21,
            **extra,
        },
        event_type="NavBeaconScan",
        timestamp="2026-01-12T12:20:00Z",
    )
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_navbeacon_scan(event, session_state)["message"]


def _fss_all_bodies_found(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:25:00Z",
            "event": "FSSAllBodiesFound",
            "SystemAddress": 10477373803,
            "Count": 7,
            **extra,
        },
        event_type="FSSAllBodiesFound",
        timestamp="2026-01-12T12:25:00Z",
    )
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_fss_all_bodies_found(event, session_state)["message"]


def _scan_bary_centre(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:30:00Z",
            "event": "ScanBaryCentre",
            "SystemAddress": 10477373803,
            "BodyID": 3,
            "SemiMajorAxis": 123456.0,
            **extra,
        },
        event_type="ScanBaryCentre",
        timestamp="2026-01-12T12:30:00Z",
    )
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_scan_bary_centre(event, session_state)["message"]


def _fss_body_signals(validator, extra):
    raw = {
        "timestamp": "2026-01-12T12:35:00Z",
        "event": "FSSBodySignals",
        "SystemAddress": 10477373803,
        "BodyID": 3,
        "BodyName": "Sol 3",
        "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 5}],
    }
    raw.update({k: v for k, v in extra.items() if k != "Signals"})
    event = ParsedEvent(raw=raw, event_type="FSSBodySignals", timestamp="2026-01-12T12:35:00Z")
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_fss_body_signals(event, session_state)["message"]


def _docking_granted(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:40:00Z",
            "event": "DockingGranted",
            "MarketID": 123456,
            "StationName": "Jameson Memorial",
            "LandingPad": 7,
            **extra,
        },
        event_type="DockingGranted",
        timestamp="2026-01-12T12:40:00Z",
    )
    return validator.transform_docking_granted(event, SessionState(horizons=True, odyssey=True))["message"]


def _docking_denied(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:45:00Z",
            "event": "DockingDenied",
            "MarketID": 123456,
            "StationName": "Jameson Memorial",
            "Reason": "Distance",
            **extra,
        },
        event_type="DockingDenied",
        timestamp="2026-01-12T12:45:00Z",
    )
    return validator.transform_docking_denied(event, SessionState(horizons=True, odyssey=True))["message"]


def _fss_signal_discovered(validator, extra):
    batch = {
        "signals": [{"timestamp": "2026-01-12T14:03:00Z", "SignalName": "$Test;"}],
        "first_timestamp": "2026-01-12T14:03:00Z",
        "system_address": 10477373803,
        "star_system": "Sol",
        "star_pos": [0.0, 0.0, 0.0],
    }
    batch.update({k: v for k, v in extra.items() if k != "signals"})
    return validator.transform_fss_signal_discovered(batch, SessionState(horizons=True, odyssey=True))["message"]


def _fc_materials(validator, extra):
    fc_data = {
        "timestamp": "2026-01-12T16:00:00Z",
        "event": "FCMaterials",
        "MarketID": 3706117376,
        "CarrierName": "Test Carrier",
        "CarrierID": "ABC-12345",
        "Items": [{"id": 1, "Name": "hydrogenfuel", "Price": 90, "Stock": 5000, "Demand": 0}],
        **extra,
    }
    return validator.transform_fc_materials(fc_data, SessionState(horizons=True, odyssey=True))["message"]


# Message-level cases: every strict schema this plugin builds via _project_allowed.
MESSAGE_LEVEL_CASES = [
    ("approachsettlement", _approach_settlement, "BodyName"),
    ("codexentry", _codex_entry, "Name"),
    ("commodity", _commodity, "stationName"),
    ("outfitting", _outfitting, "stationName"),
    ("shipyard", _shipyard, "stationName"),
    ("navroute", _navroute, "Route"),
    ("fssdiscoveryscan", _fss_discovery_scan, "BodyCount"),
    ("navbeaconscan", _navbeacon_scan, "NumBodies"),
    ("fssallbodiesfound", _fss_all_bodies_found, "Count"),
    ("scanbarycentre", _scan_bary_centre, "BodyID"),
    ("fssbodysignals", _fss_body_signals, "BodyName"),
    ("dockinggranted", _docking_granted, "LandingPad"),
    ("dockingdenied", _docking_denied, "Reason"),
    ("fsssignaldiscovered", _fss_signal_discovered, "StarSystem"),
    ("fcmaterials", _fc_materials, "CarrierName"),
]


@pytest.mark.parametrize("name,build,known_field", MESSAGE_LEVEL_CASES, ids=[c[0] for c in MESSAGE_LEVEL_CASES])
def test_message_level_unknown_field_dropped(validator, name, build, known_field):
    message = build(validator, {FUTURE_FIELD: "unexpected"})
    assert FUTURE_FIELD not in message, f"{name}: message-level allow-list let an unrecognised field through"
    assert known_field in message, f"{name}: projection dropped a field it should have kept"


# Nested-container cases: (id, build(extra_top_level), container_key, item_index).
def _approach_settlement_with_faction(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:05:00Z",
            "event": "ApproachSettlement",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "StarPos": [0.0, 0.0, 0.0],
            "StationName": "Galileo",
            "BodyID": 1,
            "BodyName": "Earth",
            "MarketID": 123456,
            "Latitude": 12.5,
            "Longitude": -45.25,
            "StationFaction": {"Name": "Test Faction", "FactionState": "Boom", **extra},
        },
        event_type="ApproachSettlement",
        timestamp="2026-01-12T12:05:00Z",
    )
    message = validator.transform_approach_settlement(event, SessionState(horizons=True, odyssey=True))["message"]
    return message["StationFaction"]


def _commodity_with_extra_commodity_field(validator, extra):
    market_data = {
        "timestamp": "2026-01-12T13:05:00Z",
        "StarSystem": "Sol",
        "StationName": "Test Station",
        "MarketID": 123,
        "Items": [{"Name": "gold", "StockBracket": 1, "DemandBracket": 0, "MeanPrice": 100,
                   "BuyPrice": 100, "Stock": 10, "SellPrice": 90, "Demand": 0}],
    }
    message = validator.transform_commodity(market_data, SessionState(horizons=True, odyssey=False))["message"]
    # commodities[] is built explicitly (not from raw passthrough); simulate a future
    # schema addition leaking through by injecting the extra key straight onto the
    # already-built payload and re-projecting, matching how _project_allowed is always
    # the final step regardless of how the dict was assembled.
    message["commodities"][0].update(extra)
    allow_list = ALLOW_LISTS[EDDN_COMMODITY_3_SCHEMA_REF]
    return _project_allowed(message, allow_list)["commodities"][0]


def _navroute_with_extra_route_field(validator, extra):
    navroute_data = {
        "timestamp": "2026-01-12T14:00:00Z",
        "event": "NavRoute",
        "Route": [{"StarSystem": "Sol", "SystemAddress": 10477373803,
                    "StarPos": [0.0, 0.0, 0.0], "StarClass": "G", **extra}],
    }
    message = validator.transform_navroute(navroute_data, SessionState(horizons=True, odyssey=False))
    return message["message"]["Route"][0]


def _fss_body_signals_with_extra_signal_field(validator, extra):
    event = ParsedEvent(
        raw={
            "timestamp": "2026-01-12T12:35:00Z",
            "event": "FSSBodySignals",
            "SystemAddress": 10477373803,
            "BodyID": 3,
            "BodyName": "Sol 3",
            "Signals": [{"Type": "$SAA_SignalType_Biological;", "Count": 5, **extra}],
        },
        event_type="FSSBodySignals",
        timestamp="2026-01-12T12:35:00Z",
    )
    session_state = SessionState(horizons=True, odyssey=True, star_pos=[0.0, 0.0, 0.0],
                                  system_address=10477373803, star_system="Sol")
    return validator.transform_fss_body_signals(event, session_state)["message"]["Signals"][0]


def _fss_signal_discovered_with_extra_signal_field(validator, extra):
    batch = {
        "signals": [{"timestamp": "2026-01-12T14:03:00Z", "SignalName": "$Test;", **extra}],
        "first_timestamp": "2026-01-12T14:03:00Z",
        "system_address": 10477373803,
        "star_system": "Sol",
        "star_pos": [0.0, 0.0, 0.0],
    }
    message = validator.transform_fss_signal_discovered(batch, SessionState(horizons=True, odyssey=True))["message"]
    return message["signals"][0]


NESTED_CASES = [
    ("approachsettlement.StationFaction", _approach_settlement_with_faction, "Name"),
    ("commodity.commodities", _commodity_with_extra_commodity_field, "name"),
    ("navroute.Route", _navroute_with_extra_route_field, "StarSystem"),
    ("fssbodysignals.Signals", _fss_body_signals_with_extra_signal_field, "Type"),
    ("fsssignaldiscovered.signals", _fss_signal_discovered_with_extra_signal_field, "SignalName"),
]


@pytest.mark.parametrize("name,build,known_field", NESTED_CASES, ids=[c[0] for c in NESTED_CASES])
def test_nested_container_unknown_field_dropped(validator, name, build, known_field):
    item = build(validator, {FUTURE_FIELD: "unexpected"})
    assert FUTURE_FIELD not in item, f"{name}: nested allow-list let an unrecognised field through"
    assert known_field in item, f"{name}: nested projection dropped a field it should have kept"
