## Project: ED Journal Monitor Decky Plugin

Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN.

## Tech Stack
- Frontend: TypeScript, React, @decky/api, @decky/ui (Decky plugin framework)
- Backend: Python 3.9+ (asyncio, stdlib only - no pip packages)
- Build: Rollup + TypeScript for frontend; Python directly for backend
- Tests: pytest + pytest-asyncio (735 tests, all passing)
- Known on-device issue: Decky Loader's PyInstaller-embedded Python 3.11 can't find system SSL certs; submitter uses `_build_ssl_context()` with explicit CA bundle cascade (env → certifi → system paths)

## Architecture
- Frontend detects ED start/stop via `SteamClient.GameSessions.RegisterForAppLifetimeNotifications`, plus `SteamClient.System.RegisterForOnResumeFromSuspend` for suspend/resume handling, and `check_ed_running()` callable to detect ED already running at plugin load
- Backend handles file watching, parsing, validation, EDDN submission, activity logging, and diagnostics
- Communication: callable() (frontend→backend), decky.emit() (backend→frontend)
- Journal path: auto-detected via Steam libraryfolders.vdf scan, with manual fallback
- No root flag needed

### Backend Callable Methods (frontend→backend)
`get_status`, `start_watcher`, `stop_watcher`, `find_journal_path`, `set_journal_path`, `set_enabled`, `set_uploader_id`, `set_edsm_credentials`, `get_edsm_credentials`, `set_edsm_lookups_enabled`, `set_edsm_notifications_enabled`, `set_edsm_notify_all_verdicts`, `set_detailed_logging`, `set_ed_running`, `check_ed_running`, `create_diagnostics`, `get_recent_activity`, `get_session_stats`, `get_nearest_scoopable_star`

### Backend-Emitted Events (backend→frontend)
`ed_state_change`, `upload_success`, `upload_failed`, `status_update`, `activity_update`, `commander_detected`, `session_update`, `edsm_worth_scanning`, `edsm_next_hop`

### Stream Consumers
The watcher fans every parsed event out to a `list[StreamConsumer]` (`src/modules/stream_consumer.py`) — protocol: `observe(event, session_state)` plus lifecycle/stats hooks `name`, `get_stats()`, `on_session_start()`, `on_session_stop()` — **before** the EDDN reportable filter, in parallel to (never gating) EDDN routing. Consumer #1 is the session-stats accumulator (`session_stats`); consumer #2 is the EDSM forwarder (`forwarders/edsm.py`); consumer #3 is the EDSM lookup consumer (`edsm_lookup_consumer.py`); consumer #4 is the EDSM next-hop consumer (`edsm_next_hop_consumer.py`). `main.py` drives `on_session_start()` for every consumer at the `set_ed_running(true)` hook and `on_session_stop()` when the watcher stops. Route-aware consumers additionally receive `on_nav_route(route)` — the watcher's `_fan_out_nav_route()` delivers the plotted `Route` array (parsed from NavRoute.json, or an empty list for NavRouteClear) to any consumer implementing that optional hook, before EDDN routing.

### EDSM Forwarding (second submission target)
`forwarders/edsm.py` (`EdsmForwarder`) is a stream consumer that forwards **raw journal lines verbatim** (no EDDN transform) to EDSM's `api-journal-v1` under the user's own credentials, via the stdlib `urllib` client in `forwarders/edsm_client.py`. It is fully isolated from EDDN: it copies the event before enriching with transient-state hints, filters by EDSM's discard list (fetched once per session), batches with size/time/forced-on-stop flush, and classifies responses by `msgnum` (1xx OK · 2xx fatal/no-retry · 5xx transient/retry) with rate-limit backoff. EDSM is **off until an API key is set** (the key's presence is the identifiable-upload consent gate). Settings keys: `edsm_commander_name`, `edsm_api_key`.

### EDSM Read Path (worth-scanning lookup + system value)
`edsm_read_client.py` (`EdsmReadClient`) issues GET requests to EDSM's public `api-system-v1/bodies` and `api-system-v1/estimated-value` endpoints (no API key required; reuses the custom User-Agent and `build_ssl_context()`). `get_system_bodies()` returns a `SystemBodiesResult` with `status` ("ok"/"unknown"/"unavailable"), `bodies` list, and `body_count`. Field names confirmed from live API: `discovery` dict = body FSS-scanned; no `isMapped` field on this endpoint. `get_estimated_value()` returns a `SystemValueResult` with `status`, `total_value` (EDSM's `estimatedValue` — scan-only, a floor that excludes any mapping bonus), and `valuable_bodies` (raw `valuableBodies` dicts: `bodyName`/`valueMax`/etc.). `edsm_system_cache.py` (`SystemLookupCache`) provides two independent per-system in-memory TTL caches (default 4 h) sharing one instance: `get`/`set` for bodies, `get_value`/`set_value` for estimated-value. `edsm_worth_scanning.py` derives a "green"/"yellow"/"red"/None verdict from a bodies result. `edsm_system_value.py` derives a `SystemValueSummary` (`total_value` + ranked top-N `priority_bodies`, default top 3) from a value result; returns `None` (neutral) unless the system is known with data. `edsm_lookup_consumer.py` (`EdsmLookupConsumer`) is a `StreamConsumer` that observes `FSDJump`/`Location`, dedupes per system, and runs both lookups concurrently fire-and-forget as asyncio tasks. The `edsm_lookups_enabled` setting (default off) gates all read calls; the consumer's `reports_upload_stats = False` keeps it out of the upload-stats map. The consumer also computes a `notify: bool` from the verdict plus the `edsm_notifications_enabled` / `edsm_notify_all_verdicts` settings (`_compute_notify`) — true only for green (either threshold) or yellow (all-verdicts threshold); red and neutral never notify, and the computation issues no extra request. The merged verdict+value payload is emitted via the `edsm_worth_scanning` decky event (fields: `system`, `verdict`, `source`, `totalValue`, `priorityBodies`, `notify`) and stored in `main.py._edsm_verdict` for `get_status` rehydration — `_on_edsm_verdict` sets the base dict first (accepting but deliberately **not** storing `notify`, so a status fetch can never replay a toast), `_on_edsm_value` merges `totalValue`/`priorityBodies` onto it (a value-fetch failure independently reports the neutral `totalValue: null, priorityBodies: []` without blocking the verdict or the notify decision).

### Worth-Scanning Notifications
`src/index.tsx` registers an `edsm_worth_scanning` listener inside `definePlugin()` (disposed in `onDismount()`) — alive for the whole Steam session, unlike `Content.tsx`'s listener, which only exists while the panel is mounted. When the event's `notify` field is true it calls `toaster.toast()` (from `@decky/api`) naming the system, with value + top priority bodies as subtext (omitted entirely, not placeholder text, when the value is neutral), and an `onClick` that calls `Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)` (from `@decky/ui`). No sound, no custom duration. `Content.tsx` keeps its own separate listener for the panel and ignores `notify` entirely — decky's emitter supports multiple listeners per event.

### EDSM Next-in-route Preview
`edsm_next_hop.py` holds pure logic: `is_scoopable(star_class)` (KGBFOAM → scoopable; `None` when the class is unknown) and `NextHopTracker` (holds the plotted `Route`; `next_hop(current_system, current_address)` returns the entry *after* the current system, matched by SystemAddress then name; `None` for no route / off-route / final hop). `edsm_next_hop_consumer.py` (`EdsmNextHopConsumer`) is a `StreamConsumer` that tracks the current system from `FSDJump`/`Location` (`observe`) and the route from `on_nav_route()`, re-derives the next hop on either change, and — when `edsm_lookups_enabled` — runs the same bodies+value read for that hop through the **shared** cache/read client (constructed once in `main.py` and passed to both the lookup and next-hop consumers, so a previewed hop is a cache hit once it becomes current). Scoopability comes from the route's `StarClass` (journal-sourced, no network), so the preview still emits scoopability with neutral verdict/value when the EDSM read is unknown/fails; genuine neutral (`system: null`) is only no-route/off-route/final-hop/disabled. It stays quiet until the current system is known (no premature neutral on a route set before the first arrival). Fire-and-forget with the same staleness guard as the lookup consumer. The preview is emitted via the `edsm_next_hop` decky event (fields: `system`, `scoopable`, `starClass`, `verdict`, `source`, `totalValue`, `priorityBodies`) and stored in `main.py._edsm_next_hop` (a neutral payload stores `None`) for `get_status` rehydration; `set_ed_running(false)` and `set_edsm_lookups_enabled(false)` clear it and emit a neutral event, `set_edsm_lookups_enabled(true)` calls `reevaluate()`.

### EDSM Nearest Scoopable Star (on-demand sphere lookup)
`edsm_read_client.py`'s `get_sphere_systems(system_name, radius=DEFAULT_SPHERE_RADIUS)` GETs EDSM's public `api-v1/sphere-systems` (bounded radius, default 25 ly; EDSM caps radius at 100) with `showPrimaryStar=1`, returning a `SphereSystemsResult` — `status` ("ok"/"unknown"/"unavailable") and raw `systems` (each `{name, distance, primaryStar: {type, isScoopable}}`; the queried system is included at distance 0; `primaryStar` can be `{}` when EDSM has no data). `edsm_nearest_scoopable.py`'s `find_nearest_scoopable(systems, current_system)` is pure logic that excludes the current system (case-insensitive name match) and returns the closest entry with `primaryStar.isScoopable is True` — EDSM's own flag is used as-is rather than re-derived from the star-type string (contrast with `edsm_next_hop.is_scoopable`, which infers from a single-letter `StarClass` code since the route doesn't carry EDSM's flag). `edsm_nearest_scoopable_lookup.py`'s `lookup_nearest_scoopable(read_client, current_system, lookups_enabled, radius=None)` orchestrates the two: short-circuits to `"disabled"` when the toggle is off or `"unavailable"` when the current system isn't known yet (no request either way), maps a genuine sphere failure to `"unavailable"` and a no-scoopable-candidate result (including the current system being unknown to EDSM) to `"none_found"`, otherwise `"ok"` with `system`/`distance`/`star_class`. Unlike the arrival-triggered lookup/next-hop consumers, this is **not** a `StreamConsumer` — it's invoked directly by the `get_nearest_scoopable_star` callable (request/response, not an emitted event), using the current system from `EdsmNextHopConsumer.current_system` (a public property) and the read client shared via `main.py.edsm_read_client`. It does not use the per-arrival `SystemLookupCache` since a radius query is point-in-time and user-initiated, not per-system.

### Activity log (target-tagged)
Every activity entry carries a `target` field (`UploadTarget = "eddn" | "edsm"`, defined in `constants.py`; `record_success`/`record_failure` default it to `eddn`). EDDN records per event at submit time; the EDSM forwarder holds the same `ActivityLog` and records **per event only on a terminal batch response** (success → one success entry per event; fatal → one failure entry per event with `error_type="edsm"` and the `msgnum` folded into `error_message`; transient/retried → records nothing until it settles). EDSM upload counts are per event (not per batch), counted only on terminal outcomes, so EDDN and EDSM counts mean the same unit. The frontend renders a target badge on each Recent Activity and Recent Errors row.

### Per-target upload stats
Upload statistics are a **per-target map** (`{"targets": {"eddn": {...}, "edsm": {...}}, "last_upload_time", "last_upload_event"}`) built in `main.py._build_target_stats()` by iterating the consumer registry (EDDN wired in as one entry; any consumer with `reports_upload_stats = True` contributes under its `name`). No hardcoded per-target keys — a 3rd target is purely additive. `get_status` and the `status_update` emit both carry this map; the frontend renders by mapping over entries. The shared SSL context builder lives in `src/modules/ssl_context.py` (`build_ssl_context()`), reused by both EDDN and EDSM.

## Coding Rules
- Always write tests before (or alongside) implementing a change — prefer delegating test creation to a subagent or specialized agent when available
- Ensure there is a verifiable way to confirm a change is successful (e.g., passing tests, manual verification steps documented in the task)
- Always run tests & lint/typecheck before committing or marking a task complete — all tests must pass
- Keep this file (AGENTS.md) up-to-date after implementing any change
- After implementing any change, update `README.md` if user-facing behavior, features, or supported events have changed
- After implementing any change, add an entry under `[Unreleased]` in `CHANGELOG.md`. Keep entries **short** — 1–2 sentences: what changed and, if it isn't obvious, why. These become the GitHub Release notes, so they are for users, not implementers. No internal mechanics (module names, event payload fields, callable names, caching/threading details, rationale for rejected alternatives) — that belongs in AGENTS.md and the OpenSpec archive
- When tagging a new release, use `bash scripts/release.sh <version>` (e.g. `bash scripts/release.sh 0.3.0`): it bumps `package.json`, prompts for the `CHANGELOG.md` update (move `[Unreleased]` entries under the new version header with the release date, add a fresh `[Unreleased]` section), commits both, and creates the tag. Never create a tag before bumping `package.json` — Decky displays the version from `package.json`
- Publishing is automated: `git push --tags` triggers `.github/workflows/release.yml` (on `push: tags: v*`), which lints, tests, packages, **creates the GitHub Release** (notes pulled from the matching `CHANGELOG.md` section), and attaches `ed-journal-monitor-decky-<tag>.zip`. Do not hand-create the GitHub Release for a normal tag push. The workflow also still runs on a manually-published Release (`release: published`) — in that path it skips release creation and only attaches the asset. The Release is created with `GITHUB_TOKEN`, which intentionally does **not** re-trigger the `release: published` job (no double run)

## Feature Workflow
- All feature work **MUST** be done on a dedicated branch or git worktree — never commit feature work directly to `main`
- Every change is integrated into `main` via a Pull Request — no direct pushes to `main`
- When accepting a PR, use **squash and rebase** (squash merge with a rebase) so `main` keeps a linear history

## Reporting
- All report and review output (code reviews, diagnostics, analysis, etc.) must be written to the `./reports/` folder

## EDDN Compliance
- All changes **MUST** follow the guidelines in the [EDDN Developers Guide](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md)
- All schema handling **MUST** match the requirements documented in each schema's README file in the [EDDN live schemas folder](https://github.com/EDCD/EDDN/blob/live/schemas)
- When modifying any event transformation, validation, filtering, or submission logic, cross-reference the relevant schema README before implementing

## Key Files
- `main.py` — Plugin entry point, wires all backend modules
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log, constants, signal_batcher, session_stats, stream_consumer, ssl_context, edsm_read_client, edsm_system_cache, edsm_worth_scanning, edsm_system_value, edsm_lookup_consumer, edsm_next_hop, edsm_next_hop_consumer, edsm_nearest_scoopable, edsm_nearest_scoopable_lookup, forwarders/edsm, forwarders/edsm_client)
- `src/api.ts` — Defines the callable frontend→backend methods
- `src/types.d.ts` — TypeScript type definitions for callable results and emitted event payloads
- `src/index.tsx` — Frontend: game lifecycle + plugin registration
- `src/Content.tsx` — Frontend: UI panel (status, configuration, recent errors, recent activity, diagnostics)
- `tests/` — All Python tests (run with `PYTHONPATH=. .venv/bin/python -m pytest tests/ -v` or `npm run test`)
- `plugin.json` — Decky plugin metadata (no root flag)
- `developer-guide.md` — Architecture, event flow, known limitations, dev setup

## Deployment
- Package: `npm run package` → produces `ed-journal-monitor.zip`
- Deploy: `scp ed-journal-monitor.zip deck@legiongo.local:~/Documents/`
- Install: Decky Developer mode → Browse → select zip
- **Do not** copy files directly into `/home/deck/homebrew/plugins/` — it breaks Decky developer mode
