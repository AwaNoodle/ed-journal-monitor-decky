"""Per-schema allow-lists for EDDN's strict (``additionalProperties: false``) schemas.

Every journal-sourced EDDN schema except ``journal/1`` (and ``blackmarket``, which this
plugin never emits) declares ``additionalProperties: false`` on ``message``: the gateway
rejects any key not named in that schema's ``properties``. Building those messages by
copying ``event.raw`` and subtracting a blacklist of known-bad fields is inverted relative
to that: the first time FDev adds a field to a covered event, every message on that schema
starts failing validation until the plugin is patched.

The tables below are an allow-list instead: the exact set of keys a schema's ``message``
(and each of its strict nested array/object containers) permits, derived from the schema
JSON itself, not from what this plugin currently sends. They are a static, hand-derived
snapshot of `EDCD/EDDN` branch `live` at the commit recorded in ``schema-versions.md`` --
the plugin ships stdlib-only and must never fetch schemas at runtime. A field that upstream
adds after this snapshot will not reach EDDN until this table is refreshed; that is a
deliberate trade-off against a blacklist that would silently permit *removed* fields
forever. ``tests/test_eddn_allowed_fields.py`` re-derives these tables from the pinned
fixture copies of the real schemas and asserts equality, so a stale table fails loudly.

``journal/1`` has **no entry** here -- its absence is the "this schema is open
(``additionalProperties: true``), keep using the blacklist" signal. Likewise
``fcmaterials_journal/1``'s ``Items[]`` has no ``additionalProperties`` constraint at all
(an open nested container), so it appears in ``ALLOW_LISTS`` with an empty ``nested`` --
only the message-level allow-list applies there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class SchemaAllowList:
    """The permitted key set for one strict schema's ``message`` object.

    ``message``: keys allowed directly on the message object.
    ``nested``: for each message-level key that is itself a strict (``additionalProperties:
    false``) container, the keys allowed inside it -- inside the object itself if it's a
    dict, or inside each item if it's an array. A key with no entry here is not itself
    filtered further (either it's a scalar, or it's an *open* nested container such as
    ``fcmaterials_journal/1``'s ``Items[]``).
    """

    message: frozenset[str]
    nested: Mapping[str, frozenset[str]] = field(default_factory=dict)


ALLOW_LISTS: dict[str, SchemaAllowList] = {
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "BodyID", "BodyName", "Latitude", "Longitude", "MarketID", "Name", "StarPos",
            "StarSystem", "StationAllegiance", "StationEconomies", "StationEconomy",
            "StationFaction", "StationGovernment", "StationServices", "SystemAddress",
            "event", "horizons", "odyssey", "timestamp",
        }),
        nested={
            "StationEconomies": frozenset({"Name", "Proportion"}),
            "StationFaction": frozenset({"FactionState", "Name"}),
        },
    ),
    EDDN_CODEXENTRY_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "BodyID", "BodyName", "Category", "EntryID", "Latitude", "Longitude", "Name",
            "NearestDestination", "Region", "StarPos", "SubCategory", "System",
            "SystemAddress", "Traits", "VoucherAmount", "event", "horizons", "odyssey",
            "timestamp",
        }),
    ),
    EDDN_COMMODITY_3_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "carrierDockingAccess", "commodities", "economies", "horizons", "marketId",
            "odyssey", "prohibited", "stationName", "stationType", "systemName",
            "timestamp",
        }),
        nested={
            "commodities": frozenset({
                "buyPrice", "demand", "demandBracket", "meanPrice", "name", "sellPrice",
                "statusFlags", "stock", "stockBracket",
            }),
            "economies": frozenset({"name", "proportion"}),
        },
    ),
    EDDN_DOCKINGDENIED_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "MarketID", "Reason", "StationName", "StationType", "event", "horizons",
            "odyssey", "timestamp",
        }),
    ),
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "LandingPad", "MarketID", "StationName", "StationType", "event", "horizons",
            "odyssey", "timestamp",
        }),
    ),
    EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "CarrierID", "CarrierName", "Items", "MarketID", "event", "horizons",
            "odyssey", "timestamp",
        }),
        # Items[] is an open container (no additionalProperties constraint) -- no nested
        # entry; it stays on the existing blacklist (_strip_disallowed).
    ),
    EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "Count", "StarPos", "SystemAddress", "SystemName", "event", "horizons",
            "odyssey", "timestamp",
        }),
    ),
    EDDN_FSSBODYSIGNALS_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "BodyID", "BodyName", "Signals", "StarPos", "StarSystem", "SystemAddress",
            "event", "horizons", "odyssey", "timestamp",
        }),
        nested={
            "Signals": frozenset({"Count", "Type"}),
        },
    ),
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "StarPos", "StarSystem", "SystemAddress", "event", "horizons", "odyssey",
            "signals", "timestamp",
        }),
        nested={
            "signals": frozenset({
                "IsStation", "OpposingPower", "SignalName", "SignalType",
                "SpawningFaction", "SpawningPower", "SpawningState", "ThreatLevel",
                "USSType", "timestamp",
            }),
        },
    ),
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "BodyCount", "NonBodyCount", "StarPos", "SystemAddress", "SystemName",
            "event", "horizons", "odyssey", "timestamp",
        }),
    ),
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "NumBodies", "StarPos", "StarSystem", "SystemAddress", "event", "horizons",
            "odyssey", "timestamp",
        }),
    ),
    EDDN_NAVROUTE_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({"Route", "event", "horizons", "odyssey", "timestamp"}),
        nested={
            "Route": frozenset({"StarClass", "StarPos", "StarSystem", "SystemAddress"}),
        },
    ),
    EDDN_OUTFITTING_2_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "horizons", "marketId", "modules", "odyssey", "stationName", "systemName",
            "timestamp",
        }),
    ),
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "AscendingNode", "BodyID", "Eccentricity", "MeanAnomaly",
            "OrbitalInclination", "OrbitalPeriod", "Periapsis", "SemiMajorAxis",
            "StarPos", "StarSystem", "SystemAddress", "event", "horizons", "odyssey",
            "timestamp",
        }),
    ),
    EDDN_SHIPYARD_2_SCHEMA_REF: SchemaAllowList(
        message=frozenset({
            "allowCobraMkIV", "horizons", "marketId", "odyssey", "ships", "stationName",
            "systemName", "timestamp",
        }),
    ),
}
