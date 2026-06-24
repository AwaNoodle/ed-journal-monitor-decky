## Project: ED Journal Monitor Decky Plugin

Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN.

## Tech Stack
- Frontend: TypeScript, React, @decky/api, @decky/ui (Decky plugin framework)
- Backend: Python 3.9+ (asyncio, stdlib only - no pip packages)
- Build: Rollup + TypeScript for frontend; Python directly for backend
- Tests: pytest + pytest-asyncio (429 tests, all passing)
- Known on-device issue: Decky Loader's PyInstaller-embedded Python 3.11 can't find system SSL certs; submitter uses `_build_ssl_context()` with explicit CA bundle cascade (env → certifi → system paths)

## Architecture
- Frontend detects ED start/stop via `SteamClient.GameSessions.RegisterForAppLifetimeNotifications`, plus `SteamClient.System.RegisterForOnResumeFromSuspend` for suspend/resume handling, and `check_ed_running()` callable to detect ED already running at plugin load
- Backend handles file watching, parsing, validation, EDDN submission, activity logging, and diagnostics
- Communication: callable() (frontend→backend), decky.emit() (backend→frontend)
- Journal path: auto-detected via Steam libraryfolders.vdf scan, with manual fallback
- No root flag needed

### Backend Callable Methods (frontend→backend)
`get_status`, `start_watcher`, `stop_watcher`, `find_journal_path`, `set_journal_path`, `set_enabled`, `set_uploader_id`, `set_detailed_logging`, `set_ed_running`, `check_ed_running`, `create_diagnostics`, `get_recent_activity`

### Backend-Emitted Events (backend→frontend)
`ed_state_change`, `upload_success`, `upload_failed`, `status_update`, `activity_update`, `commander_detected`

## Coding Rules
- Always write tests before (or alongside) implementing a change — prefer delegating test creation to a subagent or specialized agent when available
- Ensure there is a verifiable way to confirm a change is successful (e.g., passing tests, manual verification steps documented in the task)
- Always run tests & lint/typecheck before committing or marking a task complete — all tests must pass
- Keep this file (AGENTS.md) up-to-date after implementing any change
- After implementing any change, update `README.md` if user-facing behavior, features, or supported events have changed
- After implementing any change, add an entry under `[Unreleased]` in `CHANGELOG.md`
- When tagging a new release, use `bash scripts/release.sh <version>` (e.g. `bash scripts/release.sh 0.3.0`): it bumps `package.json`, prompts for the `CHANGELOG.md` update (move `[Unreleased]` entries under the new version header with the release date, add a fresh `[Unreleased]` section), commits both, and creates the tag. Never create a tag before bumping `package.json` — Decky displays the version from `package.json`

## Reporting
- All report and review output (code reviews, diagnostics, analysis, etc.) must be written to the `./reports/` folder

## EDDN Compliance
- All changes **MUST** follow the guidelines in the [EDDN Developers Guide](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md)
- All schema handling **MUST** match the requirements documented in each schema's README file in the [EDDN live schemas folder](https://github.com/EDCD/EDDN/blob/live/schemas)
- When modifying any event transformation, validation, filtering, or submission logic, cross-reference the relevant schema README before implementing

## Key Files
- `main.py` — Plugin entry point, wires all backend modules
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log, constants, signal_batcher)
- `src/api.ts` — Defines all 12 callable frontend→backend methods
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
