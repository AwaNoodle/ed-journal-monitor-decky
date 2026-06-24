## 1. Pre-implementation schema verification

- [x] 1.1 Cross-reference the live EDDN READMEs for `scanbarycentre/1`, `fssbodysignals/1`, `dockinggranted/1`, `dockingdenied/1`; record schema versions checked for the audit report
- [x] 1.2 Black-market/prohibited investigation — confirmed CAPI-only; commodity-README forbids sending `prohibited` from journal `Market.json`. Capability dropped; finding to be recorded in the audit report

## 2. Constants

- [x] 2.1 Add schema-ref constants for `scanbarycentre/1`, `fssbodysignals/1`, `dockinggranted/1`, `dockingdenied/1` in `src/modules/constants.py`
- [x] 2.2 Add `ScanBaryCentre`, `FSSBodySignals`, `DockingGranted`, `DockingDenied` to `REPORTABLE_EVENTS`
- [x] 2.3 Add the four events to `DEDICATED_SCHEMA_EVENTS` with their schema name and schema_ref

## 3. Validation

- [x] 3.1 Add `REQUIRED_FIELDS` entries: `ScanBaryCentre` (`timestamp, SystemAddress, BodyID`), `FSSBodySignals` (`timestamp, BodyName, BodyID, SystemAddress, Signals`), `DockingGranted` (`timestamp, MarketID, StationName`), `DockingDenied` (`timestamp, MarketID, StationName, Reason`)
- [x] 3.2 Write tests asserting each event is rejected when a required field is missing

## 4. Transforms

- [x] 4.1 Add `transform_scan_bary_centre` (strip disallowed/`_Localised`, SystemAddress-gated `StarPos`/`StarSystem` augmentation, add `horizons`/`odyssey`)
- [x] 4.2 Add `transform_fss_body_signals` (augment `StarSystem`/`StarPos`; verify nested `_Localised` stripping inside `Signals[]`; add flags)
- [x] 4.3 Add `transform_docking_granted` (passthrough `LandingPad`, `MarketID`, `StationName`, `StationType`; flags only; no StarPos)
- [x] 4.4 Add `transform_docking_denied` (passthrough `Reason`, `MarketID`, `StationName`, `StationType`; strip `Reason_Localised`; flags only; no StarPos)
- [x] 4.5 Write transform tests for each: correct `$schemaRef`, required payload fields present, augmentation behavior, `_Localised` stripping

## 5. Watcher dispatch

- [x] 5.1 Add the four new events to the `_process_dedicated_schema_event` dispatch dict in `src/modules/watcher.py`
- [x] 5.2 Add/extend a watcher-level test confirming the four events route to the dedicated path and submit

## 6. Documentation

- [x] 6.1 README: add the missing `FCMaterials`/fcmaterials_journal/1 row and the four new dedicated-schema rows
- [x] 6.2 Create `reports/eddn-coverage-audit.md` — a coverage matrix of all 18 live EDDN schemas (status, source event, schema version, applicability), including the black-market/prohibited finding
- [x] 6.3 Add an entry under `[Unreleased]` in `CHANGELOG.md`
- [x] 6.4 Update `AGENTS.md` if any documented conventions changed (expected: no change)

## 7. Verification

- [x] 7.1 Run the full Python test suite — all tests must pass
- [x] 7.2 Run `npm run lint:py` and `npm run lint:ts` clean
- [x] 7.3 Verify each new transform's output against the corresponding EDDN schema README one final time
