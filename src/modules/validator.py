from __future__ import annotations

"""
EDDN event validator.
Validates journal events against EDDN schema requirements.
"""

from typing import TYPE_CHECKING

from src.modules.constants import (
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_DISALLOWED_FIELDS,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState

# Required fields per event type for EDDN journal/1 schema
REQUIRED_FIELDS: dict[str, list[str]] = {
    "FSDJump": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "Scan": ["timestamp", "ScanType", "BodyName", "DistanceFromArrivalLS"],
    "Location": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "Docked": ["timestamp", "StationName", "StarSystem", "SystemAddress"],
    "FSSDiscoveryScan": ["timestamp", "SystemName", "SystemAddress"],
    "NavRoute": ["timestamp", "event", "Route"],
    "ApproachBody": ["timestamp", "StarSystem", "SystemAddress", "BodyName"],
    "LeaveBody": ["timestamp", "StarSystem", "SystemAddress", "BodyName"],
    "ApproachSettlement": ["timestamp", "StarSystem", "SystemAddress", "StationName"],
    "CarrierJump": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "FSSSignalDiscovered": ["timestamp", "SystemAddress", "SignalName"],
    "SAAScanComplete": ["timestamp", "BodyName", "SystemAddress"],
}


def _strip_disallowed(obj: object) -> object:
    """
    Recursively strip EDDN-disallowed keys from a data structure.

    Removes:
    - Keys in EDDN_DISALLOWED_FIELDS
    - Keys ending in '_Localised' (EDDN schema rejects these at all levels)

    Handles nested dicts and lists (e.g. Factions[], StationEconomies[]).
    """
    if isinstance(obj, dict):
        return {
            k: _strip_disallowed(v)
            for k, v in obj.items()
            if k not in EDDN_DISALLOWED_FIELDS and not k.endswith("_Localised")
        }
    if isinstance(obj, list):
        return [_strip_disallowed(item) for item in obj]
    return obj


def _as_dict_list(value: object) -> list[dict]:
    """Normalize a JSON value into a list of dictionaries."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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

        if not all(field in event.raw for field in required):
            return False

        if event.event_type == "NavRoute":
            route = event.raw.get("Route")
            if not isinstance(route, list) or not route:
                return False
            return all(isinstance(route_entry, dict) and "SystemAddress" in route_entry for route_entry in route)

        return True

    def transform(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """
        Transform a validated event into an EDDN message:
        1. Strip disallowed fields and _Localised keys (recursively)
        2. Augment with horizons/odyssey flags
        3. Wrap in EDDN message structure
        """
        # Recursively strip disallowed fields and _Localised keys
        message_payload = _strip_disallowed(event.raw)

        # Augment with horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_JOURNAL_1_SCHEMA_REF,
            "header": {},  # Populated by submitter with uploader info
            "message": message_payload,
        }

    def transform_commodity(self, market_data: dict, session_state: SessionState) -> dict | None:
        """Transform Market.json data into commodity/3 EDDN schema.
        Returns None if no valid commodities remain after filtering,
        or if required station fields are missing/empty.
        """
        timestamp = market_data.get("timestamp", "")
        system_name = market_data.get("StarSystem", "")
        station_name = market_data.get("StationName", "")
        market_id = market_data.get("MarketID", 0)

        # EDDN requires non-empty systemName/stationName and non-zero marketId
        if not system_name or not station_name or not market_id:
            return None

        commodities = []
        for item in _as_dict_list(market_data.get("Items", [])):
            name = item.get("Name")
            if not name or not isinstance(name, str):
                continue

            stock_bracket = item.get("StockBracket", 0)
            demand_bracket = item.get("DemandBracket", 0)
            if stock_bracket == 0 and demand_bracket == 0:
                continue

            commodities.append({
                "name": name,
                "meanPrice": item.get("MeanPrice", 0),
                "buyPrice": item.get("BuyPrice", 0),
                "stock": item.get("Stock", 0),
                "stockBracket": stock_bracket,
                "sellPrice": item.get("SellPrice", 0),
                "demand": item.get("Demand", 0),
                "demandBracket": demand_bracket,
            })

        if not commodities:
            return None

        return {
            "$schemaRef": EDDN_COMMODITY_3_SCHEMA_REF,
            "header": {},
            "message": {
                "timestamp": timestamp,
                "systemName": system_name,
                "stationName": station_name,
                "marketId": market_id,
                "commodities": commodities,
                "horizons": session_state.horizons,
                "odyssey": session_state.odyssey,
            },
        }

    def transform_outfitting(self, outfitting_data: dict, session_state: SessionState) -> dict | None:
        """Transform Outfitting.json data into outfitting/2 EDDN schema.
        Returns None if no valid modules remain, or if required station
        fields are missing/empty.
        """
        timestamp = outfitting_data.get("timestamp", "")
        system_name = outfitting_data.get("StarSystem", "")
        station_name = outfitting_data.get("StationName", "")
        market_id = outfitting_data.get("MarketID", 0)

        if not system_name or not station_name or not market_id:
            return None

        modules = []
        for module in _as_dict_list(outfitting_data.get("Modules", [])):
            name = module.get("Name")
            if not name or not isinstance(name, str):
                continue
            modules.append(name)

        if not modules:
            return None

        return {
            "$schemaRef": EDDN_OUTFITTING_2_SCHEMA_REF,
            "header": {},
            "message": {
                "timestamp": timestamp,
                "systemName": system_name,
                "stationName": station_name,
                "marketId": market_id,
                "modules": modules,
                "horizons": session_state.horizons,
                "odyssey": session_state.odyssey,
            },
        }

    def transform_shipyard(self, shipyard_data: dict, session_state: SessionState) -> dict | None:
        """Transform Shipyard.json data into shipyard/2 EDDN schema.
        Returns None if no valid ships remain, or if required station
        fields are missing/empty.
        """
        timestamp = shipyard_data.get("timestamp", "")
        system_name = shipyard_data.get("StarSystem", "")
        station_name = shipyard_data.get("StationName", "")
        market_id = shipyard_data.get("MarketID", 0)

        if not system_name or not station_name or not market_id:
            return None

        ships = []
        for ship in _as_dict_list(shipyard_data.get("PriceList", [])):
            ship_type = ship.get("ShipType")
            if not ship_type or not isinstance(ship_type, str):
                continue
            ships.append(ship_type)

        if not ships:
            return None

        return {
            "$schemaRef": EDDN_SHIPYARD_2_SCHEMA_REF,
            "header": {},
            "message": {
                "timestamp": timestamp,
                "systemName": system_name,
                "stationName": station_name,
                "marketId": market_id,
                "ships": ships,
                "horizons": session_state.horizons,
                "odyssey": session_state.odyssey,
            },
        }
