## 1. Target type + activity log (backend, TDD)

- [x] 1.1 Add `TARGET_EDDN = "eddn"`, `TARGET_EDSM = "edsm"`, and `UploadTarget = Literal["eddn", "edsm"]` to `src/modules/constants.py` (mirroring `AuxiliarySchemaType`)
- [x] 1.2 Update `tests/test_activity_log.py`: entries carry a `target` field; `record_success`/`record_failure` accept a `target` param defaulting to `"eddn"`; add cases for an explicit `target="edsm"` success and failure entry; assert existing EDDN behavior unchanged (default target `eddn`)
- [x] 1.3 Implement the `target` param + entry field in `src/modules/activity_log.py` (`record_success`/`record_failure`) until 1.2 passes; keep the `activity_update` emit and `get_recent` behavior unchanged

## 2. EDSM per-event activity + counting (backend, TDD)

- [x] 2.1 Extend `tests/test_edsm_consumer.py`: on a terminal success flush, the forwarder records one `success` activity entry per event with `target="edsm"` and `success_count += len(batch)`; on a fatal response it records one `failure` entry per event (`error_type="edsm"`, `error_message` containing the `msgnum`/msg) and `fail_count += len(batch)`; on a transient response it records nothing and does not change counts (events retained). Use a fake/mock activity log to capture calls
- [x] 2.2 Give `EdsmForwarder` an `activity_log` reference and record per-event on terminal responses; change success/fail counting from per-batch to per-event, counted only on terminal outcomes, until 2.1 passes (EDDN path untouched)

## 3. Wiring (backend, TDD)

- [x] 3.1 Add/extend a test asserting `main.py` constructs `EdsmForwarder` with the shared `activity_log`
- [x] 3.2 Pass `self.activity_log` into `EdsmForwarder` in `main.py` until 3.1 passes

## 4. Frontend

- [x] 4.1 In `src/types.d.ts`, add `type UploadTarget = "eddn" | "edsm";` and a required `target: UploadTarget` field on `ActivityEntry`
- [x] 4.2 In `src/Content.tsx`, render a compact target badge on each Recent Activity row and each Recent Errors row (e.g. `✅ FSDJump · EDSM · 19:31`); include `target` in the activity React key (`getActivityKey`)

## 5. Verification + docs

- [x] 5.1 Run the full test suite + lint/typecheck + frontend build — all green; confirm existing EDDN activity/message tests are unchanged (no regression)
- [x] 5.2 Update `AGENTS.md` (activity entries are target-tagged; EDSM records per-event on terminal batch flush; EDSM counts per event) and add a `[Unreleased]` `CHANGELOG.md` entry
- [x] 5.3 Document a manual on-device verification step: with EDSM active, confirm Recent Activity shows both `eddn` and `edsm` rows and that a bad EDSM key surfaces `edsm`/`203` failure rows in Recent Errors while EDDN rows keep succeeding
