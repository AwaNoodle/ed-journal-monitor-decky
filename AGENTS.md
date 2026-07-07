## Project: ED Journal Monitor Decky Plugin

Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN.

## Tech Stack
- Frontend: TypeScript, React, @decky/api, @decky/ui (Decky plugin framework)
- Backend: Python 3.9+ (asyncio, stdlib only - no pip packages)
- Build: Rollup + TypeScript for frontend; Python directly for backend
- Tests: pytest + pytest-asyncio (604 tests, all passing)
- Known on-device issue: Decky Loader's PyInstaller-embedded Python 3.11 can't find system SSL certs; submitter uses `_build_ssl_context()` with explicit CA bundle cascade (env → certifi → system paths)

## Architecture
- Frontend detects ED start/stop via `SteamClient.GameSessions.RegisterForAppLifetimeNotifications`, plus `SteamClient.System.RegisterForOnResumeFromSuspend` for suspend/resume handling, and `check_ed_running()` callable to detect ED already running at plugin load
- Backend handles file watching, parsing, validation, EDDN submission, activity logging, and diagnostics
- Communication: callable() (frontend→backend), decky.emit() (backend→frontend)
- Journal path: auto-detected via Steam libraryfolders.vdf scan, with manual fallback
- No root flag needed

### Backend Callable Methods (frontend→backend)
`get_status`, `start_watcher`, `stop_watcher`, `find_journal_path`, `set_journal_path`, `set_enabled`, `set_uploader_id`, `set_edsm_credentials`, `get_edsm_credentials`, `set_edsm_lookups_enabled`, `set_detailed_logging`, `set_ed_running`, `check_ed_running`, `create_diagnostics`, `get_recent_activity`, `get_session_stats`

### Backend-Emitted Events (backend→frontend)
`ed_state_change`, `upload_success`, `upload_failed`, `status_update`, `activity_update`, `commander_detected`, `session_update`, `edsm_worth_scanning`

### Stream Consumers
The watcher fans every parsed event out to a `list[StreamConsumer]` (`src/modules/stream_consumer.py`) — protocol: `observe(event, session_state)` plus lifecycle/stats hooks `name`, `get_stats()`, `on_session_start()`, `on_session_stop()` — **before** the EDDN reportable filter, in parallel to (never gating) EDDN routing. Consumer #1 is the session-stats accumulator (`session_stats`); consumer #2 is the EDSM forwarder (`forwarders/edsm.py`); consumer #3 is the EDSM lookup consumer (`edsm_lookup_consumer.py`). `main.py` drives `on_session_start()` for every consumer at the `set_ed_running(true)` hook and `on_session_stop()` when the watcher stops.

### EDSM Forwarding (second submission target)
`forwarders/edsm.py` (`EdsmForwarder`) is a stream consumer that forwards **raw journal lines verbatim** (no EDDN transform) to EDSM's `api-journal-v1` under the user's own credentials, via the stdlib `urllib` client in `forwarders/edsm_client.py`. It is fully isolated from EDDN: it copies the event before enriching with transient-state hints, filters by EDSM's discard list (fetched once per session), batches with size/time/forced-on-stop flush, and classifies responses by `msgnum` (1xx OK · 2xx fatal/no-retry · 5xx transient/retry) with rate-limit backoff. EDSM is **off until an API key is set** (the key's presence is the identifiable-upload consent gate). Settings keys: `edsm_commander_name`, `edsm_api_key`.

### EDSM Read Path (worth-scanning lookup)
`edsm_read_client.py` (`EdsmReadClient`) issues GET requests to EDSM's public `api-system-v1/bodies` endpoint (no API key required; reuses the custom User-Agent and `build_ssl_context()`). Returns a `SystemBodiesResult` with `status` ("ok"/"unknown"/"unavailable"), `bodies` list, and `body_count`. Field names confirmed from live API: `discovery` dict = body FSS-scanned; no `isMapped` field on this endpoint. `edsm_system_cache.py` (`SystemLookupCache`) provides a per-system in-memory TTL cache (default 4 h). `edsm_worth_scanning.py` derives a "green"/"yellow"/"red"/None verdict from a result. `edsm_lookup_consumer.py` (`EdsmLookupConsumer`) is a `StreamConsumer` that observes `FSDJump`/`Location`, dedupes per system, and runs lookups fire-and-forget as asyncio tasks. The `edsm_lookups_enabled` setting (default off) gates all read calls; the consumer's `reports_upload_stats = False` keeps it out of the upload-stats map. Verdict payloads are emitted via the `edsm_worth_scanning` decky event and stored in `main.py._edsm_verdict` for `get_status` rehydration.

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
- After implementing any change, add an entry under `[Unreleased]` in `CHANGELOG.md`
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
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log, constants, signal_batcher, session_stats, stream_consumer, ssl_context, edsm_read_client, edsm_system_cache, edsm_worth_scanning, edsm_lookup_consumer, forwarders/edsm, forwarders/edsm_client)
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
