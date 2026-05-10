# Plan: Phase 1 & 2 — EDDN Market/Outfitting/Shipyard + Expanded Journal Events

## Goal
Extend the ED Journal Monitor Decky plugin to send the same EDDN data that EDMC does (commodity prices, outfitting, shipyard, plus additional journal events), making it a functional replacement for EDMC on Steam Deck.

## Status (2026-05-10)
- Phase 1 implemented: Market/Outfitting/Shipyard auxiliary files are transformed and submitted to commodity/3, outfitting/2, shipyard/2.
- Phase 2 implemented: Additional journal/1 events are reportable and validated, with NavRoute sourced from `NavRoute.json`.
- Test coverage added for constants, parser auxiliary parsing, validator transforms/validation, watcher auxiliary handling, and integration flow.

## Phase 1: Commodity/Outfitting/Shipyard EDDN Schemas

### 1.1 Refactor validator to support multiple schemas
- **Current**: `EDDNValidator` hardcodes `journal/1` schema in `transform()`
- **Change**: Split validation from schema-specific transformation. Add `transform_commodity()`, `transform_outfitting()`, `transform_shipyard()` methods, each producing the correct `$schemaRef` and message payload.
- **File**: `src/modules/validator.py`
  - Keep existing `validate()` / `transform()` for journal/1 (backward compatible)
  - Add `validate_auxiliary(event_type) -> bool` to check Market/Outfitting/Shipyard triggers
  - Add `transform_commodity(market_data, session_state) -> dict` → commodity/3 schema
  - Add `transform_outfitting(outfitting_data, session_state) -> dict` → outfitting/2 schema
  - Add `transform_shipyard(shipyard_data, session_state) -> dict` → shipyard/2 schema

### 1.2 Add auxiliary file reader to parser
- **Current**: `JournalParser` only parses journal lines via `parse_line()`
- **Change**: Add `parse_auxiliary_file(filepath) -> dict | None` to read standalone JSON files (Market.json, Outfitting.json, Shipyard.json)
- **File**: `src/modules/parser.py`
  - Add `parse_auxiliary_file(filepath: str) -> dict | None`
  - Returns parsed JSON dict or None on failure

### 1.3 Add auxiliary file handling to watcher
- **Current**: `JournalWatcher` only globs `Journal*.log` and processes line-by-line
- **Change**: When Market/Outfitting/Shipyard journal event is detected, read the corresponding `.json` file and submit via the appropriate schema
- **File**: `src/modules/watcher.py`
  - In `_process_reportable_event()` or a new handler: detect Market/Outfitting/Shipyard events
  - Read the auxiliary JSON file from `self._journal_path`
  - Call the appropriate validator transform method
  - Submit the resulting message
  - Add mapping: `Market` → `Market.json`, `Outfitting` → `Outfitting.json`, `Shipyard` → `Shipyard.json`

### 1.4 Expand constants
- **File**: `src/modules/constants.py`
  - Add Market, Outfitting, Shipyard to `REPORTABLE_EVENTS`
  - Add auxiliary file name mapping: `AUXILIARY_FILES = {"Market": "Market.json", "Outfitting": "Outfitting.json", "Shipyard": "Shipyard.json"}`
  - Add EDDN schema ref constants for commodity/3, outfitting/2, shipyard/2
  - Add commodity-specific disallowed fields (if any)

### 1.5 EDDN schema details (from research)
- **commodity/3**: Requires `systemName`, `stationName`, `marketId`, `commodities[]` (each with `name`, `meanPrice`, `buyPrice`, `stock`, `stockBracket`, `sellPrice`, `demand`, `demandBracket`), `horizons`, `odyssey`. Items with `stockBracket==0` and `demandBracket==0` should be excluded (per EDDN spec).
- **outfitting/2**: Requires `systemName`, `stationName`, `marketId`, `modules[]` (each with `name`), `horizons`, `odyssey`
- **shipyard/2**: Requires `systemName`, `stationName`, `marketId`, `ships[]` (each with `shipType`), `horizons`, `odyssey`
- All use the same EDDN upload endpoint

## Phase 2: Expand Journal/1 Event Coverage

### 2.1 Add additional reportable events
- **Current**: FSDJump, Scan, Location, Docked, FSSDiscoveryScan
- **Add**: NavRoute, ApproachBody, LeaveBody, ApproachSettlement, CarrierJump, FSSSignalDiscovered, SAAScanComplete
- **File**: `src/modules/constants.py` — expand `REPORTABLE_EVENTS`
- **File**: `src/modules/validator.py` — add `REQUIRED_FIELDS` entries for new events

### 2.2 Required fields for new events (from EDDN journal/1 spec)
- `NavRoute`: timestamp, event (already has Routes[] with SystemAddress)
- `ApproachBody`: timestamp, StarSystem, SystemAddress, BodyName
- `LeaveBody`: timestamp, StarSystem, SystemAddress, BodyName
- `ApproachSettlement`: timestamp, StarSystem, SystemAddress, StationName
- `CarrierJump`: timestamp, StarSystem, SystemAddress, StarPos
- `FSSSignalDiscovered`: timestamp, SystemAddress, SignalName
- `SAAScanComplete`: timestamp, BodyName, SystemAddress

### 2.3 NavRoute.json auxiliary file
- NavRoute journal event triggers reading `NavRoute.json` for the full route data
- Similar pattern to Market.json — the journal event is a pointer, full data in the JSON file
- Add to `AUXILIARY_FILES` mapping and watcher handling

## Test-First Implementation Order

### Tests to write FIRST (before any implementation changes)

1. **test_validator.py** — New test classes:
   - `TestValidateAuxiliary` — validate_auxiliary() for Market, Outfitting, Shipyard
   - `TestTransformCommodity` — commodity/3 message construction from Market.json data
   - `TestTransformOutfitting` — outfitting/2 message construction from Outfitting.json data
   - `TestTransformShipyard` — shipyard/2 message construction from Shipyard.json data
   - `TestValidateNewJournalEvents` — validate() for NavRoute, ApproachBody, etc.
   - `TestTransformNewJournalEvents` — transform() for new journal/1 events

2. **test_parser.py** — New test class:
   - `TestParseAuxiliaryFile` — parse_auxiliary_file() for Market.json, Outfitting.json, Shipyard.json, NavRoute.json

3. **test_watcher.py** — New tests:
   - `TestAuxiliaryFileHandling` — Market event triggers Market.json read + commodity/3 submission
   - `TestOutfittingFileHandling` — same pattern
   - `TestShipyardFileHandling` — same pattern
   - `TestNavRouteFileHandling` — NavRoute event triggers NavRoute.json read + journal/1 submission

4. **test_integration.py** — New integration tests:
   - Market data end-to-end pipeline
   - Outfitting data end-to-end pipeline
   - Shipyard data end-to-end pipeline
   - NavRoute data end-to-end pipeline

5. **test_constants.py** — New file:
   - Verify REPORTABLE_EVENTS includes all expected events
   - Verify AUXILIARY_FILES mapping is correct
   - Verify schema ref constants

6. **Fixtures** — Add test fixture files:
   - `Market.json` — realistic commodity data
   - `Outfitting.json` — realistic module data
   - `Shipyard.json` — realistic ship data
   - `NavRoute.json` — realistic route data
   - Journal lines with Market, Outfitting, Shipyard, NavRoute events

### Implementation order (after tests)
1. `constants.py` — Add new events, mappings, schema refs
2. `parser.py` — Add `parse_auxiliary_file()`
3. `validator.py` — Add auxiliary transforms + new journal event required fields
4. `watcher.py` — Add auxiliary file handling + new event processing
5. Run all tests — must pass

## Acceptance Criteria
- All existing tests continue to pass (backward compatible) — now 171 total
- All new tests pass
- commodity/3, outfitting/2, shipyard/2 schemas are correctly constructed
- Market/Outfitting/Shipyard journal events trigger auxiliary file reads
- NavRoute journal event triggers NavRoute.json read
- New journal/1 events (ApproachBody, LeaveBody, etc.) are validated and submitted
- ~~No changes to submitter.py~~ — submitter.py was modified to add:
  - `_build_ssl_context()` (SSL cert fix for Decky's PyInstaller Python) — pre-existing on-device requirement
  - `event_name` parameter on `submit()` — fixes "unknown" event name in activity log for auxiliary schemas
  - HTTP error body logging improvement
- No changes to frontend (this is backend-only for now)

## Implementation Status (2026-05-10)
- Phase 1: ✅ Complete — commodity/3, outfitting/2, shipyard/2 schemas
- Phase 2: ✅ Complete — 7 new journal/1 events + NavRoute.json auxiliary
- Reviewer feedback (round 1) applied:
  - Fixed event_name="unknown" bug for auxiliary schema submissions
  - Added missing watcher test for Market event with no Market.json
  - Added test for event_name override in submitter
  - Updated AGENTS.md test count
  - Added noqa comment for ruff PLC0415 in submitter.py
  - All integration test mock functions updated for event_name kwarg
- Adversarial review feedback (round 2) applied:
  - **Fixed missing `timestamp` in all 3 auxiliary transforms** (EDDN required field)
  - **Fixed outfitting/2 `modules` to be array of strings** (not objects)
  - **Fixed shipyard/2 `ships` to be array of strings** (not objects)
  - **Guard against empty arrays**: transforms return None when no items remain, watcher skips submission
  - **Consolidated `AUXILIARY_FILES`** into structured dict with `filename`+`schema` keys; derived `AUXILIARY_SCHEMA_EVENTS` from it (single source of truth)
  - **Extracted `MockSettings` to `conftest.py`** (was duplicated in 7 test files)
  - **Extracted `copy_fixture`/`load_fixture` to `conftest.py`** (was duplicated in 3 test files)
  - **Inlined `validate_auxiliary()`** — was a one-liner set membership check
  - **Added edge-case tests**: empty commodities/modules/ships, invalid JSON through watcher, Docked not triggering auxiliary, NavRoute empty route, `_as_dict_list` unit tests, commodity[1] content verification
  - 182 tests passing, all lint clean
