## Project: ED Journal Monitor Decky Plugin

Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN.

## Tech Stack
- Frontend: TypeScript, React, @decky/api, @decky/ui (Decky plugin framework)
- Backend: Python 3.9+ (asyncio, stdlib only - no pip packages)
- Build: Rollup + TypeScript for frontend; Python directly for backend
- Tests: pytest + pytest-asyncio (205 tests, all passing)
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
- Keep this file (AGENTS.md) and README.md up-to-date after implementing any change

## Key Files
- `main.py` — Plugin entry point, wires all backend modules
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log, constants)
- `src/api.ts` — Defines all 12 callable frontend→backend methods
- `src/types.d.ts` — TypeScript type definitions for callable results and emitted event payloads
- `src/index.tsx` — Frontend: game lifecycle + plugin registration
- `src/Content.tsx` — Frontend: UI panel (status, configuration, recent errors, recent activity, diagnostics)
- `tests/` — All Python tests (run with `PYTHONPATH=. .venv/bin/python -m pytest tests/ -v` or `npm run test`)
- `plugin.json` — Decky plugin metadata (no root flag)

## Deployment
- Package: `npm run package` → produces `ed-journal-monitor.zip`
- Deploy: `scp ed-journal-monitor.zip deck@legiongo.local:~/Documents/`
- Install: Decky Developer mode → Browse → select zip
- **Do not** copy files directly into `/home/deck/homebrew/plugins/` — it breaks Decky developer mode
