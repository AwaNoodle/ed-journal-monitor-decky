"""Tests for shared constants."""

from src.modules.constants import (
    AUXILIARY_FILES,
    AUXILIARY_SCHEMA_EVENTS,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
    REPORTABLE_EVENTS,
)


class TestReportableEvents:
    def test_includes_phase_1_and_phase_2_events(self):
        expected = {
            "FSDJump",
            "Scan",
            "Location",
            "Docked",
            "FSSDiscoveryScan",
            "Market",
            "Outfitting",
            "Shipyard",
            "NavRoute",
            "ApproachBody",
            "LeaveBody",
            "ApproachSettlement",
            "CarrierJump",
            "FSSSignalDiscovered",
            "SAAScanComplete",
        }
        assert expected.issubset(REPORTABLE_EVENTS)


class TestAuxiliaryFiles:
    def test_auxiliary_file_mapping(self):
        assert AUXILIARY_FILES == {
            "Market": {"filename": "Market.json", "schema": "commodity"},
            "Outfitting": {"filename": "Outfitting.json", "schema": "outfitting"},
            "Shipyard": {"filename": "Shipyard.json", "schema": "shipyard"},
            "NavRoute": {"filename": "NavRoute.json", "schema": "journal"},
        }

    def test_auxiliary_schema_events_derived(self):
        """AUXILIARY_SCHEMA_EVENTS is derived from AUXILIARY_FILES (non-journal schemas)."""
        assert {"Market", "Outfitting", "Shipyard"} == AUXILIARY_SCHEMA_EVENTS
        assert "NavRoute" not in AUXILIARY_SCHEMA_EVENTS


class TestSchemaReferences:
    def test_schema_ref_constants(self):
        assert EDDN_JOURNAL_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/journal/1"
        assert EDDN_COMMODITY_3_SCHEMA_REF == "https://eddn.edcd.io/schemas/commodity/3"
        assert EDDN_OUTFITTING_2_SCHEMA_REF == "https://eddn.edcd.io/schemas/outfitting/2"
        assert EDDN_SHIPYARD_2_SCHEMA_REF == "https://eddn.edcd.io/schemas/shipyard/2"
