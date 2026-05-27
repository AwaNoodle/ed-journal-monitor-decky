## 1. Constants

- [x] 1.1 Add `EDDN_FSSALLBODIESFOUND_1_SCHEMA_REF` constant pointing to `https://eddn.edcd.io/schemas/fssallbodiesfound/1`
- [x] 1.2 Add `FSSAllBodiesFound` to `REPORTABLE_EVENTS` set
- [x] 1.3 Add `FSSAllBodiesFound` entry to `DEDICATED_SCHEMA_EVENTS` dict with schema name `fssallbodiesfound` and the new schema ref

## 2. Validator

- [x] 2.1 Add `FSSAllBodiesFound` entry to `REQUIRED_FIELDS` with required fields: `timestamp`, `SystemName`, `SystemAddress`, `Count`
- [x] 2.2 Implement `transform_fss_all_bodies_found()` method: strip disallowed fields, augment StarPos/StarSystem from session state with SystemAddress cross-check, inject horizons/odyssey flags, wrap in EDDN message structure

## 3. Watcher

- [x] 3.1 Add `FSSAllBodiesFound` to `transform_dispatch` dict in `_process_dedicated_schema_event`, mapping to `self.validator.transform_fss_all_bodies_found`

## 4. Tests

- [x] 4.1 Add validation tests: valid event, missing required fields, StarPos augmentation failure, SystemAddress mismatch
- [x] 4.2 Add transform tests: successful transform with all fields, StarPos augmentation from session state, Count passthrough, horizons/odyssey injection

## 5. Documentation

- [x] 5.1 Add `FSSAllBodiesFound` to the "Dedicated Schema Events" table in README.md with schema link and notes
- [x] 5.2 Update CHANGELOG.md with an entry under `[Unreleased]`

## 6. Verify

- [x] 6.1 Run full test suite — all tests pass
- [x] 6.2 Run lint/typecheck — no errors
