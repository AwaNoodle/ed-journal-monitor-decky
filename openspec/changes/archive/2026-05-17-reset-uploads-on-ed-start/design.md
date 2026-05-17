## Context

The `EDDNSubmitter` class tracks four statistics as instance variables:
- `_success_count: int` — total successful uploads
- `_fail_count: int` — total failed uploads
- `_last_upload_time: str | None` — ISO timestamp of last upload
- `_last_upload_event: str | None` — event name of last upload

These are exposed via `get_stats()` and emitted to the frontend through `status_update`, `upload_success`, and `upload_failed` events. Currently they accumulate for the entire plugin lifetime (from load to unload) and are never reset.

The `set_ed_running()` method in `main.py` handles the ED state transition and emits `ed_state_change`. This is the natural insertion point for a session-boundary reset.

## Goals / Non-Goals

**Goals:**
- Reset all upload statistics when ED starts (transition from `false` → `true`)
- Emit `status_update` after reset so the frontend updates immediately
- Keep changes minimal and isolated to backend
- No frontend changes required

**Non-Goals:**
- Do NOT clear the activity log (it persists across sessions)
- Do NOT reset on ED stop (previous session totals should remain visible)
- Do NOT persist reset state (stats are in-memory only)

## Decisions

### 1. Backend-only reset via `EDDNSubmitter.reset_stats()`

Add a `reset_stats()` method to `EDDNSubmitter` that zeroes all four counters. Call it from `Plugin.set_ed_running()` when the transition is to `true`.

**Rationale:** The submitter is the single source of truth for stats. Resetting at the source ensures consistency between backend state and frontend display. The frontend already listens to `status_update` and handles zero/null values correctly.

**Alternatives considered:**
- *Frontend-only reset*: Would create a mismatch between backend and frontend state on status re-fetch.
- *Recreate the submitter instance*: Overkill; `reset_stats()` is simpler and clearer.

### 2. Emit `status_update` after reset

After calling `reset_stats()`, emit a `status_update` event with the zeroed stats. This reuses the existing frontend listener — no new event types needed.

**Rationale:** The frontend's `status_update` listener already calls `setSuccessCount(data.success_count)`, `setFailCount(data.fail_count)`, `setLastUpload(data.last_upload_time)`, and `setLastUploadEvent(data.last_upload_event)`. When these receive `0` / `None`, the UI correctly shows `✅ 0 ❌ 0` and "No uploads yet".

**Alternatives considered:**
- *New event type `stats_reset`*: Unnecessary; `status_update` already covers it.
- *Frontend resets on `ed_state_change`*: Would duplicate state logic and risk inconsistency.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| `set_ed_running(True)` called without a submitter (early init) | Guard with `if self.submitter:` before calling `reset_stats()` |
| Existing test `test_set_ed_running_true` asserts `len(emitted_events) == 1` | Update the test to expect 2 events (`status_update` + `ed_state_change`) |
| Race condition: emit before reset completes | `reset_stats()` is synchronous (no I/O), so ordering is guaranteed |
