# Test Creation Report — EDDN Schema Fix

## Summary
All test files have been created/updated for the EDDN schema fix plan. Tests are written **before** implementation — they are expected to FAIL against the current codebase since the source modules haven't been modified yet.

## Files Changed

### 1. `tests/test_signal_batcher.py` (NEW — 33 tests)
Created from scratch. Tests the new `SignalBatcher` module:
- **TestAddSignal** (18 tests): accumulation, field stripping (TimeRemaining, event, timestamp, _Localised keys), field preservation (SignalName, IsStation, USSType, SpawningState, SpawningFaction, ThreatLevel, SignalType, SpawningPower, OpposingPower), stripping of message-level fields from individual signals (StarPos, StarSystem, SystemAddress)
- **TestMetadata** (5 tests): last_timestamp, system_address, star_system, star_pos tracking, metadata updates with latest signal
- **TestFlush** (4 tests): empty returns None, returns batch data, clears internal state, allows new signals after flush
- **TestShouldFlush** (2 parametrized tests): True for 7 trigger events (FSSDiscoveryScan, SupercruiseEntry, Location, FSDJump, CarrierJump, Shutdown, Music), False for 8 non-trigger events
- **TestIsSystemChange** (2 parametrized tests): True for FSDJump/Location/CarrierJump, False for others
- **TestClear** (2 tests): discards signals, allows new signals after clear

### 2. `tests/test_constants.py` (ALREADY UPDATED — 42 tests)
Was previously updated with tests for:
- New schema ref constants (fsssignaldiscovered/1, fssdiscoveryscan/1, navroute/1, approachsettlement/1, codexentry/1)
- Removed events (ApproachBody, LeaveBody, SAAScanComplete) NOT in REPORTABLE_EVENTS
- Added events (SAASignalsFound, CodexEntry) IN REPORTABLE_EVENTS
- Latitude/Longitude removed from EDDN_DISALLOWED_FIELDS
- JOURNAL_1_ONLY_DISALLOWED (6 fields)
- FSS_SIGNAL_DISALLOWED_FIELDS (3 fields)
- DEDICATED_SCHEMA_EVENTS (4 entries)
- NavRoute schema changed to "navroute"

### 3. `tests/test_validator.py` (ALREADY UPDATED — 80 tests)
Was previously updated with tests for:
- Removed ApproachBody/LeaveBody/SAAScanComplete from parametrized tests
- Added SAASignalsFound, CodexEntry validation tests
- ApproachSettlement REQUIRED_FIELDS with Name (not StationName)
- FSSDiscoveryScan REQUIRED_FIELDS with BodyCount, NonBodyCount
- **TestTransformFSSSignalDiscovered** (7 tests): valid batch, empty returns None, schema ref, signal field preservation, StarPos augmentation, message-level fields, _Localised stripping in signals
- **TestTransformFSSDiscoveryScan** (4 tests): valid event, schema ref, StarPos augmentation, disallowed field stripping
- **TestTransformNavRoute** (4 tests): valid data, schema ref, StarPos augmentation at message level, _Localised stripping in Route entries
- **TestTransformApproachSettlement** (6 tests): Latitude/Longitude preservation, StationName→Name rename, schema ref, StarPos augmentation, other disallowed field stripping, _Localised stripping
- **TestTransformCodexEntry** (7 tests): valid event, schema ref, VoucherAmount/Traits/IsNewEntry/NewTraitsDiscovered preservation, StarPos augmentation, _Localised stripping
- Journal/1 Latitude/Longitude/VoucherAmount/Traits stripping tests
- Factions MyReputation stripping test

### 4. `tests/test_watcher.py` (UPDATED — 26 tests, +9 new)
Updated fixture to include SignalBatcher, updated imports, and added:
- **TestDedicatedSchemaRouting** (9 new tests):
  - `test_fss_signal_discovered_routes_to_batcher` — verifies batching not immediate submit
  - `test_fss_discovery_scan_triggers_flush_and_uses_dedicated_schema` — batch flush + fssdiscoveryscan/1
  - `test_approach_settlement_uses_dedicated_schema` — approachsettlement/1
  - `test_codex_entry_uses_dedicated_schema` — codexentry/1
  - `test_saa_signals_found_routes_through_journal1` — SAASignalsFound uses journal/1
  - `test_approach_body_not_reportable` — ApproachBody ignored
  - `test_leave_body_not_reportable` — LeaveBody ignored
  - `test_saa_scan_complete_not_reportable` — SAAScanComplete ignored
  - `test_fsdjump_triggers_signal_batch_flush` — FSDJump flushes batcher
- Updated `test_navroute_event_uses_navroute_json` — now expects navroute/1 schema (was journal/1)

### 5. `tests/test_parser.py` (UPDATED — 23 tests, +1 new)
- Removed ApproachBody, LeaveBody, SAAScanComplete from reportable list
- Added SAASignalsFound, CodexEntry to reportable list
- Added `test_removed_events_not_reportable` — verifies ApproachBody/LeaveBody/SAAScanComplete are not reportable

## Current Test Status

| File | Status | Reason |
|------|--------|--------|
| test_signal_batcher.py | ❌ Collection errors | `signal_batcher` module doesn't exist yet |
| test_constants.py | ❌ Import errors | New constants not defined yet |
| test_validator.py | ❌ Import errors | New schema ref constants not defined yet |
| test_watcher.py | ❌ Import errors | New schema ref constants not defined yet |
| test_parser.py | ❌ 2 test failures | REPORTABLE_EVENTS not updated yet |
| test_submitter.py | ✅ 14 passing | Unaffected |
| test_activity_log.py | ✅ 11 passing | Unaffected |
| test_diagnostics.py | ✅ 18 passing | Unaffected |

This is the expected "tests-first" state. All failures are due to missing source code that will be implemented next.

## Test Count Summary
- **Before**: 205 tests
- **After implementation**: ~204 tests (net change from removed parametrized cases + new tests)
  - test_constants.py: +42 tests (was ~15)
  - test_signal_batcher.py: +33 tests (new file)
  - test_validator.py: +80 tests (was ~40)
  - test_watcher.py: +26 tests (was ~17)
  - test_parser.py: +23 tests (was ~22)
