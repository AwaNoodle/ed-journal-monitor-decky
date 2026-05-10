"""Shared constants for ED Journal Monitor."""

from typing import Literal

# EDDN schema references
EDDN_JOURNAL_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/journal/1"
EDDN_COMMODITY_3_SCHEMA_REF = "https://eddn.edcd.io/schemas/commodity/3"
EDDN_OUTFITTING_2_SCHEMA_REF = "https://eddn.edcd.io/schemas/outfitting/2"
EDDN_SHIPYARD_2_SCHEMA_REF = "https://eddn.edcd.io/schemas/shipyard/2"

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
    "ApproachBody",
    "LeaveBody",
    "ApproachSettlement",
    "CarrierJump",
    "FSSSignalDiscovered",
    "SAAScanComplete",
}

# Journal events that require auxiliary JSON files.
# Each entry maps an event type to its sidecar filename and EDDN schema type.
# schema "journal" means the auxiliary data goes through journal/1 validate+transform;
# schema "commodity"/"outfitting"/"shipyard" means dedicated transform methods are used.
AuxiliarySchemaType = Literal["journal", "commodity", "outfitting", "shipyard"]

AUXILIARY_FILES: dict[str, dict[str, str]] = {
    "Market": {"filename": "Market.json", "schema": "commodity"},
    "Outfitting": {"filename": "Outfitting.json", "schema": "outfitting"},
    "Shipyard": {"filename": "Shipyard.json", "schema": "shipyard"},
    "NavRoute": {"filename": "NavRoute.json", "schema": "journal"},
}

# Events that use non-journal auxiliary schemas (derived from AUXILIARY_FILES)
AUXILIARY_SCHEMA_EVENTS = {
    event for event, info in AUXILIARY_FILES.items() if info["schema"] != "journal"
}

# Fields that EDDN disallows per journal/1 schema - must be stripped before submission
# See: https://eddn.edcd.io/schemas/journal/1
EDDN_DISALLOWED_FIELDS = {
    "ActiveFine",
    "BoostUsed",
    "CockpitBreach",
    "FuelLevel",
    "FuelUsed",
    "IsNewEntry",
    "JumpDist",
    "Latitude",
    "Longitude",
    "NewTraitsDiscovered",
    "Traits",
    "VoucherAmount",
    "Wanted",
}
