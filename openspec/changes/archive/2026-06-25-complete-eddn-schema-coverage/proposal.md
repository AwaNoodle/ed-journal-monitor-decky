## Why

An audit against the live EDDN schema set (18 schemas) shows the plugin covers 12 and is missing four journal-sourced schemas (`scanbarycentre/1`, `fssbodysignals/1`, `dockinggranted/1`, `dockingdenied/1`), and the README's coverage tables have drifted from the code (`FCMaterials` is implemented but undocumented). Closing these gaps makes the plugin a complete EDDN contributor and keeps documentation trustworthy.

## What Changes

- Add EDDN submission support for four new journal-sourced events, each via the existing dedicated-schema routing path:
  - `ScanBaryCentre` → `scanbarycentre/1` (augment `StarPos`/`StarSystem` from session state)
  - `FSSBodySignals` → `fssbodysignals/1` (augment `StarSystem`/`StarPos`; strip `*_Localised` inside `Signals[]`)
  - `DockingGranted` → `dockinggranted/1` (passthrough + header flags; no `StarPos`)
  - `DockingDenied` → `dockingdenied/1` (passthrough + header flags; no `StarPos`)
- Reconcile documentation: add the missing `FCMaterials` row and the four new schema rows to the README coverage tables, and add a standing coverage matrix at `reports/eddn-coverage-audit.md`.

## Out of Scope: black-market / prohibited data

The audit confirmed the black-market data gap is **not fillable by a journal-only plugin**: `blackmarket/1` is deprecated, and its `commodity/3` replacement (`prohibited`/`economies` arrays) is CAPI-sourced — the commodity-README states *"the Journal Market.json doesn't contain `economies` or `prohibited` data, leave these entirely out of the message."* This plugin reads only `Market.json`, so emitting `prohibited` would violate EDDN guidance. This finding is recorded in the coverage audit.

## Capabilities

### New Capabilities
- `scanbarycentre-support`: Recognize, validate, and transform `ScanBaryCentre` events into the `scanbarycentre/1` EDDN schema.
- `fssbodysignals-support`: Recognize, validate, and transform `FSSBodySignals` events into the `fssbodysignals/1` EDDN schema, including nested `_Localised` stripping.
- `docking-events-support`: Recognize, validate, and transform `DockingGranted` and `DockingDenied` events into the `dockinggranted/1` and `dockingdenied/1` EDDN schemas.

### Modified Capabilities
<!-- None. The new schemas are additive and follow the existing dedicated-schema routing established by eddn-submission; no existing requirement changes. -->

## Impact

- `src/modules/constants.py`: new schema-ref constants; new entries in `REPORTABLE_EVENTS` and `DEDICATED_SCHEMA_EVENTS`.
- `src/modules/validator.py`: new `REQUIRED_FIELDS` entries; four new `transform_*` methods.
- `src/modules/watcher.py`: four new entries in the `_process_dedicated_schema_event` dispatch dict.
- `tests/`: new tests for each transform (validation, schema ref, augmentation, `_Localised` stripping).
- Docs: `README.md`, `reports/eddn-coverage-audit.md`, `CHANGELOG.md`.
- No frontend, API, or dependency changes. No breaking changes.
