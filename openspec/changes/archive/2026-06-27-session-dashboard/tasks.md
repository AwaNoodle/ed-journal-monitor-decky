## 1. Accumulator module (backend, TDD)

- [x] 1.1 Write `tests/test_session_stats.py` covering: FSDJump increments jumps + distance + current system; Scan increments bodies scanned; Scan with `WasDiscovered:false` increments first discoveries; Scan with `WasDiscovered:true` does not; missing `WasDiscovered` treated as not-first; non-tracked events are ignored
- [x] 1.2 Add boundary/reset tests: `reset()` zeros all counters; soft reset when LoadGame commander differs; no reset on same-commander LoadGame; stats preserved across a `Continued` file roll
- [x] 1.3 Implement `src/modules/session_stats.py` — `SessionStats` dataclass (`commander`, `star_system`, `jumps`, `distance_ly`, `bodies_scanned`, `first_discoveries`) and an `observe(event)` / `reset()` accumulator (stdlib-only) until tests in 1.1–1.2 pass

## 2. Watcher integration (backend, TDD)

- [x] 2.1 Define a thin `StreamConsumer` protocol with a single `observe(event: ParsedEvent, session_state: SessionState) -> None` method; have the accumulator satisfy it
- [x] 2.2 Write a watcher test asserting every registered consumer's `observe` is called for every parsed event before the `is_reportable` filter (use a fake second consumer to prove fan-out, not just the accumulator), and that EDDN validation/submission for reportable events is unchanged (no regression in existing routing)
- [x] 2.3 Wire a consumer fan-out loop into `watcher._process_file` immediately after `parser.parse_line`, before `is_reportable`; give `JournalWatcher` a `consumers: list[StreamConsumer]` collaborator and register the accumulator as consumer #1 from `main.py`
- [x] 2.4 Coalesce `session_update` emits during the initial-scan replay (update in-memory during replay, emit once when it settles) to avoid panel flicker

## 3. Lifecycle + frontend contract (backend, TDD)

- [x] 3.1 Write tests: `set_ed_running(true)` resets session stats AND the reset runs before `_initial_scan` replay (retroactive totals preserved); `get_session_stats()` returns current stats
- [x] 3.2 In `main.py`, instantiate the accumulator, add `stats.reset()` beside the existing `submitter.reset_stats()` in `set_ed_running(true)` (before replay), and add the `get_session_stats` callable
- [x] 3.3 Emit `session_update` from the backend when stats change, carrying the `SessionStats` shape

## 4. Frontend panel

- [x] 4.1 Add `SessionStats` type and `session_update` payload to `src/types.d.ts`; add `getSessionStats` to `src/api.ts`
- [x] 4.2 Add a `Session` `PanelSection` to `src/Content.tsx` placed before Status — hero location line + 2×2 counter grid (Variant B) — using the existing inline-flex `<div>` idiom, with a neutral empty state
- [x] 4.3 Rehydrate via `getSessionStats` on panel mount and subscribe to `session_update` for live updates (mirror the existing `status_update` wiring)

## 5. Verification + docs

- [x] 5.1 Run full test suite + lint/typecheck (`npm run test`, frontend build) — all green
- [x] 5.2 Update `AGENTS.md` (new `get_session_stats` callable, new `session_update` emit, new `session_stats` module), `README.md` (session dashboard feature), and add a `[Unreleased]` `CHANGELOG.md` entry
- [x] 5.3 Document a manual on-device verification step (launch ED, confirm Session section updates live and resets on relaunch)
