# Implementation Report: Phase 1 + Phase 2 Expansion

## Summary
Implemented Phase 1 and Phase 2 backend expansion for ED Journal Monitor Decky plugin, following the requested test-first order:

1. Added fixtures in `tests/fixtures/`
2. Added/extended tests across constants/parser/validator/watcher/integration
3. Implemented backend code changes in constants/parser/validator/watcher

No frontend files were modified for this task.

## What was implemented

### Phase 1 (commodity/3, outfitting/2, shipyard/2)
- Added EDDN schema constants:
  - `EDDN_COMMODITY_3_SCHEMA_REF`
  - `EDDN_OUTFITTING_2_SCHEMA_REF`
  - `EDDN_SHIPYARD_2_SCHEMA_REF`
- Added `AUXILIARY_FILES` mapping:
  - `Market -> Market.json`
  - `Outfitting -> Outfitting.json`
  - `Shipyard -> Shipyard.json`
  - `NavRoute -> NavRoute.json`
- Added `JournalParser.parse_auxiliary_file(filepath)` for auxiliary JSON parsing.
- Added validator methods:
  - `validate_auxiliary(event_type)`
  - `transform_commodity(market_data, session_state)`
  - `transform_outfitting(outfitting_data, session_state)`
  - `transform_shipyard(shipyard_data, session_state)`
- Commodity transform behavior:
  - Builds commodity/3 payload fields per plan
  - Excludes items where `StockBracket == 0` and `DemandBracket == 0`
  - `_Localised` fields are naturally excluded by selective field mapping
- Watcher now reads auxiliary files on trigger events and submits the correct schema message.

### Phase 2 (expanded journal/1 events + NavRoute auxiliary)
- Added reportable events:
  - `NavRoute`, `ApproachBody`, `LeaveBody`, `ApproachSettlement`, `CarrierJump`, `FSSSignalDiscovered`, `SAAScanComplete`
- Added `REQUIRED_FIELDS` entries for all new journal/1 events.
- Added NavRoute validation detail: `Route` must be a non-empty list and each route entry must include `SystemAddress`.
- Watcher behavior for `NavRoute`:
  - Reads `NavRoute.json`
  - Replaces pointer line payload with auxiliary payload
  - Validates and submits under `journal/1`

## Tests added/updated

### New fixtures
- `tests/fixtures/Market.json`
- `tests/fixtures/Outfitting.json`
- `tests/fixtures/Shipyard.json`
- `tests/fixtures/NavRoute.json`

### New/updated test files
- Added: `tests/test_constants.py`
- Updated: `tests/test_parser.py`
- Updated: `tests/test_validator.py`
- Updated: `tests/test_watcher.py`
- Updated: `tests/test_integration.py`

## Backend files changed
- `src/modules/constants.py`
- `src/modules/parser.py`
- `src/modules/validator.py`
- `src/modules/watcher.py`

## Documentation/plan updates
- Updated `README.md` EDDN coverage to reflect implemented schemas/events.
- Updated `plans/plan.md` with implementation status (2026-05-10).

## Validation
- Test-first check (before implementation): new tests failed at collection due missing constants/methods (expected).
- After implementation:
  - `PYTHONPATH=. python3 -m pytest tests/ -q` → **166 passed**
  - `npm run lint:ts` → passed
  - `.venv/bin/ruff check` on all changed backend/test files → passed

## Notes / constraints
- `submitter.py` was intentionally not modified per task constraint.
- Full `npm run lint:py` reports one pre-existing ruff issue in `src/modules/submitter.py` (`PLC0415`, local `import certifi` inside fallback logic). This file is out-of-scope for this task and restricted by the explicit no-modification constraint.
