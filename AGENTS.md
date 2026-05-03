## Project: ED Journal Monitor Decky Plugin

Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN.

## Tech Stack
- Frontend: TypeScript, React, @decky/api, @decky/ui (Decky plugin framework)
- Backend: Python 3.9+ (asyncio, stdlib only - no pip packages)
- Build: Rollup + TypeScript for frontend; Python directly for backend
- Tests: pytest + pytest-asyncio (96 tests, all passing)

## Architecture
- Frontend detects ED start/stop via SteamClient.GameSessions.RegisterForAppLifetimeNotifications
- Backend handles file watching, parsing, validation, EDDN submission
- Communication: callable() (frontend→backend), decky.emit() (backend→frontend)
- Journal path: auto-detected via Steam libraryfolders.vdf scan, with manual fallback
- No root flag needed

## Coding Rules
- Always write tests before (or alongside) implementing a change — prefer delegating test creation to a subagent or specialized agent when available
- Ensure there is a verifiable way to confirm a change is successful (e.g., passing tests, manual verification steps documented in the task)
- Always run tests & lint/typecheck before committing or marking a task complete — all tests must pass
- Keep this file (AGENTS.md) and README.md up-to-date after implementing any change

## Key Files
- `main.py` — Plugin entry point, wires all backend modules
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log)
- `src/index.tsx` — Frontend: game lifecycle + plugin registration
- `src/Content.tsx` — Frontend: UI panel (status, configuration, diagnostics)
- `tests/` — All Python tests (run with `PYTHONPATH=. python -m pytest tests/ -v`)
- `plugin.json` — Decky plugin metadata (no root flag)
