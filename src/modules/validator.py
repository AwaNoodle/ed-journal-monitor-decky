from __future__ import annotations

"""
EDDN event validator.
Validates journal events against EDDN schema requirements.
"""

from typing import TYPE_CHECKING, ClassVar

from src.modules.constants import (
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
    EDDN_CODEXENTRY_1_SCHEMA_REF,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_DISALLOWED_FIELDS,
    EDDN_DOCKINGDENIED_1_SCHEMA_REF,
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF,
    EDDN_FACTIONS_DISALLOWED_FIELDS,
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
    JOURNAL_1_ONLY_DISALLOWED,
)

if TYPE_CHECKING:
    from src.modules.parser import ParsedEvent, SessionState

# Required fields per event type for EDDN journal/1 schema
REQUIRED_FIELDS: dict[str, list[str]] = {
    "FSDJump": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "Scan": ["timestamp", "ScanType", "BodyName", "DistanceFromArrivalLS"],
    "Location": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "Docked": ["timestamp", "StationName", "StarSystem", "SystemAddress"],
    "FSSDiscoveryScan": ["timestamp", "SystemAddress"],
    "NavRoute": ["timestamp", "event", "Route"],
    "ApproachSettlement": [
        "timestamp", "StarSystem", "SystemAddress",
        "BodyID", "BodyName", "MarketID", "Latitude", "Longitude",
    ],
    "CarrierJump": ["timestamp", "StarSystem", "SystemAddress", "StarPos"],
    "FSSSignalDiscovered": ["timestamp", "SystemAddress", "SignalName"],
    "SAASignalsFound": ["timestamp", "StarSystem", "SystemAddress"],
    "CodexEntry": ["timestamp", "SystemAddress", "Name", "Region", "EntryID", "BodyID", "BodyName"],
    "NavBeaconScan": ["timestamp", "NumBodies"],
    "FSSAllBodiesFound": ["timestamp", "SystemName", "SystemAddress", "Count"],
    "ScanBaryCentre": ["timestamp", "SystemAddress", "BodyID"],
    "FSSBodySignals": ["timestamp", "BodyName", "BodyID", "SystemAddress", "Signals"],
    "DockingGranted": ["timestamp", "MarketID", "StationName"],
    "DockingDenied": ["timestamp", "MarketID", "StationName", "Reason"],
}


def _strip_disallowed(obj: object, keep_fields: set[str] | None = None) -> object:
    """
    Recursively strip EDDN-disallowed keys from a data structure.

    Removes:
    - Keys in EDDN_DISALLOWED_FIELDS
    - Keys ending in '_Localised' (EDDN schema rejects these at all levels)
    - Keys in keep_fields are preserved even if they'd otherwise be stripped

    Handles nested dicts and lists (e.g. Factions[], StationEconomies[]).
    """
    if isinstance(obj, dict):
        return {
            k: _strip_disallowed(v, keep_fields)
            for k, v in obj.items()
            if (k not in EDDN_DISALLOWED_FIELDS or (keep_fields and k in keep_fields))
            and not k.endswith("_Localised")
        }
    if isinstance(obj, list):
        return [_strip_disallowed(item, keep_fields) for item in obj]
    return obj


def _sanitize_eddn_name(name: str) -> str:
    """Sanitize an EDDN name from journal data.

    The journal uses internal symbolic names like '$platinum_name;'
    or '$SideWinder_name;' while EDDN expects the clean form
    'platinum' or 'SideWinder'.  This function strips the leading
    '$' and trailing '_name;' (or just ';' if no '_name' suffix
    is present).

    Applies to commodity names from Market.json, ShipType from
    Shipyard.json, and module names from Outfitting.json.
    Names that are already in the clean format pass through unchanged.
    """
    if name.startswith('$'):
        name = name[1:]
    if name.endswith('_name;'):
        name = name[:-6]
    elif name.endswith(';'):
        name = name[:-1]
    return name


def _as_dict_list(value: object) -> list[dict]:
    """Normalize a JSON value into a list of dictionaries."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


class EDDNValidator:
    """Validates journal events against EDDN schema requirements."""

    # Events that natively contain StarPos in the journal
    _STARPOS_EVENTS: ClassVar[set[str]] = {"FSDJump", "Location", "CarrierJump"}

    # Station-context events whose EDDN schemas do not include StarPos and so
    # must not require it (e.g. dockinggranted/1, dockingdenied/1).
    _NO_STARPOS_EVENTS: ClassVar[set[str]] = {"DockingGranted", "DockingDenied"}

    def validate(self, event: ParsedEvent, session_state: SessionState | None = None) -> bool:  # noqa: PLR0911
        """
        Validate that an event has all required fields for its type.
        Returns True if valid, False otherwise.

        Also checks that events lacking StarPos can be augmented from
        session_state (EDDN journal/1 and dedicated schemas require StarPos).
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

        # ApproachSettlement requires StationName (journal) or Name (already renamed)
        if event.event_type == "ApproachSettlement" and "StationName" not in event.raw and "Name" not in event.raw:
            return False

        # EDDN requires StarPos on most messages.
        # Events that natively have StarPos are fine. Station-context events
        # (docking) never carry StarPos. Others need augmentation.
        if (
            event.event_type not in self._STARPOS_EVENTS
            and event.event_type not in self._NO_STARPOS_EVENTS
            and "StarPos" not in event.raw
        ):
            if not session_state or not session_state.star_pos:
                return False
            # Check SystemAddress matches cached position
            event_sys = event.raw.get("SystemAddress")
            if (
                event_sys is not None
                and session_state.system_address is not None
                and event_sys != session_state.system_address
            ):
                return False

        return True

    def transform(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """
        Transform a validated event into an EDDN journal/1 message:
        1. Strip disallowed fields and _Localised keys (recursively)
        2. Strip journal/1-only disallowed fields (Latitude, Longitude, etc.)
        3. Strip Factions-specific disallowed fields
        4. Augment with StarPos/StarSystem if missing and available
        5. Augment with horizons/odyssey flags
        6. Wrap in EDDN message structure
        """
        # Recursively strip disallowed fields and _Localised keys
        message_payload = _strip_disallowed(event.raw)

        # Strip journal/1-only disallowed fields
        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Strip Factions-specific disallowed fields
        if "Factions" in message_payload:
            message_payload["Factions"] = [
                {k: v for k, v in f.items() if k not in EDDN_FACTIONS_DISALLOWED_FIELDS}
                for f in message_payload["Factions"]
                if isinstance(f, dict)
            ]

        # Augment with StarPos and StarSystem if the event lacks them
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            # Only augment if SystemAddress matches (prevent stale coordinates)
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos
                if not message_payload.get("StarSystem") and session_state.star_system:
                    message_payload["StarSystem"] = session_state.star_system

        # Augment with horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_JOURNAL_1_SCHEMA_REF,
            "header": {},  # Populated by submitter with uploader info
            "message": message_payload,
        }

    def transform_fss_signal_discovered(self, batch: dict, session_state: SessionState) -> dict | None:
        """Transform a batch of FSSSignalDiscovered signals into fsssignaldiscovered/1 message.

        Args:
            batch: Dict with keys: signals, last_timestamp, system_address,
                   star_system, star_pos
            session_state: Current session state for augmentation.

        Returns:
            EDDN message dict or None if no signals.
        """
        signals = batch.get("signals", [])
        if not signals:
            return None

        # Strip _Localised keys from each signal
        cleaned_signals = []
        for signal in signals:
            cleaned = {k: v for k, v in signal.items() if not k.endswith("_Localised")}
            cleaned_signals.append(cleaned)

        # Position data comes from the batch (augmented by SignalBatcher.flush()
        # using session_state). The batcher already verified SystemAddress matches
        # and discarded batches without valid position data.
        star_system = batch.get("star_system", "")
        star_pos = batch.get("star_pos", [])
        system_address = batch.get("system_address")

        payload: dict = {
            "timestamp": batch.get("last_timestamp", ""),
            "event": "FSSSignalDiscovered",
            "StarSystem": star_system,
            "StarPos": star_pos,
            "SystemAddress": system_address,
            "signals": cleaned_signals,
            "horizons": session_state.horizons,
            "odyssey": session_state.odyssey,
        }

        return {
            "$schemaRef": EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF,
            "header": {},
            "message": payload,
        }

    def transform_fss_discovery_scan(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """Transform a FSSDiscoveryScan event into fssdiscoveryscan/1 message.

        Strips disallowed fields and _Localised keys, then builds message
        with required fields: timestamp, StarSystem, StarPos, SystemAddress,
        BodyCount, NonBodyCount, horizons, odyssey.
        """
        # Strip disallowed fields and _Localised
        message_payload = _strip_disallowed(event.raw)

        # Strip journal/1-only disallowed fields
        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # fssdiscoveryscan/1 uses SystemName (same as journal), not StarSystem
        # No rename needed - SystemName is the correct field name for this schema.

        # Augment StarPos from session_state if missing
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos
        # Augment SystemName from session_state if missing
        if "SystemName" not in message_payload and session_state.star_system:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["SystemName"] = session_state.star_system

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_navroute(self, auxiliary_data: dict, session_state: SessionState) -> dict | None:
        """Transform NavRoute.json data into navroute/1 EDDN schema.

        The navroute/1 schema only allows timestamp, event, Route,
        horizons, and odyssey at message level. StarSystem, StarPos, and
        SystemAddress belong only inside Route[] entries (where the journal
        already provides them). Route entries have _Localised keys stripped.

        Returns None if the auxiliary data is NavRouteClear (empty route)
        or has an unexpected event type.
        """
        # NavRouteClear is not a valid NavRoute submission — skip it
        if auxiliary_data.get("event") == "NavRouteClear":
            return None

        # Strip disallowed and _Localised from the top-level payload
        message_payload = _strip_disallowed(auxiliary_data)

        # Strip journal/1-only disallowed fields
        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Strip _Localised from Route entries
        route = message_payload.get("Route")
        if isinstance(route, list):
            cleaned_route = []
            for entry in route:
                if isinstance(entry, dict):
                    cleaned = {k: v for k, v in entry.items() if not k.endswith("_Localised")}
                    cleaned_route.append(cleaned)
                else:
                    cleaned_route.append(entry)
            message_payload["Route"] = cleaned_route

        # Remove message-level StarSystem/StarPos/SystemAddress if present.
        # The navroute/1 schema does not allow these at message level;
        # they belong inside individual Route entries only.
        message_payload.pop("StarSystem", None)
        message_payload.pop("StarPos", None)
        message_payload.pop("SystemAddress", None)

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_NAVROUTE_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_approach_settlement(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """Transform an ApproachSettlement event into approachsettlement/1 message.

        Preserves Latitude and Longitude (required by this schema).
        Renames StationName→Name (EDDN schema uses Name).
        Strips other disallowed fields and _Localised keys.
        """
        # Strip disallowed fields, but keep Latitude/Longitude
        keep_fields = {"Latitude", "Longitude"}
        message_payload = _strip_disallowed(event.raw, keep_fields=keep_fields)

        # Strip journal/1-only disallowed fields EXCEPT Latitude/Longitude
        for field in JOURNAL_1_ONLY_DISALLOWED:
            if field not in keep_fields:
                message_payload.pop(field, None)

        # Rename StationName→Name (EDDN approachsettlement/1 uses "Name")
        if "StationName" in message_payload:
            if "Name" not in message_payload:
                message_payload["Name"] = message_payload.pop("StationName")
            else:
                # Name already present, just remove StationName
                message_payload.pop("StationName")

        # Augment StarPos/StarSystem from session_state
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos
        if "StarSystem" not in message_payload and session_state.star_system:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarSystem"] = session_state.star_system

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_codex_entry(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """Transform a CodexEntry event into codexentry/1 message.

        Preserves fields that are disallowed in journal/1 but valid in
        codexentry/1: VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered.
        """
        # Strip disallowed fields, but keep codexentry-specific fields
        keep_fields = {"VoucherAmount", "Traits"}
        message_payload = _strip_disallowed(event.raw, keep_fields=keep_fields)

        # Strip journal/1-only disallowed fields EXCEPT the ones we're keeping
        for field in JOURNAL_1_ONLY_DISALLOWED:
            if field not in keep_fields:
                message_payload.pop(field, None)

        # Augment StarPos/StarSystem from session_state
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos
        if "StarSystem" not in message_payload and session_state.star_system:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarSystem"] = session_state.star_system

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_CODEXENTRY_1_SCHEMA_REF,
            "header": {},
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

            # Skip NonMarketable commodities (per EDDN commodity-README)
            # Journal uses "nonde" prefix for "non-" categories
            category = item.get("Category", "")
            if category and "nonde" in category.lower():
                continue

            stock_bracket = item.get("StockBracket", 0)
            demand_bracket = item.get("DemandBracket", 0)
            if stock_bracket == 0 and demand_bracket == 0:
                continue

            commodity = {
                "name": _sanitize_eddn_name(name),
                "meanPrice": item.get("MeanPrice", 0),
                "buyPrice": item.get("BuyPrice", 0),
                "stock": item.get("Stock", 0),
                "stockBracket": stock_bracket,
                "sellPrice": item.get("SellPrice", 0),
                "demand": item.get("Demand", 0),
                "demandBracket": demand_bracket,
            }

            # Include statusFlags if present (e.g. ["powerplay"])
            status_flags = item.get("StatusFlags")
            if status_flags and isinstance(status_flags, list):
                commodity["statusFlags"] = status_flags

            commodities.append(commodity)

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
        for module in _as_dict_list(outfitting_data.get("Items", [])):
            name = module.get("Name")
            if not name or not isinstance(name, str):
                continue
            modules.append(_sanitize_eddn_name(name))

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
            ships.append(_sanitize_eddn_name(ship_type))

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

    def transform_navbeacon_scan(self, event: ParsedEvent, session_state: SessionState) -> dict:
        """Transform a NavBeaconScan event into navbeaconscan/1 message.

        Strips disallowed fields and _Localised keys, then builds message
        with required fields: timestamp, event, StarSystem, StarPos,
        SystemAddress, NumBodies, horizons, odyssey.
        """
        # Strip disallowed fields and _Localised
        message_payload = _strip_disallowed(event.raw)

        # Strip journal/1-only disallowed fields
        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Augment StarPos from session_state if missing
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos
        # Augment StarSystem from session_state if missing
        if "StarSystem" not in message_payload and session_state.star_system:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarSystem"] = session_state.star_system

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_NAVBEACONSCAN_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_fss_all_bodies_found(
        self, event: ParsedEvent, session_state: SessionState
    ) -> dict:
        """Transform an FSSAllBodiesFound event into fssallbodiesfound/1 message.

        Strips disallowed fields and _Localised keys, augments StarPos from
        session state (not present in the journal event), and injects
        horizons/odyssey flags.
        """
        # Strip disallowed fields and _Localised
        message_payload = _strip_disallowed(event.raw)

        # Strip journal/1-only disallowed fields
        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Augment StarPos from session_state (not in journal event)
        if "StarPos" not in message_payload and session_state.star_pos:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["StarPos"] = session_state.star_pos

        # Augment SystemName from session_state if missing
        if "SystemName" not in message_payload and session_state.star_system:
            event_sys = message_payload.get("SystemAddress")
            if event_sys is None or event_sys == session_state.system_address:
                message_payload["SystemName"] = session_state.star_system

        # Add horizons/odyssey
        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_scan_bary_centre(
        self, event: ParsedEvent, session_state: SessionState
    ) -> dict | None:
        """Transform a ScanBaryCentre event into a scanbarycentre/1 message.

        Strips disallowed/_Localised fields, augments StarSystem and StarPos
        from session state (StarPos is not present in the journal event), and
        injects horizons/odyssey. Returns None when StarPos cannot be supplied,
        since it is required by the schema.
        """
        message_payload = _strip_disallowed(event.raw)

        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Augment StarPos/StarSystem from session state, gated by SystemAddress
        event_sys = message_payload.get("SystemAddress")
        if event_sys is None or event_sys == session_state.system_address:
            if "StarPos" not in message_payload and session_state.star_pos:
                message_payload["StarPos"] = session_state.star_pos
            if not message_payload.get("StarSystem") and session_state.star_system:
                message_payload["StarSystem"] = session_state.star_system

        # StarPos is required by scanbarycentre/1
        if "StarPos" not in message_payload:
            return None

        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_SCANBARYCENTRE_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_fss_body_signals(
        self, event: ParsedEvent, session_state: SessionState
    ) -> dict | None:
        """Transform an FSSBodySignals event into an fssbodysignals/1 message.

        Strips disallowed fields and _Localised keys (including Type_Localised
        nested inside Signals[]), augments StarSystem and StarPos from session
        state (neither is present in the journal event), and injects
        horizons/odyssey. Returns None when StarSystem/StarPos cannot be
        supplied, since both are required by the schema.
        """
        message_payload = _strip_disallowed(event.raw)

        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        # Augment StarPos/StarSystem from session state, gated by SystemAddress
        event_sys = message_payload.get("SystemAddress")
        if event_sys is None or event_sys == session_state.system_address:
            if "StarPos" not in message_payload and session_state.star_pos:
                message_payload["StarPos"] = session_state.star_pos
            if not message_payload.get("StarSystem") and session_state.star_system:
                message_payload["StarSystem"] = session_state.star_system

        # StarSystem and StarPos are required by fssbodysignals/1
        if "StarPos" not in message_payload or not message_payload.get("StarSystem"):
            return None

        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_FSSBODYSIGNALS_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_docking_granted(
        self, event: ParsedEvent, session_state: SessionState
    ) -> dict:
        """Transform a DockingGranted event into a dockinggranted/1 message.

        Station-context schema: passes through LandingPad, MarketID,
        StationName, StationType (no StarPos/StarSystem augmentation), strips
        disallowed/_Localised fields, and injects horizons/odyssey.
        """
        message_payload = _strip_disallowed(event.raw)

        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_DOCKINGGRANTED_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_docking_denied(
        self, event: ParsedEvent, session_state: SessionState
    ) -> dict:
        """Transform a DockingDenied event into a dockingdenied/1 message.

        Station-context schema: passes through Reason, MarketID, StationName,
        StationType (no StarPos/StarSystem augmentation), strips
        disallowed/_Localised fields (including Reason_Localised), and injects
        horizons/odyssey.
        """
        message_payload = _strip_disallowed(event.raw)

        for field in JOURNAL_1_ONLY_DISALLOWED:
            message_payload.pop(field, None)

        message_payload["horizons"] = session_state.horizons
        message_payload["odyssey"] = session_state.odyssey

        return {
            "$schemaRef": EDDN_DOCKINGDENIED_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }

    def transform_fc_materials(self, fc_data: dict, session_state: SessionState) -> dict | None:
        """Transform FCMaterials.json data into fcmaterials_journal/1 EDDN schema.

        Returns None if required fields are missing or Items list is empty.
        """
        timestamp = fc_data.get("timestamp", "")
        market_id = fc_data.get("MarketID")
        carrier_name = fc_data.get("CarrierName", "")
        carrier_id = fc_data.get("CarrierID", "")

        # Validate required top-level fields
        if not timestamp or not market_id or not carrier_name or not carrier_id:
            return None

        items = fc_data.get("Items", [])
        if not isinstance(items, list) or not items:
            return None

        # Strip _Localised and disallowed fields from each Item
        cleaned_items = []
        for item in _as_dict_list(items):
            cleaned = _strip_disallowed(item)
            cleaned_items.append(cleaned)

        if not cleaned_items:
            return None

        message_payload = {
            "timestamp": timestamp,
            "event": "FCMaterials",
            "MarketID": market_id,
            "CarrierName": carrier_name,
            "CarrierID": carrier_id,
            "Items": cleaned_items,
            "horizons": session_state.horizons,
            "odyssey": session_state.odyssey,
        }

        return {
            "$schemaRef": EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF,
            "header": {},
            "message": message_payload,
        }
