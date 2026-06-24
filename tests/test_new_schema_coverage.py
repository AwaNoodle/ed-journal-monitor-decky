"""Tests for the schemas added by the complete-eddn-schema-coverage change:
ScanBaryCentre, FSSBodySignals, DockingGranted, DockingDenied.
"""

import pytest

from src.modules.constants import (
    EDDN_DOCKINGDENIED_1_SCHEMA_REF,
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF,
    EDDN_FSSBODYSIGNALS_1_SCHEMA_REF,
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF,
)
from src.modules.parser import ParsedEvent, SessionState
from src.modules.validator import EDDNValidator


@pytest.fixture
def validator():
    return EDDNValidator()


@pytest.fixture
def session_state():
    return SessionState(
        star_pos=[1.0, 2.0, 3.0],
        system_address=10477373803,
        star_system="Sol",
        horizons=True,
        odyssey=True,
    )


def _event(event_type, raw):
    return ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])


# --------------------------------------------------------------------------- #
# Validation: required-field rejection
# --------------------------------------------------------------------------- #
class TestValidation:
    @pytest.mark.parametrize(
        ("event_type", "raw"),
        [
            ("ScanBaryCentre", {"timestamp": "t", "event": "ScanBaryCentre",
                                "StarSystem": "Sol", "SystemAddress": 10477373803, "BodyID": 2}),
            ("FSSBodySignals", {"timestamp": "t", "event": "FSSBodySignals", "BodyName": "Earth",
                                "BodyID": 2, "SystemAddress": 10477373803,
                                "Signals": [{"Type": "$SAA_SignalType_Geological;", "Count": 3}]}),
            ("DockingGranted", {"timestamp": "t", "event": "DockingGranted",
                                "MarketID": 128, "StationName": "Galileo", "StationType": "Coriolis"}),
            ("DockingDenied", {"timestamp": "t", "event": "DockingDenied", "Reason": "Distance",
                               "MarketID": 128, "StationName": "Galileo"}),
        ],
    )
    def test_valid_events(self, validator, session_state, event_type, raw):
        # ScanBaryCentre/FSSBodySignals need StarPos augmentation from session_state;
        # docking events are station-context and validate without it.
        assert validator.validate(_event(event_type, raw), session_state) is True

    @pytest.mark.parametrize(
        ("event_type", "raw"),
        [
            ("ScanBaryCentre", {"timestamp": "t", "BodyID": 2}),  # missing SystemAddress
            ("ScanBaryCentre", {"timestamp": "t", "SystemAddress": 1}),  # missing BodyID
            ("FSSBodySignals", {"timestamp": "t", "BodyID": 2, "SystemAddress": 1,
                                "Signals": []}),  # missing BodyName
            ("FSSBodySignals", {"timestamp": "t", "BodyName": "E", "BodyID": 2,
                                "SystemAddress": 1}),  # missing Signals
            ("DockingGranted", {"timestamp": "t", "StationName": "G"}),  # missing MarketID
            ("DockingDenied", {"timestamp": "t", "MarketID": 1, "StationName": "G"}),  # missing Reason
        ],
    )
    def test_missing_required_field_rejected(self, validator, session_state, event_type, raw):
        assert validator.validate(_event(event_type, raw), session_state) is False


# --------------------------------------------------------------------------- #
# ScanBaryCentre transform
# --------------------------------------------------------------------------- #
class TestScanBaryCentre:
    def test_transform(self, validator, session_state):
        raw = {
            "timestamp": "2026-01-12T12:00:00Z",
            "event": "ScanBaryCentre",
            "StarSystem": "Sol",
            "SystemAddress": 10477373803,
            "BodyID": 2,
            "SemiMajorAxis": 1.23,
        }
        msg = validator.transform_scan_bary_centre(_event("ScanBaryCentre", raw), session_state)
        assert msg["$schemaRef"] == EDDN_SCANBARYCENTRE_1_SCHEMA_REF
        m = msg["message"]
        assert m["StarPos"] == [1.0, 2.0, 3.0]  # augmented
        assert m["StarSystem"] == "Sol"
        assert m["BodyID"] == 2
        assert m["horizons"] is True and m["odyssey"] is True

    def test_rejected_when_starpos_unavailable(self, validator):
        raw = {"timestamp": "t", "event": "ScanBaryCentre",
               "StarSystem": "Sol", "SystemAddress": 1, "BodyID": 2}
        assert validator.transform_scan_bary_centre(_event("ScanBaryCentre", raw), SessionState()) is None

    def test_rejected_on_system_mismatch(self, validator, session_state):
        raw = {"timestamp": "t", "event": "ScanBaryCentre",
               "StarSystem": "Sol", "SystemAddress": 99999, "BodyID": 2}
        assert validator.transform_scan_bary_centre(_event("ScanBaryCentre", raw), session_state) is None

    def test_strips_localised_and_disallowed_fields(self, validator, session_state):
        raw = {
            "timestamp": "2026-01-12T12:00:00Z",
            "event": "ScanBaryCentre",
            "StarSystem": "Sol",
            "StarSystem_Localised": "Sol (localised)",
            "SystemAddress": 10477373803,
            "BodyID": 2,
            "Wanted": True,  # EDDN-disallowed field
        }
        msg = validator.transform_scan_bary_centre(_event("ScanBaryCentre", raw), session_state)
        m = msg["message"]
        assert "StarSystem_Localised" not in m
        assert "Wanted" not in m
        assert m["StarSystem"] == "Sol"


# --------------------------------------------------------------------------- #
# FSSBodySignals transform
# --------------------------------------------------------------------------- #
class TestFSSBodySignals:
    def test_transform_strips_nested_localised(self, validator, session_state):
        raw = {
            "timestamp": "2026-01-12T12:00:00Z",
            "event": "FSSBodySignals",
            "BodyName": "Earth",
            "BodyID": 2,
            "SystemAddress": 10477373803,
            "Signals": [
                {"Type": "$SAA_SignalType_Geological;",
                 "Type_Localised": "Geological", "Count": 3},
            ],
        }
        msg = validator.transform_fss_body_signals(_event("FSSBodySignals", raw), session_state)
        assert msg["$schemaRef"] == EDDN_FSSBODYSIGNALS_1_SCHEMA_REF
        m = msg["message"]
        assert m["StarSystem"] == "Sol" and m["StarPos"] == [1.0, 2.0, 3.0]
        signal = m["Signals"][0]
        assert signal["Type"] == "$SAA_SignalType_Geological;"
        assert "Type_Localised" not in signal  # nested _Localised stripped
        assert signal["Count"] == 3

    def test_rejected_without_session_state(self, validator):
        raw = {"timestamp": "t", "event": "FSSBodySignals", "BodyName": "E",
               "BodyID": 2, "SystemAddress": 1, "Signals": [{"Type": "x", "Count": 1}]}
        assert validator.transform_fss_body_signals(_event("FSSBodySignals", raw), SessionState()) is None


# --------------------------------------------------------------------------- #
# Docking transforms (no StarPos augmentation)
# --------------------------------------------------------------------------- #
class TestDocking:
    def test_docking_granted(self, validator, session_state):
        raw = {
            "timestamp": "2026-01-12T12:00:00Z",
            "event": "DockingGranted",
            "LandingPad": 7,
            "MarketID": 128666762,
            "StationName": "Galileo",
            "StationType": "Coriolis",
        }
        msg = validator.transform_docking_granted(_event("DockingGranted", raw), session_state)
        assert msg["$schemaRef"] == EDDN_DOCKINGGRANTED_1_SCHEMA_REF
        m = msg["message"]
        assert m["LandingPad"] == 7 and m["MarketID"] == 128666762
        assert m["StationName"] == "Galileo" and m["StationType"] == "Coriolis"
        assert m["horizons"] is True and m["odyssey"] is True
        assert "StarPos" not in m and "StarSystem" not in m  # station-context: no augmentation

    def test_docking_denied_strips_reason_localised(self, validator, session_state):
        raw = {
            "timestamp": "2026-01-12T12:00:00Z",
            "event": "DockingDenied",
            "Reason": "Distance",
            "Reason_Localised": "Too far away",
            "MarketID": 128666762,
            "StationName": "Galileo",
            "StationType": "Coriolis",
        }
        msg = validator.transform_docking_denied(_event("DockingDenied", raw), session_state)
        assert msg["$schemaRef"] == EDDN_DOCKINGDENIED_1_SCHEMA_REF
        m = msg["message"]
        assert m["Reason"] == "Distance"
        assert "Reason_Localised" not in m
        assert "StarPos" not in m and "StarSystem" not in m
