## Why

The plugin is a competent EDDN submitter but its panel shows only operational telemetry (`✅ 42 ❌ 0`, error tables, diagnostics) — nothing a commander wants to glance at mid-flight on the Steam Deck quick-access menu. The Deck form factor is ideal for a glanceable side panel, so we turn the panel into a live session summary that surfaces player-facing value (current location, jumps, distance, bodies scanned, first discoveries) the plugin already sees in the journal stream but currently discards after EDDN routing.

## What Changes

- Add a session-stats accumulator that observes the parsed journal event stream and maintains running totals for the **current ED game launch**: current system/commander, jumps, distance travelled, bodies scanned, and first-discovery count.
- Introduce the observe tap as a **stream-consumer fan-out** in the watcher (a `list[StreamConsumer]` fed by one loop) rather than a single hardcoded call, with the accumulator as the first registered consumer. This is the same raw-event seam a future EDSM forwarder will tap (see `docs/exploration/2026-06-25-multi-target-eddn.md`), so shaping it as a one-entry list now makes that change purely additive. Only the observe fan-out is built here — lifecycle fan-out is deferred to the change that needs it.
- Reset session stats on game launch (the existing `set_ed_running(True)` hook), with a soft reset when the active commander changes. Do **not** reset on journal file rolls (`Continued`), same-commander relogs/mode switches, or suspend/resume.
- Add a `get_session_stats()` backend callable (rehydrate on panel open) and a `session_update` backend→frontend emit (live updates).
- Add a new **Session** panel section (hero location line + 2×2 counter grid) placed first, above the existing Status section.
- **Out of scope (deferred):** estimated exploration credit value (requires a hand-rolled body-value model) is explicitly left to a future change.

## Capabilities

### New Capabilities
- `session-dashboard`: A player-facing live summary of the current ED game launch — accumulating session stats from the journal event stream, the session-boundary/reset semantics, the backend callable + emit contract, and the Session panel UI.

### Modified Capabilities
<!-- None. The accumulator observes the existing event stream in parallel to EDDN
     routing without changing any EDDN submission, validation, or watcher routing
     requirements. New UI is additive and owned by the session-dashboard capability. -->

## Impact

- **Backend:** new `src/modules/` accumulator module (stdlib-only); a thin `StreamConsumer` protocol (`observe(event, session_state)`); `watcher._process_file` gains a consumer fan-out loop **before** the `is_reportable` filter, and `JournalWatcher` takes a `consumers` list; `main.py` registers the accumulator as consumer #1, adds `stats.reset()` at the `set_ed_running(True)` hook, and a `get_session_stats` callable. The EDDN submission path is untouched.
- **Frontend:** new Session `PanelSection` in `src/Content.tsx`; new `get_session_stats` entry in `src/api.ts`; new `session_update` payload + `SessionStats` type in `src/types.d.ts`.
- **Docs/meta:** `AGENTS.md` (new callable + emit, new module), `README.md` (user-facing feature), `CHANGELOG.md` (`[Unreleased]`).
- **Tests:** accumulator unit tests (counting + boundary/reset semantics) and watcher integration test confirming stats observe without affecting EDDN routing.
