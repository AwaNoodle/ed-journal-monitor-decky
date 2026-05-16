"""Tests for shared constants — updated for EDDN schema fix."""

from src.modules.constants import (
    AUXILIARY_FILES,
    AUXILIARY_SCHEMA_EVENTS,
    DEDICATED_SCHEMA_EVENTS,
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
    EDDN_CODEXENTRY_1_SCHEMA_REF,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_DISALLOWED_FIELDS,
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
    FSS_SIGNAL_DISALLOWED_FIELDS,
    JOURNAL_1_ONLY_DISALLOWED,
    REPORTABLE_EVENTS,
)


class TestReportableEvents:
    def test_includes_core_journal1_events(self):
        expected = {
            "FSDJump",
            "Scan",
            "Location",
            "Docked",
            "CarrierJump",
            "SAASignalsFound",
        }
        assert expected.issubset(REPORTABLE_EVENTS)

    def test_includes_auxiliary_trigger_events(self):
        expected = {
            "Market",
            "Outfitting",
            "Shipyard",
            "NavRoute",
        }
        assert expected.issubset(REPORTABLE_EVENTS)

    def test_includes_dedicated_schema_events(self):
        expected = {
            "FSSDiscoveryScan",
            "ApproachSettlement",
            "FSSSignalDiscovered",
            "CodexEntry",
        }
        assert expected.issubset(REPORTABLE_EVENTS)

    def test_excludes_approach_body(self):
        assert "ApproachBody" not in REPORTABLE_EVENTS

    def test_excludes_leave_body(self):
        assert "LeaveBody" not in REPORTABLE_EVENTS

    def test_excludes_saa_scan_complete(self):
        assert "SAAScanComplete" not in REPORTABLE_EVENTS

    def test_includes_saa_signals_found(self):
        assert "SAASignalsFound" in REPORTABLE_EVENTS

    def test_includes_codex_entry(self):
        assert "CodexEntry" in REPORTABLE_EVENTS


class TestAuxiliaryFiles:
    def test_auxiliary_file_mapping(self):
        assert AUXILIARY_FILES == {
            "Market": {"filename": "Market.json", "schema": "commodity"},
            "Outfitting": {"filename": "Outfitting.json", "schema": "outfitting"},
            "Shipyard": {"filename": "Shipyard.json", "schema": "shipyard"},
            "NavRoute": {"filename": "NavRoute.json", "schema": "navroute"},
    }

    def test_auxiliary_schema_events_derived(self):
        """AUXILIARY_SCHEMA_EVENTS is derived from AUXILIARY_FILES (non-journal schemas)."""
        assert {"Market", "Outfitting", "Shipyard", "NavRoute"} == AUXILIARY_SCHEMA_EVENTS
        # NavRoute is now navroute schema, not journal
        assert "NavRoute" in AUXILIARY_SCHEMA_EVENTS


class TestSchemaReferences:
    def test_journal1_schema_ref(self):
        assert EDDN_JOURNAL_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/journal/1"

    def test_commodity3_schema_ref(self):
        assert EDDN_COMMODITY_3_SCHEMA_REF == "https://eddn.edcd.io/schemas/commodity/3"

    def test_outfitting2_schema_ref(self):
        assert EDDN_OUTFITTING_2_SCHEMA_REF == "https://eddn.edcd.io/schemas/outfitting/2"

    def test_shipyard2_schema_ref(self):
        assert EDDN_SHIPYARD_2_SCHEMA_REF == "https://eddn.edcd.io/schemas/shipyard/2"

    def test_fsssignaldiscovered1_schema_ref(self):
        assert EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/fsssignaldiscovered/1"

    def test_fssdiscoveryscan1_schema_ref(self):
        assert EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/fssdiscoveryscan/1"

    def test_navroute1_schema_ref(self):
        assert EDDN_NAVROUTE_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/navroute/1"

    def test_approachsettlement1_schema_ref(self):
        assert EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/approachsettlement/1"

    def test_codexentry1_schema_ref(self):
        assert EDDN_CODEXENTRY_1_SCHEMA_REF == "https://eddn.edcd.io/schemas/codexentry/1"


class TestDisallowedFields:
    def test_latitude_not_in_global_disallowed(self):
        """Latitude removed from EDDN_DISALLOWED_FIELDS (needed for approachsettlement/1)."""
        assert "Latitude" not in EDDN_DISALLOWED_FIELDS

    def test_longitude_not_in_global_disallowed(self):
        """Longitude removed from EDDN_DISALLOWED_FIELDS (needed for approachsettlement/1)."""
        assert "Longitude" not in EDDN_DISALLOWED_FIELDS

    def test_global_disallowed_still_has_others(self):
        """Core disallowed fields remain."""
        expected = {"ActiveFine", "BoostUsed", "CockpitBreach", "FuelLevel", "FuelUsed",
                    "JumpDist", "Wanted"}
        assert expected.issubset(EDDN_DISALLOWED_FIELDS)

    def test_journal1_only_disallowed_contains_latitude(self):
        assert "Latitude" in JOURNAL_1_ONLY_DISALLOWED

    def test_journal1_only_disallowed_contains_longitude(self):
        assert "Longitude" in JOURNAL_1_ONLY_DISALLOWED

    def test_journal1_only_disallowed_contains_voucher_amount(self):
        assert "VoucherAmount" in JOURNAL_1_ONLY_DISALLOWED

    def test_journal1_only_disallowed_contains_traits(self):
        assert "Traits" in JOURNAL_1_ONLY_DISALLOWED

    def test_journal1_only_disallowed_complete(self):
        expected = {"Latitude", "Longitude", "VoucherAmount", "Traits"}
        assert expected == JOURNAL_1_ONLY_DISALLOWED


class TestFssSignalDisallowedFields:
    def test_time_remaining_in_disallowed(self):
        assert "TimeRemaining" in FSS_SIGNAL_DISALLOWED_FIELDS

    def test_event_in_disallowed(self):
        assert "event" in FSS_SIGNAL_DISALLOWED_FIELDS

    def test_system_address_in_disallowed(self):
        """SystemAddress belongs at message level, not in individual signals."""
        assert "SystemAddress" in FSS_SIGNAL_DISALLOWED_FIELDS

    def test_timestamp_not_in_disallowed(self):
        """Timestamp must be preserved in signals for fsssignaldiscovered/1 schema."""
        assert "timestamp" not in FSS_SIGNAL_DISALLOWED_FIELDS

    def test_complete_set(self):
        assert {"TimeRemaining", "event", "SystemAddress"} == FSS_SIGNAL_DISALLOWED_FIELDS


class TestDedicatedSchemaEvents:
    def test_fss_signal_discovered_in_dedicated(self):
        assert "FSSSignalDiscovered" in DEDICATED_SCHEMA_EVENTS

    def test_fss_discovery_scan_in_dedicated(self):
        assert "FSSDiscoveryScan" in DEDICATED_SCHEMA_EVENTS

    def test_approach_settlement_in_dedicated(self):
        assert "ApproachSettlement" in DEDICATED_SCHEMA_EVENTS

    def test_codex_entry_in_dedicated(self):
        assert "CodexEntry" in DEDICATED_SCHEMA_EVENTS

    def test_fss_signal_discovered_schema(self):
        entry = DEDICATED_SCHEMA_EVENTS["FSSSignalDiscovered"]
        assert entry["schema"] == "fsssignaldiscovered"
        assert entry["schema_ref"] == EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF

    def test_fss_discovery_scan_schema(self):
        entry = DEDICATED_SCHEMA_EVENTS["FSSDiscoveryScan"]
        assert entry["schema"] == "fssdiscoveryscan"
        assert entry["schema_ref"] == EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF

    def test_approach_settlement_schema(self):
        entry = DEDICATED_SCHEMA_EVENTS["ApproachSettlement"]
        assert entry["schema"] == "approachsettlement"
        assert entry["schema_ref"] == EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF

    def test_codex_entry_schema(self):
        entry = DEDICATED_SCHEMA_EVENTS["CodexEntry"]
        assert entry["schema"] == "codexentry"
        assert entry["schema_ref"] == EDDN_CODEXENTRY_1_SCHEMA_REF

    def test_only_four_dedicated_events(self):
        assert len(DEDICATED_SCHEMA_EVENTS) == 4
