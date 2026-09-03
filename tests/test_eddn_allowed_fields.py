"""Drift test: ALLOW_LISTS must equal what the pinned upstream schema fixtures declare.

Derives each schema's permitted key set directly from the fixture JSON (mirroring how a
forbidden property is actually expressed upstream: listed in ``properties`` with
``{"$ref": "#/definitions/disallowed"}``) and asserts it equals the corresponding entry in
`src.modules.eddn_allowed_fields.ALLOW_LISTS`. A refreshed fixture that adds/removes a
permitted field, without ``ALLOW_LISTS`` being updated to match, fails this test loudly
instead of drifting silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from src.modules.eddn_allowed_fields import ALLOW_LISTS, SchemaAllowList

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "eddn-schemas"

DISALLOWED_REF = "#/definitions/disallowed"

# schema ref -> fixture filename. journal-v1.0.json is intentionally excluded: journal/1
# is the one open (additionalProperties: true) schema and has no ALLOW_LISTS entry.
SCHEMA_FIXTURES: dict[str, str] = {
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF: "approachsettlement-v1.0.json",
    EDDN_CODEXENTRY_1_SCHEMA_REF: "codexentry-v1.0.json",
    EDDN_COMMODITY_3_SCHEMA_REF: "commodity-v3.0.json",
    EDDN_DOCKINGDENIED_1_SCHEMA_REF: "dockingdenied-v1.0.json",
    EDDN_DOCKINGGRANTED_1_SCHEMA_REF: "dockinggranted-v1.0.json",
    EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF: "fcmaterials_journal-v1.0.json",
    EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF: "fssallbodiesfound-v1.0.json",
    EDDN_FSSBODYSIGNALS_1_SCHEMA_REF: "fssbodysignals-v1.0.json",
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF: "fssdiscoveryscan-v1.0.json",
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF: "fsssignaldiscovered-v1.0.json",
    EDDN_NAVBEACONSCAN_1_SCHEMA_REF: "navbeaconscan-v1.0.json",
    EDDN_NAVROUTE_1_SCHEMA_REF: "navroute-v1.0.json",
    EDDN_OUTFITTING_2_SCHEMA_REF: "outfitting-v2.0.json",
    EDDN_SCANBARYCENTRE_1_SCHEMA_REF: "scanbarycentre-v1.0.json",
    EDDN_SHIPYARD_2_SCHEMA_REF: "shipyard-v2.0.json",
}

# All 16 files referenced by the workplan, including journal-v1.0.json, must exist even
# though journal/1 has no ALLOW_LISTS entry -- it documents the "open schema" baseline.
ALL_FIXTURE_FILES = {*SCHEMA_FIXTURES.values(), "journal-v1.0.json"}


def _load_schema(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text(encoding="utf-8"))


def _derive_container_allowed(properties: dict) -> frozenset[str]:
    """Allowed keys for one object's ``properties`` block.

    A key is allowed unless its subschema is the ``disallowed`` $ref, or the key is the
    literal ``patternProperties`` string (an authoring artifact inside
    fsssignaldiscovered/1's signals[] items, not a real property name).
    """
    allowed = set()
    for name, subschema in properties.items():
        if name == "patternProperties":
            continue
        if subschema.get("$ref") == DISALLOWED_REF:
            continue
        allowed.add(name)
    return frozenset(allowed)


def _derive_allow_list(schema: dict) -> SchemaAllowList:
    message = schema["properties"]["message"]
    assert message.get("additionalProperties") is False, (
        "fixture is not a strict schema; SCHEMA_FIXTURES should not include it"
    )
    props = message.get("properties", {})
    top_allowed = _derive_container_allowed(props)

    nested: dict[str, frozenset[str]] = {}
    for name, subschema in props.items():
        if name == "patternProperties" or name not in top_allowed:
            continue
        container = None
        if subschema.get("type") == "array" and isinstance(subschema.get("items"), dict):
            container = subschema["items"]
        elif subschema.get("type") == "object" and "properties" in subschema:
            container = subschema
        if container is None:
            continue
        if container.get("additionalProperties") is not False:
            # Open nested container (e.g. fcmaterials_journal/1's Items[]) -- no
            # allow-list entry; it stays on the blacklist.
            continue
        nested[name] = _derive_container_allowed(container.get("properties", {}))

    return SchemaAllowList(message=top_allowed, nested=nested)


def test_fixture_files_present():
    for filename in ALL_FIXTURE_FILES:
        assert (FIXTURES_DIR / filename).is_file(), f"missing fixture {filename}"


def test_journal_v1_is_open_and_has_no_allow_list_entry():
    schema = _load_schema("journal-v1.0.json")
    assert schema["properties"]["message"]["additionalProperties"] is True


@pytest.mark.parametrize("schema_ref", sorted(SCHEMA_FIXTURES))
def test_allow_list_matches_fixture(schema_ref):
    schema = _load_schema(SCHEMA_FIXTURES[schema_ref])
    derived = _derive_allow_list(schema)
    configured = ALLOW_LISTS[schema_ref]

    assert configured.message == derived.message, (
        f"{schema_ref}: message allow-list drifted from fixture.\n"
        f"missing from ALLOW_LISTS: {derived.message - configured.message}\n"
        f"extra in ALLOW_LISTS: {configured.message - derived.message}"
    )
    assert dict(configured.nested) == dict(derived.nested), (
        f"{schema_ref}: nested allow-list drifted from fixture.\n"
        f"derived: {dict(derived.nested)}\nconfigured: {dict(configured.nested)}"
    )


def test_every_strict_schema_fixture_is_covered():
    """Every strict-schema fixture on disk has a SCHEMA_FIXTURES/ALLOW_LISTS entry."""
    strict_fixtures = {
        f.name
        for f in FIXTURES_DIR.glob("*.json")
        if f.name != "journal-v1.0.json"
    }
    assert strict_fixtures == set(SCHEMA_FIXTURES.values())
    assert set(ALLOW_LISTS.keys()) == set(SCHEMA_FIXTURES.keys())
