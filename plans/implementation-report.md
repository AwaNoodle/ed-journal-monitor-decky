# Implementation Report: EDDN Schema Fix

## Summary
Implemented the EDDN schema fix to route events to their correct EDDN schemas instead of sending everything to journal/1.

## Changed Files

### Source Code
| File | Changes |
|------|---------|
| `src/modules/constants.py` | Added 5 new schema refs, DEDICATED_SCHEMA_EVENTS, JOURNAL_1_ONLY_DISALLOWED, FSS_SIGNAL_DISALLOWED_FIELDS; removed ApproachBody/LeaveBody/SAAScanComplete from REPORTABLE_EVENTS; added SAASignalsFound/CodexEntry; changed NavRoute schema to "navroute"; removed Latitude/Longitude from EDDN_DISALLOWED_FIELDS |
| `src/modules/signal_batcher.py` | **NEW** — SignalBatcher class for batching FSSSignalDiscovered events with flush triggers |
| `src/modules/validator.py` | Added 5 new transform methods (fss_signal_discovered, fss_discovery_scan, navroute, approach_settlement, codex_entry); updated _strip_disallowed() with keep_fields; added JOURNAL_1_ONLY_DISALLOWED stripping in journal/1 transform; added ApproachSettlement StationName/Name dual acceptance; added SystemName→StarSystem rename for FSSDiscoveryScan |
| `src/modules/watcher.py` | New routing in _process_reportable_event: FSSSignalDiscovered→batcher, flush triggers, dedicated schema dispatch, auxiliary events, journal/1 fallback; added _process_dedicated_schema_event and _process_auxiliary_event methods; integrated SignalBatcher |
| `main.py` | Import SignalBatcher, pass to JournalWatcher constructor |

### Test Files
| File | Changes |
|------|---------|
| `tests/test_constants.py` | Added tests for new constants, schema refs, DEDICATED_SCHEMA_EVENTS, JOURNAL_1_ONLY_DISALLOWED, FSS_SIGNAL_DISALLOWED_FIELDS |
| `tests/test_signal_batcher.py` | **NEW** — 36 tests for SignalBatcher (add_signal, flush, should_flush, is_system_change, clear, metadata tracking, field stripping) |
| `tests/test_validator.py` | Added tests for 5 new transform methods, SAASignalsFound validation, ApproachSettlement dual validation, JOURNAL_1_ONLY_DISALLOWED stripping, CodexEntry field preservation; fixed _make_batch helper (signals=[] falsy bug) |
| `tests/test_watcher.py` | Added TestDedicatedSchemaRouting (9 tests: signal batching, flush triggers, dedicated schema routing, removed event rejection); fixed EDDNSubmitter import typo |
| `tests/test_parser.py` | Updated reportable events (added SAASignalsFound/CodexEntry, removed ApproachBody/LeaveBody/SAAScanComplete) |
| `tests/test_integration.py` | Updated NavRoute test to expect navroute/1 schema; updated FSSDiscoveryScan integration to expect fssdiscoveryscan/1 schema |

## Verification
- **338 tests passing** (up from 205 before the schema fix work)
- **Ruff lint**: All checks passed
- **TypeScript lint**: All checks passed

## Key Implementation Decisions

1. **ApproachSettlement validation**: Accepts either `StationName` (from journal) or `Name` (already renamed) for validation. The transform renames `StationName→Name`.

2. **FSSDiscoveryScan SystemName→StarSystem**: The journal uses `SystemName` but EDDN fssdiscoveryscan/1 uses `StarSystem`. The transform renames this field.

3. **Latitude/Longitude handling**: Removed from global `EDDN_DISALLOWED_FIELDS`, added to `JOURNAL_1_ONLY_DISALLOWED`. Journal/1 transform strips them; approachsettlement/1 transform preserves them via `keep_fields`.

4. **CodexEntry field preservation**: VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered are disallowed in journal/1 but valid in codexentry/1. The codexentry/1 transform preserves them via `keep_fields`.

5. **_strip_disallowed() keep_fields**: Added optional `keep_fields` parameter to selectively preserve fields that would otherwise be stripped. Used for approachsettlement/1 (Latitude/Longitude) and codexentry/1 (VoucherAmount/Traits/IsNewEntry/NewTraitsDiscovered).

6. **Watcher routing refactor**: Extracted `_process_dedicated_schema_event()` and `_process_auxiliary_event()` from the main `_process_reportable_event()` to reduce branch count and improve readability.

## Open Risks
- Signal batcher is in-memory only; signals accumulated before a plugin crash/reload are lost
- No explicit test for `SystemName→StarSystem` rename in FSSDiscoveryScan transform (covered by integration test with fixture but not unit-tested)
- The `AuxiliarySchemaType` Literal still includes "journal" but no AUXILIARY_FILES entries use it anymore

## Recommended Next Step
- Run reviewers on the implementation
- Update README.md and AGENTS.md with new EDDN schema coverage tables
- Test on live Steam Deck with ED running to verify EDDN submissions succeed
