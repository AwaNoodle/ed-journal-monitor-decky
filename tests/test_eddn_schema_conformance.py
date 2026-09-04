"""Validates each transform's output against the real upstream EDDN schema.

Builds a realistic raw journal/auxiliary event, runs it through the matching
`EDDNValidator` transform, attaches a header the way `submitter.py` does, and
validates the resulting `{$schemaRef, header, message}` document against the
pinned schema fixture (`tests/fixtures/eddn-schemas/`) with `jsonschema`
(dev-only dependency; the shipped backend stays stdlib-only).

This is the acceptance evidence for issue #27: before the `transform_codex_entry`
fix, every CodexEntry message failed here because `codexentry/1`'s `message` has
no `StarSystem` property (`additionalProperties: false`) -- see
`test_codex_entry_star_system_defect_would_fail_conformance` below, which pins
that regression by re-deriving the pre-fix payload shape directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from src.modules.constants import (
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
    EDDN_CODEXENTRY_1_SCHEMA_REF,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_DOCKINGDENIED_1_SCHEMA_REF,
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF,
    EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF,
    EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF,
    EDDN_FSSBODYSIGNALS_1_SCHEMA_REF,
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
)
from src.modules.parser import ParsedEvent, SessionState
from src.modules.validator import EDDNValidator

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMAS_DIR = FIXTURES_DIR / "eddn-schemas"

SCHEMA_FILES = {
    EDDN_JOURNAL_1_SCHEMA_REF: "journal-v1.0.json",
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF: "approachsettlement-v1.0.json",
    EDDN_CODEXENTRY_1_SCHEMA_REF: "codexentry-v1.0.json",
    EDDN_COMMODITY_3_SCHEMA_REF: "commodity-v3.0.json",
    EDDN_DOCKINGDENIED_1_SCHEMA_REF: "dockingdenied-v1.0.json",
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF: "dockinggranted-v1.0.json",
    EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF: "fcmaterials_journal-v1.0.json",
    EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF: "fssallbodiesfound-v1.0.json",
    EDDN_FSSBODYSIGNALS_1_SCHEMA_REF: "fssbodysignals-v1.0.json",
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF: "fssdiscoveryscan-v1.0.json",
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF: "fsssignaldiscovered-v1.0.json",
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF: "navbeaconscan-v1.0.json",
    EDDN_NAVROUTE_1_SCHEMA_REF: "navroute-v1.0.json",
    EDDN_OUTFITTING_2_SCHEMA_REF: "outfitting-v2.0.json",
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF: "scanbarycentre-v1.0.json",
    EDDN_SHIPYARD_2_SCHEMA_REF: "shipyard-v2.0.json",
}


def _load_schema(schema_ref: str) -> dict:
    return json.loads((SCHEMAS_DIR / SCHEMA_FILES[schema_ref]).read_text(encoding="utf-8"))


def _with_header(message: dict) -> dict:
    """Attach a header the way `submitter.py`'s `submit()` does."""
    document = dict(message)
    document["header"] = {
        "uploaderID": "test-uploader",
        "softwareName": SOFTWARE_NAME,
        "softwareVersion": SOFTWARE_VERSION,
        "gameversion": "4.1.0.404",
        "gamebuild": "r280105/r0 ",
    }
    return document


def _assert_conforms(message: dict, schema_ref: str) -> None:
    document = _with_header(message)
    schema = _load_schema(schema_ref)
    jsonschema.Draft4Validator(schema).validate(document)


@pytest.fixture
def validator():
    return EDDNValidator()


@pytest.fixture
def load_fixture():
    def _load(filename):
        return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))

    return _load


class TestJournalConformance:
    def test_fsd_jump_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:00:00Z",
                "event": "FSDJump",
                "StarSystem": "Sol",
                "SystemAddress": 10477373803,
                "StarPos": [0.0, 0.0, 0.0],
                "JumpDist": 15.123,
            },
            event_type="FSDJump",
            timestamp="2026-01-12T12:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform(event, session_state)
        _assert_conforms(message, EDDN_JOURNAL_1_SCHEMA_REF)


class TestApproachSettlementConformance:
    def test_conforms(self, validator):
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
            },
            event_type="ApproachSettlement",
            timestamp="2026-01-12T12:05:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_approach_settlement(event, session_state)
        _assert_conforms(message, EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF)


class TestCodexEntryConformance:
    def test_conforms(self, validator):
        """The acceptance evidence for issue #27: this failed before the fix
        because the old transform emitted StarSystem, a key codexentry/1's
        additionalProperties:false message does not allow."""
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
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_codex_entry(event, session_state)
        _assert_conforms(message, EDDN_CODEXENTRY_1_SCHEMA_REF)

    def test_conforms_without_body_fields(self, validator):
        """Issue #38: a CodexEntry event logged away from a body carries neither
        BodyID nor BodyName -- codexentry-v1.0.json requires neither, so the
        resulting message must still validate against the real schema."""
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T15:00:00Z",
                "event": "CodexEntry",
                "SystemAddress": 10477373803,
                "EntryID": 123,
            },
            event_type="CodexEntry",
            timestamp="2026-01-12T15:00:00Z",
        )
        session_state = SessionState(
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_codex_entry(event, session_state)
        assert "BodyID" not in message["message"]
        assert "BodyName" not in message["message"]
        _assert_conforms(message, EDDN_CODEXENTRY_1_SCHEMA_REF)

    def test_pre_fix_star_system_payload_fails_conformance(self, validator):
        """Pins the issue #27 defect: a message built the old way (StarSystem
        instead of System) must fail schema validation. Guards against the fix
        being reverted without this test catching it."""
        pre_fix_message = {
            "$schemaRef": EDDN_CODEXENTRY_1_SCHEMA_REF,
            "message": {
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
        }
        with pytest.raises(jsonschema.ValidationError):
            _assert_conforms(pre_fix_message, EDDN_CODEXENTRY_1_SCHEMA_REF)


class TestCommodityConformance:
    def test_conforms(self, validator, load_fixture):
        market_data = load_fixture("Market.json")
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_commodity(market_data, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_COMMODITY_3_SCHEMA_REF)


class TestOutfittingConformance:
    def test_conforms(self, validator, load_fixture):
        outfitting_data = load_fixture("Outfitting.json")
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_outfitting(outfitting_data, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_OUTFITTING_2_SCHEMA_REF)


class TestShipyardConformance:
    def test_conforms(self, validator, load_fixture):
        shipyard_data = load_fixture("Shipyard.json")
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_shipyard(shipyard_data, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_SHIPYARD_2_SCHEMA_REF)


class TestNavRouteConformance:
    def test_conforms(self, validator, load_fixture):
        navroute_data = load_fixture("NavRoute.json")
        session_state = SessionState(horizons=True, odyssey=False)
        message = validator.transform_navroute(navroute_data, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_NAVROUTE_1_SCHEMA_REF)


class TestFssSignalDiscoveredConformance:
    def test_conforms(self, validator):
        batch = {
            "signals": [
                {
                    "timestamp": "2026-01-12T14:03:00Z",
                    "SignalName": "$MULTIPLAYER_SCENARIO42_TITLE;",
                    "SignalType": "USS",
                    "IsStation": False,
                    "USSType": "$USS_Type_Debris;",
                    "SpawningState": "$FactionState_Boom;",
                    "SpawningFaction": "Test Faction",
                    "SpawningPower": "Aisling Duval",
                    "OpposingPower": "Zachary Hudson",
                    "ThreatLevel": 2,
                },
            ],
            "first_timestamp": "2026-01-12T14:03:00Z",
            "system_address": 10477373803,
            "star_system": "Sol",
            "star_pos": [0.0, 0.0, 0.0],
        }
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fss_signal_discovered(batch, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF)


class TestFssDiscoveryScanConformance:
    def test_conforms(self, validator):
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
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_fss_discovery_scan(event, session_state)
        _assert_conforms(message, EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF)


class TestNavBeaconScanConformance:
    def test_conforms(self, validator):
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
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_navbeacon_scan(event, session_state)
        _assert_conforms(message, EDDN_NAVBEACONSCAN_1_SCHEMA_REF)


class TestFssAllBodiesFoundConformance:
    def test_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:25:00Z",
                "event": "FSSAllBodiesFound",
                "SystemAddress": 10477373803,
                "Count": 7,
            },
            event_type="FSSAllBodiesFound",
            timestamp="2026-01-12T12:25:00Z",
        )
        session_state = SessionState(
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_fss_all_bodies_found(event, session_state)
        _assert_conforms(message, EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF)


class TestScanBaryCentreConformance:
    def test_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:30:00Z",
                "event": "ScanBaryCentre",
                "SystemAddress": 10477373803,
                "BodyID": 3,
                "SemiMajorAxis": 123456.0,
                "Eccentricity": 0.1,
                "OrbitalInclination": 1.5,
                "Periapsis": 45.0,
                "OrbitalPeriod": 987654.0,
                "AscendingNode": 12.3,
                "MeanAnomaly": 67.8,
            },
            event_type="ScanBaryCentre",
            timestamp="2026-01-12T12:30:00Z",
        )
        session_state = SessionState(
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_scan_bary_centre(event, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_SCANBARYCENTRE_1_SCHEMA_REF)


class TestFssBodySignalsConformance:
    def test_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:35:00Z",
                "event": "FSSBodySignals",
                "SystemAddress": 10477373803,
                "BodyID": 3,
                "BodyName": "Sol 3",
                "Signals": [
                    {"Type": "$SAA_SignalType_Biological;", "Count": 5},
                ],
            },
            event_type="FSSBodySignals",
            timestamp="2026-01-12T12:35:00Z",
        )
        session_state = SessionState(
            horizons=True, odyssey=True,
            star_pos=[0.0, 0.0, 0.0], system_address=10477373803, star_system="Sol",
        )
        message = validator.transform_fss_body_signals(event, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_FSSBODYSIGNALS_1_SCHEMA_REF)


class TestDockingGrantedConformance:
    def test_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:40:00Z",
                "event": "DockingGranted",
                "MarketID": 123456,
                "StationName": "Jameson Memorial",
                "StationType": "Orbis",
                "LandingPad": 7,
            },
            event_type="DockingGranted",
            timestamp="2026-01-12T12:40:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_docking_granted(event, session_state)
        _assert_conforms(message, EDDN_DOCKINGGRANTED_1_SCHEMA_REF)


class TestDockingDeniedConformance:
    def test_conforms(self, validator):
        event = ParsedEvent(
            raw={
                "timestamp": "2026-01-12T12:45:00Z",
                "event": "DockingDenied",
                "MarketID": 123456,
                "StationName": "Jameson Memorial",
                "StationType": "Orbis",
                "Reason": "Distance",
            },
            event_type="DockingDenied",
            timestamp="2026-01-12T12:45:00Z",
        )
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_docking_denied(event, session_state)
        _assert_conforms(message, EDDN_DOCKINGDENIED_1_SCHEMA_REF)


class TestFcMaterialsConformance:
    def test_conforms(self, validator):
        fc_data = {
            "timestamp": "2026-01-12T16:00:00Z",
            "event": "FCMaterials",
            "MarketID": 3706117376,
            "CarrierName": "Test Carrier",
            "CarrierID": "ABC-12345",
            "Items": [
                {"id": 1, "Name": "hydrogenfuel", "Price": 90, "Stock": 5000, "Demand": 0},
                {"id": 2, "Name": "metallic_alloy", "Price": 1200, "Stock": 200, "Demand": 150},
            ],
        }
        session_state = SessionState(horizons=True, odyssey=True)
        message = validator.transform_fc_materials(fc_data, session_state)
        assert message is not None
        _assert_conforms(message, EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF)
