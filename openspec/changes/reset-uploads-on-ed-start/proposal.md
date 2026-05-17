## Why

The uploads indicator (✅ success count / ❌ fail count) accumulates for the entire plugin lifetime and never resets between Elite Dangerous sessions. After multiple play sessions, the displayed totals are stale and meaningless — they mix counts from unrelated sessions. Users should see per-session totals that reset when a new ED session begins.

## What Changes

- When Elite Dangerous starts (transition from `ed_running: false` to `ed_running: true`), the upload statistics counters (success count, fail count, last upload time, last upload event) SHALL reset to zero/empty.
- The frontend "Uploads" indicator and "Last Upload" display SHALL reflect the reset, showing `✅ 0 ❌ 0` and "No uploads yet" at the start of each session.
- The activity log SHALL NOT be cleared — it continues to accumulate across sessions.
- Previous session totals remain visible until ED starts again (reset occurs on ED *start*, not ED stop).

## Capabilities

### New Capabilities
- `upload-stats-reset`: Upload statistics SHALL reset when Elite Dangerous starts, providing per-session counters.

### Modified Capabilities
- `eddn-submission`: Add a new requirement for the "Track and report upload statistics" requirement to specify that stats reset on ED start.
- `game-lifecycle`: Add a new scenario under the "Detect Elite Dangerous start" requirement for the stats reset side effect.

## Impact

- **Backend**: `EDDNSubmitter` gains a `reset_stats()` method; `Plugin.set_ed_running()` calls it and emits `status_update` on ED start transition.
- **Frontend**: No changes needed — existing `status_update` listener already handles zeroed counts and null last-upload values.
- **Tests**: New tests in `test_submitter.py` for `reset_stats()`; updated/new tests in `test_ed_running.py` for reset behavior on state transitions.
