from __future__ import annotations

"""
EDDN event validator.
Validates journal events against EDDN journal/1 schema requirements.
"""

from typing import TYPE_CHECKING

from src.modules.constants import EDDN_DISALLOWED_FIELDS

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState

# Required fields per event type for EDDN journal/1 schema
REQUIRED_FIELDS: dict[str, list[str]] = {
    "FSDJump": ["timestamp", "StarSystem", "SystemAddress", "StarPos", "JumpDist", "FuelUsed", "FuelLevel"],
    "Scan": ["timestamp", "ScanType", "BodyName", "DistanceFromArrivalLS"],
    "Location": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "Docked": ["timestamp", "StationName", "StarSystem", "SystemAddress"],
    "FSSDiscoveryScan": ["timestamp", "SystemName", "SystemAddress"],
}

EDDN_JOURNAL_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/journal/1"


class EDDNValidator:
    """Validates journal events against EDDN schema requirements."""

    def validate(self, event: ParsedEvent) -> bool:
        """
        Validate that an event has all required fields for its type.
        Returns True if valid, False otherwise.
        """
        required = REQUIRED_FIELDS.get(event.event_type)
        if not required:
            return False

        return all(field in event.raw for field in required)

    def transform(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """
        Transform a validated event into an EDDN message:
        1. Strip disallowed fields
        2. Augment with horizons/odyssey flags
        3. Wrap in EDDN message structure
        """
        # Strip disallowed fields
        message_payload = {
            k: v for k, v in event.raw.items()
            if k not in EDDN_DISALLOWED_FIELDS
        }

        # Augment with horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_JOURNAL_1_SCHEMA_REF,
            "header": {},  # Populated by submitter with uploader info
            "message": message_payload,
        }
