# Test Coverage Review: EDDN Schema Fix

**Reviewed files:** test_constants.py, test_signal_batcher.py, test_validator.py, test_watcher.py, test_parser.py, conftest.py + source modules (constants.py, signal_batcher.py, validator.py, watcher.py)  
**Test run:** 232 passed, 0 failed

---

## 1. Are all new constants tested?

**Verdict: ✅ Well covered.**

| Constant | Tested? | Notes |
|---|---|---|
| All 9 `EDDN_*_SCHEMA_REF` values | ✅ | `TestSchemaReferences` class, one test per ref |
| `DEDICATED_SCHEMA_EVENTS` | ✅ | `TestDedicatedSchemaEvents` — membership, schema name, schema_ref, cardinality (==4) |
| `JOURNAL_1_ONLY_DISALLOWED` | ✅ | `TestDisallowedFields` — each of 6 members tested individually + complete-set assertion |
| `FSS_SIGNAL_DISALLOWED_FIELDS` | ✅ | `TestFssSignalDisallowedFields` — each member + complete set |
| `EDDN_DISALLOWED_FIELDS` (modified) | ✅ | Confirms Latitude/Longitude removed, core fields still present |
| `REPORTABLE_EVENTS` (modified) | ✅ | Includes dedicated schema events, excludes removed events |
| `AUXILIARY_SCHEMA_EVENTS` | ✅ | Confirms NavRoute now in auxiliary set |

---

## 2. Are all transform methods adequately tested?

**Verdict: ✅ Good coverage, with one gap noted.**

| Method | Test class | Coverage |
|---|---|---|
| `transform()` (journal/1) | `TestTransform` | ✅ Disallowed stripping, _Localised stripping (top-level, nested, arrays), Factions-specific, StarPos augmentation, horizons/odyssey, JOURNAL_1_ONLY_DISALLOWED (Lat/Lon, VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered) |
| `transform_fss_signal_discovered()` | `TestTransformFSSSignalDiscovered` | ✅ Batch structure, schema ref, signal preservation, _Localised stripping, message-level fields, StarPos augmentation |
| `transform_fss_discovery_scan()` | `TestTransformFSSDiscoveryScan` | ✅ Valid event, schema ref, StarPos augmentation, disallowed stripping |
| `transform_approach_settlement()` | `TestTransformApproachSettlement` | ✅ Lat/Lon preserved, StationName→Name rename, schema ref, StarPos augmentation, disallowed stripping, _Localised stripping |
| `transform_codex_entry()` | `TestTransformCodexEntry` | ✅ Valid event, schema ref, preserves VoucherAmount/Traits/IsNewEntry/NewTraitsDiscovered, StarPos augmentation, _Localised stripping |
| `transform_navroute()` | `TestTransformNavRoute` | ✅ Valid data, schema ref, StarSystem/StarPos augmentation, _Localised stripping in Route |
| `transform_commodity()` | `TestTransformCommodity` | ✅ Full fixture, empty/no-items/missing-fields → None |
| `transform_outfitting()` | `TestTransformOutfitting` | ✅ Full fixture, empty/missing → None |
| `transform_shipyard()` | `TestTransformShipyard` | ✅ Full fixture, empty/missing → None |

**Gap noted (see §6 below):** No test for `SystemName→StarSystem` rename in `transform_fss_discovery_scan`. All existing tests supply `StarSystem` directly in raw events rather than `SystemName` (which is what the ED journal actually produces).

---

## 3. Is the signal batcher thoroughly tested?

**Verdict: ✅ Thorough at unit level. One architectural concern (see below).**

| Area | Tested? | Details |
|---|---|---|
| Signal accumulation | ✅ | Single and multiple signals |
| Field stripping | ✅ | TimeRemaining, event, timestamp, _Localised, StarPos, StarSystem, SystemAddress stripped from individual signals |
| Signal field preservation | ✅ | SignalName, IsStation, USSType, SpawningState, SpawningFaction, ThreatLevel, SignalType, SpawningPower, OpposingPower |
| Metadata tracking | ✅ | last_timestamp, system_address, star_system, star_pos — including update-with-latest |
| Flush triggers | ✅ | Parametrized for 7 trigger events + 8 non-triggers |
| System change detection | ✅ | `is_system_change` for FSDJump/Location/CarrierJump |
| Empty batch | ✅ | `flush()` returns None when empty |
| Clear | ✅ | `clear()` discards signals, allows new ones after |
| State reset on flush | ✅ | Second flush returns None |

**Architectural concern:** `SignalBatcher.is_system_change()` and `clear()` are fully tested but **never called by the watcher**. The watcher only calls `should_flush()` and `flush()`. System change events (FSDJump, Location, CarrierJump) are flush triggers, so they submit the batch rather than discarding it. This is actually correct behavior (signals from the old system should be submitted before processing the jump), but `is_system_change()` and `clear()` are dead code paths that could confuse future maintainers. See Note N1.

---

## 4. Are the watcher routing tests realistic?

**Verdict: ✅ Good. Tests exercise the full watcher flow with real journal lines parsed through the parser.**

| Flow | Test | Verdict |
|---|---|---|
| Event→batcher→(no immediate submit) | `test_fss_signal_discovered_routes_to_batcher` | ✅ Verifies FSSSignalDiscovered goes to batcher, not submitter |
| FSSSignalDiscovered batch→flush→submit + FSSDiscoveryScan→dedicated→submit | `test_fss_discovery_scan_triggers_flush_and_uses_dedicated_schema` | ✅ Full flow: 2 signals batched, FSSDiscoveryScan triggers flush, verifies both schema refs and event_names |
| FSDJump→flush batch→submit + FSDJump→journal/1→submit | `test_fsdjump_triggers_signal_batch_flush` | ✅ Full flow including system change |
| ApproachSettlement→dedicated→submit | `test_approach_settlement_uses_dedicated_schema` | ✅ |
| CodexEntry→dedicated→submit | `test_codex_entry_uses_dedicated_schema` | ✅ |
| SAASignalsFound→journal/1 | `test_saa_signals_found_routes_through_journal1` | ✅ |
| Auxiliary (Market, Outfitting, Shipyard, NavRoute) | Various tests in `TestAuxiliaryFileHandling` | ✅ |

**Missing watcher-level test:** No test for the scenario where **signals accumulate from two different star systems before a flush trigger**. If FSSSignalDiscovered events from System A and System B arrive without a flush trigger in between, the batch metadata will reflect System B while containing signals from System A. This is unlikely in practice (FSDJump is a flush trigger), but there's no test proving it can't happen.

---

## 5. Are negative cases tested?

**Verdict: ✅ Well covered.**

| Negative case | Test |
|---|---|
| Removed events not reportable (ApproachBody, LeaveBody, SAAScanComplete) | `test_parser.py::TestIsReportable::test_removed_events_not_reportable` + 3 watcher tests |
| Invalid/unknown event types | `test_validator.py::TestValidate::test_unknown_event_type` |
| Missing required fields | Parametrized test for CarrierJump, FSSSignalDiscovered, FSSDiscoveryScan, CodexEntry |
| ApproachSettlement without StationName or Name | `test_approach_settlement_requires_station_name_or_name` |
| Scan without session state | `test_scan_rejected_without_session_state` |
| Scan with wrong system | `test_scan_rejected_with_wrong_system` |
| SystemAddress mismatch in StarPos augmentation | `test_does_not_augment_starpos_if_system_mismatch` |
| Empty batch → None | `test_signal_batcher.py::TestFlush::test_returns_none_when_empty` |
| Empty NavRoute route | `test_validator.py::TestValidateNewJournalEvents::test_navroute_empty_route_rejected` |
| Missing auxiliary file | `test_watcher.py::TestAuxiliaryFileHandling::test_market_event_missing_market_json` |
| Invalid auxiliary JSON | `test_watcher.py` + `test_parser.py` |
| Empty Market (all items filtered) | `test_watcher.py::test_empty_market_no_submission` |
| Per-event exception isolation | `test_watcher.py::test_per_event_exception_does_not_block_later_events` |

---

## 6. Is there a test for SystemName→StarSystem rename in FSSDiscoveryScan?

**Verdict: ❌ NO. This is a gap.**

The `transform_fss_discovery_scan()` method in `validator.py` (lines 233-237) implements:
```python
if "SystemName" in message_payload and "StarSystem" not in message_payload:
    message_payload["StarSystem"] = message_payload.pop("SystemName")
elif "SystemName" in message_payload:
    message_payload.pop("SystemName")
```

This is a critical EDDN compatibility fix — the ED journal emits `SystemName` for FSSDiscoveryScan, but EDDN's fssdiscoveryscan/1 schema requires `StarSystem`. **No test exercises this rename path.** All existing tests supply `StarSystem` directly in the raw event, bypassing the rename logic entirely.

The parser test (`test_parser.py::test_valid_fssdiscoveryscan`) correctly uses `SystemName` in the test data, confirming this is the real journal format. But the validator test never uses `SystemName`.

**Two untested branches:**
1. `SystemName` present, `StarSystem` absent → rename should occur
2. Both `SystemName` and `StarSystem` present → `SystemName` should be dropped, `StarSystem` kept

---

## 7. Is there a test for StationName→Name rename in ApproachSettlement?

**Verdict: ✅ YES.**

`test_validator.py::TestTransformApproachSettlement::test_renames_station_name_to_name` explicitly:
- Creates an event with `StationName` (no `Name`)
- Asserts `StationName` is absent from output
- Asserts `Name` == "Galileo" in output

However, the edge case where **both** `StationName` and `Name` are present is not tested. The code handles it (drops `StationName`, keeps `Name`), but this branch is untested. Low risk — this scenario is unlikely in real data.

---

## 8. Are there integration-level tests that exercise the full pipeline?

**Verdict: Partial — the watcher tests come close.**

The watcher tests (`TestDedicatedSchemaRouting`) exercise: journal file → parser → watcher routing → validator → submitter (mocked). This is nearly end-to-end, but the submitter is always mocked, so no actual HTTP request or SSL context handling is tested.

No test exercises: watcher poll loop → file detection → incremental read → full routing → submission in a single async flow. The existing tests call `_process_file` directly.

This is adequate for the schema fix scope — the integration gap is pre-existing and not specific to this change.

---

## 9. Any test that passes but shouldn't?

**Verdict: No false-positive tests found.**

All schema ref assertions match the actual constants. No test asserts the wrong schema ref. The `test_fss_discovery_scan_triggers_flush_and_uses_dedicated_schema` correctly checks for both `EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF` and `EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF` in the submission list.

---

## Summary

### ✅ Correct
- All 232 tests pass
- Constants are exhaustively tested with individual + complete-set assertions
- All transform methods have substantive test coverage including field stripping, augmentation, and _Localised handling
- Signal batcher is thoroughly unit-tested (accumulation, stripping, metadata, flush, clear, triggers)
- Watcher routing tests exercise realistic journal file flows through parser → routing → validator → submitter
- Negative cases are well covered (removed events, missing fields, system mismatches, empty data)
- StationName→Name rename for ApproachSettlement is tested
- CodexEntry correctly tested for preserving journal/1-disallowed fields (VoucherAmount, Traits, etc.)

### ❌ Blocker
- **Missing test for SystemName→StarSystem rename in FSSDiscoveryScan** (`validator.py:233-237`). This is a critical EDDN compatibility fix with zero test coverage on its rename path. Both branches (rename when StarSystem absent, drop when both present) are untested. The real ED journal uses `SystemName`, so this is the production code path.

### ⚠️ Note
- **N1: Dead code in SignalBatcher** — `is_system_change()` and `clear()` are fully tested but never called by the watcher. The watcher's flush-trigger approach handles system changes correctly (submitting the old system's signals before processing the jump), making these methods unused. Consider either: (a) removing them to avoid confusion, or (b) adding a watcher test that calls `clear()` on system change if the intent is to discard stale signals instead of submitting them. Current behavior (flush=submit) is correct for EDDN.
- **N2: Untested edge case** — ApproachSettlement with both `StationName` and `Name` present. Low risk.
- **N3: No watcher test for cross-system signal accumulation** — signals from two different systems in the same batch without a flush trigger between them. Unlikely in practice but not proven by tests.
