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

## EDDN Event Coverage

Upload endpoint: `https://eddn.edcd.io:4430/upload/`

Messages are sent with `softwareName: ED Journal Monitor Decky` in the EDDN header.

### journal/1 Events

Events submitted under the [journal/1](https://github.com/EDCD/EDDN/blob/live/schemas/journal/1/README.md) schema:

| Event | Description |
|-------|-------------|
| FSDJump | System jump data |
| Scan | Body scan data |
| Location | Current location on load |
| Docked | Station docking event |
| CarrierJump | Fleet carrier jump arrival |
| SAASignalsFound | SAA scan signals found |

### Auxiliary Schema Events

Events that read a sidecar JSON file and use a dedicated schema:

| Journal Event | Auxiliary File | Schema |
|---------------|----------------|--------|
| Market | `Market.json` | [commodity/3](https://github.com/EDCD/EDDN/blob/live/schemas/commodity/3/README.md) |
| Outfitting | `Outfitting.json` | [outfitting/2](https://github.com/EDCD/EDDN/blob/live/schemas/outfitting/2/README.md) |
| Shipyard | `Shipyard.json` | [shipyard/2](https://github.com/EDCD/EDDN/blob/live/schemas/shipyard/2/README.md) |
| NavRoute | `NavRoute.json` | [navroute/1](https://github.com/EDCD/EDDN/blob/live/schemas/navroute/1/README.md) |
| FCMaterials | `FCMaterials.json` | [fcmaterials_journal/1](https://github.com/EDCD/EDDN/blob/live/schemas/fcmaterials_journal-README.md) |

### Dedicated Schema Events

Events with their own EDDN schema (not journal/1):

| Event | Schema | Notes |
|-------|--------|-------|
| FSSSignalDiscovered | [fsssignaldiscovered/1](https://github.com/EDCD/EDDN/blob/live/schemas/fsssignaldiscovered/1/README.md) | Batched: signals accumulated and flushed on trigger events (FSSDiscoveryScan, SupercruiseEntry, Location, FSDJump, CarrierJump) |
| FSSDiscoveryScan | [fssdiscoveryscan/1](https://github.com/EDCD/EDDN/blob/live/schemas/fssdiscoveryscan/1/README.md) | Requires `BodyCount`, `NonBodyCount`; `SystemName` → `StarSystem` rename |
| ApproachSettlement | [approachsettlement/1](https://github.com/EDCD/EDDN/blob/live/schemas/approachsettlement/1/README.md) | Requires `Latitude`, `Longitude`, `BodyID`, `BodyName`, `MarketID`; `StationName` → `Name` rename |
| CodexEntry | [codexentry/1](https://github.com/EDCD/EDDN/blob/live/schemas/codexentry/1/README.md) | Requires `Name`, `Region`, `EntryID`, `BodyID`, `BodyName` |
| NavBeaconScan | [navbeaconscan/1](https://github.com/EDCD/EDDN/blob/live/schemas/navbeaconscan/1/README.md) | Requires `NumBodies` |
| FSSAllBodiesFound | [fssallbodiesfound/1](https://github.com/EDCD/EDDN/blob/live/schemas/fssallbodiesfound-README.md) | Requires `Count`; `StarPos` augmented from session state |
| ScanBaryCentre | [scanbarycentre/1](https://github.com/EDCD/EDDN/blob/live/schemas/scanbarycentre-README.md) | Requires `SystemAddress`, `BodyID`; `StarPos` augmented from session state |
| FSSBodySignals | [fssbodysignals/1](https://github.com/EDCD/EDDN/blob/live/schemas/fssbodysignals-README.md) | Requires `BodyName`, `BodyID`, `SystemAddress`, `Signals`; `StarSystem`/`StarPos` augmented; nested `_Localised` stripped |
| DockingGranted | [dockinggranted/1](https://github.com/EDCD/EDDN/blob/live/schemas/dockinggranted-README.md) | Requires `MarketID`, `StationName`; station-context (no `StarPos`) |
| DockingDenied | [dockingdenied/1](https://github.com/EDCD/EDDN/blob/live/schemas/dockingdenied-README.md) | Requires `MarketID`, `StationName`, `Reason`; station-context (no `StarPos`) |

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

### VS Code tasks (Steam Deck deploy scaffolding)

The `.vscode/` tasks deploy a CLI-built zip to a device over SSH. Settings live in
`.vscode/settings.json`, created from `.vscode/defsettings.json` by `.vscode/config.sh`
on first run (`settingscheck` task) and gitignored thereafter.

- **No stored password.** `settings.json` holds no sudo-password key at all. Every privileged
  remote command runs through `.vscode/deploy.sh`, which uses `ssh -t` so `sudo`
  prompts interactively in the task terminal. Nothing is passed via `echo <password> | sudo -S`,
  so no secret reaches `/proc/<pid>/cmdline`, task output, or shell scrollback.
  *Better long-term option:* add a sudoers rule on the device for just the deploy
  commands, e.g. a `/etc/sudoers.d/decky-deploy` entry granting the `deck` user
  `NOPASSWD` on `/usr/bin/mkdir`, `/usr/bin/chown`, `/usr/bin/bsdtar` and
  `/usr/bin/systemctl restart plugin_loader` — scoped commands, never blanket
  `NOPASSWD: ALL` — and the prompts disappear entirely.
- **No shell splicing of settings.** The deploy tasks pass every `${config:*}` value to
  `.vscode/deploy.sh` through the task **environment** (`DECK_USER`, `DECK_IP`,
  `DECK_PORT`, `DECK_DIR`, `PLUGIN_NAME`, `DECK_KEY`), never inside the command
  string. That distinction matters: VS Code substitutes `${config:*}` as raw text, so
  a value spliced into a `command` would be parsed by your *local* shell before any
  script could check it — one `'` or `$(` in `settings.json` would execute on your
  workstation. Environment values are not re-parsed, so `deploy.sh`'s validation is
  the first and only gate: `deckuser`/`deckip`/`pluginname` against `[A-Za-z0-9._-]+`,
  `deckport` numeric, `deckdir` an absolute path, and it fails loudly rather than
  rewriting bad input. `deckkey` is split into ssh flags inside the script (not by a
  shell), each word validated, with `ProxyCommand`/`LocalCommand` rejected because
  they hand a string to a shell; a leading `~/` is expanded for you. The
  multi-command remote block lives in the checked-in `.vscode/deploy-remote.sh`,
  copied to the device and invoked with positional arguments, so no config value is
  ever concatenated into a command string on either side. `pluginname` must match the
  basename of the zip in `out/` and contain no spaces — rename the built zip if the
  CLI emits one with spaces.
- **`depsetup` installs pnpm via `corepack`** (or points at your distro's package
  manager) instead of piping `https://get.pnpm.io/install.sh` into a shell.
- **The Decky CLI is pinned and verified.** `.vscode/setup.sh` downloads Decky CLI
  **0.0.8** from `releases/download/0.0.8/` (never the mutable `releases/latest/`),
  checks the artifact's SHA-256 against a digest embedded in the script, and only
  then makes it executable. A mismatch, a missing checksum tool, or an unsupported
  platform aborts with a non-zero exit — both scripts run under `set -euo pipefail`.
  To bump the CLI: change `DECKY_CLI_VERSION` and recompute every digest with the
  `curl … | sha256sum` loop documented at the top of the script.
- **`cli-build` runs the CLI under plain `sudo`,** not `sudo -E`, so the build does
  not inherit the caller's environment; it fails fast if the verified CLI is absent.

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
