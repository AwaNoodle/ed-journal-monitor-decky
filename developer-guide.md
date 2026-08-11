# Developer Guide

Architecture details, known limitations, and development setup for the ED Journal Monitor Decky plugin.

## Event Flow

1. **ED starts** → SteamClient fires `AppLifetimeNotifications` (or fallback `/proc` scan for already-running ED) → frontend calls `setEdRunning(true)`
2. **Path discovery** → frontend calls `findJournalPath()` → backend scans Steam `libraryfolders.vdf` or uses cached path
3. **Watcher starts** → frontend calls `startWatcher()` → backend polls journal directory every 10s
4. **Event processing** → new journal lines are parsed → reportable events are validated against EDDN schema requirements → auxiliary sidecar files are read for Market/Outfitting/Shipyard/NavRoute → FSSSignalDiscovered events are batched → dedicated schema events use their own transforms
5. **Submission** → validated events are transformed (disallowed fields stripped, StarPos/horizons/odyssey augmented) → POSTed to EDDN with retry logic (3 retries, exponential backoff)
6. **UI updates** → backend emits status/activity events → frontend updates counters, activity list, and error display
7. **ED stops** → frontend calls `stopWatcher()` → watcher persists `last_active` timestamp for catch-up on next start

## Known Limitations

- **Polling-based watching**: Not inotify; 10s default interval means up to 10s delay before new events are picked up
- **PyInstaller SSL**: Decky's embedded Python may not find system CA certs; the `_build_ssl_context()` cascade mitigates but may still fail on some configurations
- **/proc scanning**: Process names are truncated to 15 characters by the Linux kernel (`EliteDangerous64.exe` → `EliteDangerous6`); detection may break if Frontier changes the executable name
- **SteamClient availability**: `SteamClient.GameSessions` and `SteamClient.System` may be undefined on some SteamOS versions
- **Activity log is in-memory**: Lost on plugin reload/unload; only the last 50 entries are retained
- **NavRoute requires sidecar file**: NavRoute data comes from `NavRoute.json` in the journal directory, routed to `navroute/1` schema
- **Signal batching**: FSSSignalDiscovered events are batched and flushed on trigger events; signals accumulated before a crash/reload are lost
- **ApproachSettlement Latitude/Longitude**: These fields are disallowed in journal/1 but required in approachsettlement/1; per-schema stripping handles this correctly

## Development Setup

### Prerequisites

- Node.js (for frontend build)
- Python 3.9+ (for backend)
- pytest, pytest-asyncio (for Python tests)

### Build

```bash
npm install
npm run build      # bundles frontend to dist/
```

### Package

```bash
npm run package      # builds + zips plugin files into ed-journal-monitor.zip
```

### Test

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v
# or: npm run test
```

### Lint / Typecheck

```bash
npm run lint:ts
npm run lint:py
```

### Deployment

- **Package:** `npm run package` → produces `ed-journal-monitor.zip`
- **Deploy:** `scp ed-journal-monitor.zip deck@legiongo.local:~/Documents/`
- **Install:** Decky Developer mode → Browse → select zip
- **Do not** copy files directly into `/home/deck/homebrew/plugins/` — it breaks Decky developer mode

## Key Files

- `main.py` — Plugin entry point, wires all backend modules
- `src/modules/` — Python backend modules (settings, path_finder, parser, validator, submitter, watcher, diagnostics, activity_log, constants, signal_batcher)
- `src/api.ts` — Defines all 12 callable frontend→backend methods
- `src/types.d.ts` — TypeScript type definitions for callable results and emitted event payloads
- `src/index.tsx` — Frontend: game lifecycle + plugin registration
- `src/Content.tsx` — Frontend: UI panel, ordered by reading frequency (health strip, Navigation, Session always visible; Data flow, Setup, Troubleshooting collapsible) — see AGENTS.md's "Panel Layout" section
- `plugin.json` — Decky plugin metadata (no root flag)

## Architecture

- **Frontend** detects ED start/stop via `SteamClient.GameSessions.RegisterForAppLifetimeNotifications`, plus `SteamClient.System.RegisterForOnResumeFromSuspend` for suspend/resume handling, and `check_ed_running()` callable to detect ED already running at plugin load
- **Backend** handles file watching, parsing, validation, EDDN submission, activity logging, and diagnostics
- **Communication:** `callable()` (frontend→backend), `decky.emit()` (backend→frontend)
- **Journal path:** auto-detected via Steam `libraryfolders.vdf` scan, with manual fallback

### Backend Callable Methods (frontend→backend)

`get_status`, `start_watcher`, `stop_watcher`, `find_journal_path`, `set_journal_path`, `set_enabled`, `set_uploader_id`, `set_detailed_logging`, `set_ed_running`, `check_ed_running`, `create_diagnostics`, `get_recent_activity`

### Backend-Emitted Events (backend→frontend)

`ed_state_change`, `upload_success`, `upload_failed`, `status_update`, `activity_update`, `commander_detected`
