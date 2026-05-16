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

## Phase 3: Fix EDDN Schema Mismatches (2026-05-10)

Root cause: Multiple events sent to journal/1 but EDDN rejects them — they belong to dedicated schemas.
Live Decky log: `EDDN client error 400: 'FSSSignalDiscovered' is not one of ['Docked', 'FSDJump', 'Scan', 'Location', 'SAASignalsFound', 'CarrierJump', 'CodexEntry']`

### Changes applied:
- **New module**: `signal_batcher.py` — batches FSSSignalDiscovered events, flushes on trigger events
- **constants.py**: Added 5 dedicated schema refs (fsssignaldiscovered/1, fssdiscoveryscan/1, navroute/1, approachsettlement/1, codexentry/1); added DEDICATED_SCHEMA_EVENTS, JOURNAL_1_ONLY_DISALLOWED, FSS_SIGNAL_DISALLOWED_FIELDS; removed ApproachBody/LeaveBody/SAAScanComplete from REPORTABLE_EVENTS; added SAASignalsFound/CodexEntry; changed NavRoute schema to "navroute"; removed Latitude/Longitude from EDDN_DISALLOWED_FIELDS
- **validator.py**: Added 5 new transform methods (fss_signal_discovered, fss_discovery_scan, navroute, approach_settlement, codex_entry); updated _strip_disallowed() with keep_fields; added JOURNAL_1_ONLY_DISALLOWED stripping in journal/1 transform; ApproachSettlement StationName→Name dual acceptance; FSSDiscoveryScan SystemName→StarSystem rename
- **watcher.py**: New routing in _process_reportable_event: FSSSignalDiscovered→batcher, flush triggers, dedicated schema dispatch, auxiliary events, journal/1 fallback
- **main.py**: Import SignalBatcher, pass to JournalWatcher constructor

### Reviewer feedback applied:
- Added tests for SystemName→StarSystem rename in FSSDiscoveryScan (both branches)
- Added test for StationName+Name both present in ApproachSettlement
- Removed dead code: is_system_change() and clear() from SignalBatcher (flush handles system changes correctly)
- Fixed broken flush() method (missing return result)
- Updated README.md: new EDDN schema tables, events not sent section, updated Known Limitations
- Updated AGENTS.md: test count 330, signal_batcher in module list

### Phase 4: Fix Commodity Name Sanitization (2026-05-13)

Root cause: The plugin was sending raw journal commodity names (e.g., `$platinum_name;`) to EDDN instead of the clean format EDDN expects (e.g., `platinum`). ED Market Connector correctly strips the `$` prefix and `_name;` suffix.

### Changes applied:
- **validator.py**: Added `_sanitize_commodity_name()` function that strips `$` prefix and `_name;`/`;` suffix from commodity names; updated `transform_commodity()` to sanitize the `Name` field; added `statusFlags` passthrough from Market.json `StatusFlags`
- **tests/fixtures/Market.json**: Updated to use realistic journal-format names (`$hydrogenfuel_name;`, `$drones_name;`), added gold item with `StatusFlags: ["powerplay"]`
- **tests/test_validator.py**: Updated commodity assertions for 3 items (was 2), added gold item with statusFlags assertion, added `test_commodity_name_sanitization` unit test
- **tests/test_integration.py** & **tests/test_watcher.py**: Updated commodity count assertion from 2 to 3

### Status:
- Phase 3: ✅ Complete — 330 tests passing, all lint clean
- Phase 4: ✅ Complete — 333 tests passing, all lint clean
  - Commodity names sanitized (strip `$..._name;` format to clean EDDN names)
  - Ship names sanitized (same transformation applied to Shipyard ShipType)
  - Module names sanitized (same transformation applied to Outfitting module Name, no-op for already-clean names)
  - Added `statusFlags` passthrough for commodity items with `StatusFlags` in Market.json
  - Renamed `_sanitize_commodity_name` to `_sanitize_eddn_name` (broader scope)
  - Updated test fixtures to use realistic journal-format names
  - Added unit tests for name sanitization covering commodities, ships, modules, and edge cases
  - Added `gameversion` and `gamebuild` to EDDN message header (from Fileheader journal event)
  - Added `_submit()` helper in watcher to pass session state's game_version/game_build to submitter
  - Added tests for game version in header (present when provided, absent when empty)

### Phase 5: Fix Auxiliary File Race Condition (2026-05-13)

Root cause: Elite Dangerous writes auxiliary JSON files (Market.json, Outfitting.json, Shipyard.json, NavRoute.json) asynchronously after the corresponding journal event line appears. The watcher was trying to read these files immediately, finding they didn't exist yet, and silently discarding the event. This meant outfitting (and potentially other auxiliary) messages were never sent to EDDN.

### Changes applied:
- **watcher.py**: Changed `_read_auxiliary_data()` from sync to async; added retry logic (5 attempts × 0.5s delay) to handle the race condition where the auxiliary file isn't written yet by ED
- **watcher.py**: Upgraded log level from `debug` to `info` for the "auxiliary file still missing" message so it's visible in default logging
- **tests/test_watcher.py**: Added `test_auxiliary_file_retries_on_missing` — verifies that when the first read fails but second succeeds, the event is still submitted
- **tests/test_watcher.py**: Added `test_auxiliary_file_retries_exhausted` — verifies that when all retries fail, no submission occurs

### Status:
- Phase 5: ✅ Complete — 335 tests passing

### Phase 7: Fix Outfitting Events Not Sent (2026-05-14)

Root cause: `transform_outfitting()` in `validator.py` was reading outfitting items from the JSON key `"Modules"`, but Elite Dangerous's `Outfitting.json` file uses the key `"Items"`. This caused the module list to always be empty, making `transform_outfitting()` return `None` and silently dropping all outfitting events.

The test fixture also used `"Modules"` (matching the code's wrong assumption), so tests passed despite the bug.

### Changes applied:
- **validator.py**: Changed `outfitting_data.get("Modules", [])` → `outfitting_data.get("Items", [])` in `transform_outfitting()`
- **tests/fixtures/Outfitting.json**: Changed `"Modules"` → `"Items"` to match real game output
- **tests/test_validator.py**: Updated all inline outfitting test data from `"Modules"` → `"Items"`
- **tests/test_parser.py**: Updated assertion from `data["Modules"]` → `data["Items"]`
- 336 tests passing

### Phase 6: Fix EDDN Schema Validation Rejections (2026-05-14)

Root cause: Three EDDN schema violations causing 400 errors on the live device:
1. **FSSSignalDiscovered**: `FSS_SIGNAL_DISALLOWED_FIELDS` included `"timestamp"`, stripping it from individual signals. The fsssignaldiscovered/1 schema *requires* `timestamp` in each signal object.
2. **FSSDiscoveryScan**: `transform_fss_discovery_scan()` renamed `SystemName` → `StarSystem`, but the fssdiscoveryscan/1 schema uses `SystemName` (same as the journal). Also, the `Progress` field was not stripped despite being disallowed by the schema.
3. **NavRoute**: `transform_navroute()` augmented `StarSystem`, `StarPos`, and `SystemAddress` at message level, but the navroute/1 schema only allows `timestamp`, `event`, `Route`, `horizons`, `odyssey` at message level — those fields belong inside Route entries only.

### Changes applied:
- **constants.py**: Removed `"timestamp"` from `FSS_SIGNAL_DISALLOWED_FIELDS` (signals need it); added `"Progress"` to `EDDN_DISALLOWED_FIELDS` (it's disallowed by fssdiscoveryscan/1)
- **validator.py**:
  - `transform_fss_discovery_scan()`: Removed `SystemName` → `StarSystem` rename (fssdiscoveryscan/1 uses `SystemName`)
  - `transform_navroute()`: Removed `StarSystem`/`StarPos`/`SystemAddress` augmentation at message level; instead explicitly pops them since they're not allowed by navroute/1 schema
- **tests/test_constants.py**: Updated FSS_SIGNAL_DISALLOWED_FIELDS tests (timestamp no longer disallowed); will add Progress test
- **tests/test_validator.py**: Updated FSSDiscoveryScan tests (SystemName preserved, Progress stripped, no StarSystem); updated NavRoute test (no message-level StarSystem/StarPos/SystemAddress)
- **tests/test_signal_batcher.py**: Updated timestamp test (timestamp now preserved in signals)
- 334 tests passing

### Phase 8: Fix FSSSignalDiscovered Missing StarSystem/StarPos (2026-05-14)

Root cause: FSSSignalDiscovered journal events in Elite Dangerous **never** contain 
`StarSystem` or `StarPos` fields — they only have `SystemAddress`, `SignalName`, 
and `SignalType`. The signal batcher stored `star_system=None` and `star_pos=None` 
for these events, relying on the validator's `transform_fss_signal_discovered()` to 
augment from `session_state`. However, there were two failure scenarios:

1. **SystemAddress mismatch**: When an FSDJump triggers a batch flush, 
   `parse_line()` updates `session_state` to the **current** system (the jump 
   destination). But the accumulated signals are from the **previous** system. 
   The SystemAddress mismatch blocked augmentation, resulting in 
   `StarSystem: ""` and `StarPos: []` — which fails EDDN's fsssignaldiscovered/1 
   schema validation that requires non-empty `StarSystem` and a 3-element 
   `StarPos` array.

2. **No prior position data**: If the watcher starts fresh (no prior FSDJump/Location 
   event), `session_state` has no `star_pos`, and signals accumulated before any 
   position event would have no position data to augment from.

This caused EDDN 400 errors:
- `'timestamp' is a required property` (empty `StarPos: []` may cause structural issues)
- `'StarSystem' was unexpected` (signals sent to wrong schema due to cascading failures)
- `'SystemAddress', 'StarSystem', 'StarPos' were unexpected` (position data in non-position schemas)

### Changes applied:
- **signal_batcher.py**: 
  - `flush()` now takes optional `session_state` parameter
  - When the batch lacks `star_system` or `star_pos`, it augments from `session_state` 
    (checking SystemAddress match to prevent stale coordinates)
  - When position data can't be obtained (mismatched SystemAddress with no signal-level 
    data, or no session_state), the batch is **discarded** (returns None) — 
    it's better to drop signals than submit invalid data to EDDN
  - Added docstring explaining the position data flow
- **watcher.py**: Updated `_process_reportable_event()` to pass `session_state` to 
  `signal_batcher.flush()`
- **validator.py**: Simplified `transform_fss_signal_discovered()` — since the batcher 
  now handles augmentation and validation, the transform simply uses the batch's 
  `star_system` and `star_pos` directly, falling back to `""` and `[]` only if the 
  batch somehow has no data (which shouldn't happen since flush() returns None for 
  empty batches)
- **tests/test_signal_batcher.py**: Comprehensive rewrite to test:
  - Augmentation from session_state when signals lack position data
  - SystemAddress matching for safe augmentation
  - Batch discarding when position data can't be determined
  - Preservation of signal-level position data even with mismatched SystemAddress
  - Batch discarding when no session_state and no signal position data
- 343 tests passing, lint clean

### Phase 8b: Fix Missing gameversion/gamebuild in Header (2026-05-14)

Root cause: On first run (no `last_active`), the `_initial_scan` method only processed **today's** journal files via `_is_from_today()`. If ED was started on a previous day and still running, the current journal file would be from **yesterday** — and `_is_from_today()` would skip it. Since the `Fileheader` event (which sets `game_version`/`game_build` in session state) is always the first line of a journal file, skipping it meant these values stayed empty, causing `gameversion` and `gamebuild` to be omitted from all EDDN message headers.

### Changes applied:
- **watcher.py**: Changed `_initial_scan()` first-run logic to process **only the most recent journal file** instead of only today's files. This ensures the `Fileheader` is always parsed, setting `game_version`/`game_build`/`commander`/`horizons`/`odyssey` in session state. Older files are tracked for position but not processed (their events would be stale catch-up data anyway).
- **tests/test_watcher.py**: Added `TestInitialScan` test class with 4 tests:
  - `test_first_run_processes_most_recent_file`: verifies most recent file's Fileheader sets session state
  - `test_first_run_skips_older_files`: verifies older files are tracked but not processed
  - `test_catch_up_processes_modified_files`: verifies catch-up mode processes newer files
  - `test_game_version_in_submission_header`: verifies `game_version`/`game_build` are passed to submitter
- 347 tests passing, lint clean
- **Sol FSDJump mystery resolved**: The `Sol` FSDJump events seen in EDDN are NOT from this plugin — they come from other EDDN contributors with different uploaderIDs. Zero FSDJump events to Sol exist in this device's journal files.

### Phase 9: Fix Minor Code Review Issues (2026-05-16)

Root cause: Release readiness code review flagged minor improvements.

### Changes applied:
- **constants.py**: Added `SOFTWARE_NAME` and `SOFTWARE_VERSION` module-level constants
- **submitter.py**: Replaced hardcoded `"ED Journal Monitor Decky"` and `"0.1.0"` string literals with references to `constants.SOFTWARE_NAME` and `constants.SOFTWARE_VERSION`
- **m1 (softwareName constant)**: ✅ Resolved — single source of truth for plugin identity strings
- **m2 (empty py_modules/)**: ⏭ Ignored per user instruction
- **m3 (OpenSpec not archived)**: ✅ Verified already archived — `openspec/changes/archive/2026-05-16-add-diagnostic-bundle/`
- **m4 (softwareName spec discrepancy)**: ⏭ Accepting human-readable name for now
- **m5 (package.json version)**: ⏭ 0.1.0 is acceptable for first release
- 385 tests passing, lint clean

## Documentation Review (2026-05-10)
- Reviewed README.md and AGENTS.md for accuracy against codebase
- **README.md fixes**: Added NavRoute to auxiliary table, added missing architecture diagram nodes (Activity log, Diagnostics, Constants), added directional arrows (callable vs decky.emit), added full Configuration section (enabled, detailed_logging, uploader_id auto-detection, poll_interval, all settings table), added EDDN upload endpoint, added UI Panel description, added Event Flow walkthrough, added Emitted Events table, added Troubleshooting section (SSL certs, journal path, EDDN failures, ED detection, system resume), added Known Limitations section, added Diagnostic Bundle contents table, softened "no manual setup required" to "for Steam installs", added Proton username note, aligned test command with package.json
- **AGENTS.md fixes**: Added RegisterForOnResumeFromSuspend and check_ed_running to architecture description, added full callable methods list, added emitted events list, added constants.py to module list, added api.ts and types.d.ts to key files, updated Content.tsx description to include all 5 panel sections, aligned test command
