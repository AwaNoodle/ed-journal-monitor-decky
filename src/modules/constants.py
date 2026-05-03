"""Shared constants for ED Journal Monitor."""

# Events that should be reported to EDDN under journal/1 schema
REPORTABLE_EVENTS = {"FSDJump", "Scan", "Location", "Docked", "FSSDiscoveryScan"}

# Fields that EDDN disallows - must be stripped before submission
EDDN_DISALLOWED_FIELDS = {
    "ActiveFine",
    "Crew",
    "Fines",
    "HottestSystem",
    "HottestMarket",
    "Collected",
    "HottestCommodity",
}
