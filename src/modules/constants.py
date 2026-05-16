"""Shared constants for ED Journal Monitor."""

from typing import Literal

# EDDN schema references
EDDN_JOURNAL_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/journal/1"
EDDN_COMMODITY_3_SCHEMA_REF = "https://eddn.edcd.io/schemas/commodity/3"
EDDN_OUTFITTING_2_SCHEMA_REF = "https://eddn.edcd.io/schemas/outfitting/2"
EDDN_SHIPYARD_2_SCHEMA_REF = "https://eddn.edcd.io/schemas/shipyard/2"
EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/fsssignaldiscovered/1"
EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/fssdiscoveryscan/1"
EDDN_NAVROUTE_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/navroute/1"
EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/approachsettlement/1"
EDDN_CODEXENTRY_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/codexentry/1"
EDDN_NAVBEACONSCAN_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/navbeaconscan/1"
EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/fcmaterials_journal/1"

# Events that should be reported to EDDN
REPORTABLE_EVENTS = {
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
    "NavBeaconScan",
    "FCMaterials",
}

# Journal events that require auxiliary JSON files.
# Each entry maps an event type to its sidecar filename and EDDN schema type.
# schema "commodity"/"outfitting"/"shipyard"/"navroute" means dedicated transform methods.
AuxiliarySchemaType = Literal["navroute", "commodity", "outfitting", "shipyard", "fcmaterials"]

AUXILIARY_FILES: dict[str, dict[str, str]] = {
    "Market": {"filename": "Market.json", "schema": "commodity"},
    "Outfitting": {"filename": "Outfitting.json", "schema": "outfitting"},
    "Shipyard": {"filename": "Shipyard.json", "schema": "shipyard"},
    "NavRoute": {"filename": "NavRoute.json", "schema": "navroute"},
    "FCMaterials": {"filename": "FCMaterials.json", "schema": "fcmaterials"},
}

# Events that use non-journal auxiliary schemas (derived from AUXILIARY_FILES)
# All auxiliary schemas are now dedicated (none use journal/1)
AUXILIARY_SCHEMA_EVENTS = set(AUXILIARY_FILES.keys())

# Events that use dedicated (non-journal/1, non-auxiliary) EDDN schemas
# Each entry maps an event type to its schema name and schema ref
DEDICATED_SCHEMA_EVENTS: dict[str, dict[str, str]] = {
    "FSSSignalDiscovered": {"schema": "fsssignaldiscovered", "schema_ref": EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF},
    "FSSDiscoveryScan": {"schema": "fssdiscoveryscan", "schema_ref": EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF},
    "ApproachSettlement": {"schema": "approachsettlement", "schema_ref": EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF},
    "CodexEntry": {"schema": "codexentry", "schema_ref": EDDN_CODEXENTRY_1_SCHEMA_REF},
    "NavBeaconScan": {"schema": "navbeaconscan", "schema_ref": EDDN_NAVBEACONSCAN_1_SCHEMA_REF},
}

# Fields that EDDN disallows per journal/1 schema - must be stripped before submission
# See: https://eddn.edcd.io/schemas/journal/1
# Note: Latitude, Longitude, VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered
# are removed from this global set because they are valid in some dedicated schemas
# (e.g. approachsettlement/1 needs Latitude/Longitude, codexentry/1 needs the others).
# They are instead in JOURNAL_1_ONLY_DISALLOWED and stripped only for journal/1.
EDDN_DISALLOWED_FIELDS = {
    "ActiveFine",
    "BoostUsed",
    "CockpitBreach",
    "FuelLevel",
    "FuelUsed",
    "JumpDist",
    "Wanted",
    # Progress — personal scan data in FSSDiscoveryScan, disallowed in fssdiscoveryscan/1
    "Progress",
    # IsNewEntry/NewTraitsDiscovered — personal data in CodexEntry, disallowed in codexentry/1
    "IsNewEntry",
    "NewTraitsDiscovered",
}

# Fields disallowed in journal/1 specifically, but valid in some dedicated schemas.
# These are stripped during journal/1 transform but preserved for dedicated schemas.
JOURNAL_1_ONLY_DISALLOWED = {"Latitude", "Longitude", "VoucherAmount", "Traits"}

# Fields disallowed inside Factions[] items per EDDN journal/1 schema
EDDN_FACTIONS_DISALLOWED_FIELDS = {
    "HappiestSystem",
    "HomeSystem",
    "MyReputation",
    "SquadronFaction",
}

# Fields stripped from individual FSSSignalDiscovered signals before batching
FSS_SIGNAL_DISALLOWED_FIELDS = {"TimeRemaining", "event", "SystemAddress"}
