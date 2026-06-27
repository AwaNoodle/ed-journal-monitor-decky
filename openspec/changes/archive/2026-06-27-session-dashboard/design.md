## Context

The plugin parses every journal line in `watcher._process_file`, then routes only EDDN-reportable events to validation/submission. `SessionState` (in `parser.py`) tracks current location/commander but no running totals. Upload stats already reset on ED launch via `set_ed_running(true)` in `main.py`, and the watcher's `_initial_scan` replays the most recent journal file on start — so the existing "uploads this launch" counter is already anchored to a game-launch epoch.

This change adds a parallel, player-facing accumulator over the same event stream without touching the EDDN path. Backend is stdlib-only Python; frontend uses the existing `callable()` (pull) + `decky.emit()` (push) contract.

## Goals / Non-Goals

**Goals:**
- A glanceable live session summary (location, jumps, distance, bodies scanned, first discoveries) for the current ED game launch.
- Clean separation from EDDN routing — the accumulator observes, it does not gate or transform submissions.
- Reuse the existing session-boundary hook and emit/poll patterns rather than inventing new lifecycle machinery.

**Non-Goals:**
- Estimated exploration credit value (Tier 3) — deferred; requires a hand-rolled body-value model and is its own change.
- Persisting session stats across full plugin reload or Deck reboot — in-memory only; a session is a single launch.
- Per-event historical breakdown beyond the current activity log.

## Decisions

### Decision: Observe the stream before the reportable filter
Hook the observe call into `watcher._process_file`, immediately after `parser.parse_line` and **before** `is_reportable`. The accumulator inspects parsed events it cares about (`FSDJump`, `Scan`, `LoadGame`) and ignores the rest.

*Why over alternatives:* Tapping the EDDN-reportable branch would miss `LoadGame` (not reportable) and entangle stats with submission. A separate file re-read would duplicate I/O and risk drift. One observe seam on the existing parse loop is the smallest clean tap.

### Decision: Fan out via a stream-consumer registry, not a hardcoded call
The seam is a **list of stream consumers** fed by one loop, not a single hardcoded `self.stats.observe(event)`:

```python
event = self.parser.parse_line(line)
if event:
    for consumer in self._consumers:
        consumer.observe(event, self.parser.session_state)
```

`JournalWatcher` takes `consumers: list[StreamConsumer]` alongside its other collaborators; `main.py` registers the session accumulator as consumer #1. `StreamConsumer` is a thin protocol — a single `observe(event: ParsedEvent, session_state: SessionState) -> None` method. The accumulator ignores `session_state` (it reads everything it needs off the event); the parameter is in the signature so future consumers that need launch context get it for free.

*Why over a hardcoded single call:* The plugin already has a planned **second** consumer of this exact raw-event stream — an EDSM forwarder (`docs/exploration/2026-06-25-multi-target-eddn.md`), whose tap point is byte-for-byte this seam (raw `ParsedEvent`, before the EDDN reportable filter). EDDN itself is conceptually a third consumer (it stays embedded in the watcher for now — its aux-file reads and batching make a clean extraction a separate, riskier change). With three real consumers of one stream, the rule of three is satisfied: the fan-out is extracted pattern, not speculative generality. Shaping the seam as a one-entry list now makes the EDSM change *append a consumer* instead of *re-cut the watcher seam*.

*Scope boundary (deliberately minimal):* This change builds **only** the observe fan-out. Lifecycle fan-out (a uniform `on_session_start()`/`on_session_stop()` across consumers) is **not** built here — the accumulator keeps its existing reset path (`main.py` calls `stats.reset()` at the `set_ed_running(true)` hook, before replay). EDSM needs richer lifecycle (queue flush, discard-list refresh, credential checks), so generalizing lifecycle belongs to the EDSM change where the second real case forces its shape. Building it now would be the speculative kind of abstraction we're avoiding.

### Decision: Game-launch epoch (Clock A), not LoadGame
Reset on `set_ed_running(true)` — the same hook that already calls `submitter.reset_stats()`. Place `stats.reset()` beside it, and ensure the reset runs before `_initial_scan` replay so the current launch's earlier events are recounted (retroactive totals when the plugin joins a launch late).

*Why over alternatives:* A journal file equals a launch, but files roll mid-session via `Continued`, so "reset on new file" would zero a long session. `LoadGame` fires on every relog/mode switch, so a pure LoadGame epoch resets mid-session on the common relog case. The Steam process signal is independent of file rolls and matches the existing uploads-counter epoch, keeping the panel internally coherent.

### Decision: Soft reset on commander change
On an observed `LoadGame` whose `Commander` differs from the accumulator's current commander, reset. Same-commander `LoadGame` preserves stats.

*Why:* The only real weakness of Clock A is smearing two commanders' stats together under one header. Comparing the incoming commander (already parsed at `parser.py:103`) costs ~5 lines and kills that confusion without inheriting LoadGame's relog noise.

### Decision: `SessionStats` shape + contract
A small dataclass: `commander: str`, `star_system: str`, `jumps: int`, `distance_ly: float`, `bodies_scanned: int`, `first_discoveries: int`. Backend exposes `get_session_stats()` (rehydrate on panel open) and emits `session_update` with the same shape on change. Frontend adds a `SessionStats` type, an `api.ts` entry, and a `session_update` listener mirroring the existing `status_update` wiring.

*Why:* Mirrors the proven `get_status` + `status_update` pattern. In-memory state means rehydrate-on-open needs only the callable, no disk.

### Decision: UI — Session section first (Variant B)
New `PanelSection title="Session"` placed before Status: a full-width hero location line (so long system names wrap rather than truncate) above a 2×2 grid of big-digit counters with dim labels. Built with the inline-flex `<div>` idiom already used in `Content.tsx`.

*Why:* Directly answers the brief's complaint that the panel leads with operational telemetry. Big-digit-over-label is what makes a number glanceable on a moving screen; the hero line fixes truncation.

## Risks / Trade-offs

- **Emit volume during replay** → A full-file replay on watcher start could fire many `session_update` emits. Mitigation: coalesce — update in-memory during replay and emit once at the end (or debounce), so the panel sees one settled value, not a flicker.
- **`Scan` double-counting / event variants** → `Scan` has variants (auto/detailed/nav-beacon); `WasDiscovered` may be absent on some. Mitigation: treat missing `WasDiscovered` as not-first; cover variant handling in unit tests against real journal samples.
- **Commander smear despite soft reset** → If `LoadGame` is missed (e.g. plugin joins mid-session after the only LoadGame), header commander may lag. Mitigation: accept — `SessionState.commander` already drives this elsewhere and is best-effort.
- **Ordering regression** → If a future refactor moves `stats.reset()` after replay, retroactive totals zero out. Mitigation: spec scenario + a test asserting reset-before-replay ordering.
