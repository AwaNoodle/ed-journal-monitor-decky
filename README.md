# ED Journal Monitor — Decky Plugin

A [Decky](https://github.com/SteamDeckHomebrew/decky-loader) plugin for Steam Deck that monitors Elite Dangerous journal files and submits events to the [Elite Dangerous Data Network (EDDN)](https://eddn.edcd.io/).

## Features

- **Hands-off operation**: Automatically detects when Elite Dangerous starts and stops, beginning/ending journal monitoring accordingly
- **Auto-discovery**: Finds the ED journal directory by scanning Steam's library configuration — no manual setup required for Steam installs
- **EDDN submission**: Validates and submits journal/1 events plus Market/Outfitting/Shipyard auxiliary schemas to EDDN
- **No root access required**: All operations use user-accessible filesystem paths
- **Steam Deck optimized**: Lightweight polling-based watcher (default 10s interval), minimal resource usage
- **Diagnostic bundle**: Package log files, settings, and runtime state into a zip for offline troubleshooting
- **Detailed logging toggle**: Increase log verbosity from INFO to DEBUG for richer diagnostic capture
- **Activity log & error display**: See recent upload activity and errors in real-time, with event-level detail on failures
- **Auto uploader ID**: Automatically sets your EDDN uploader ID from your CMDR name when a game session loads

## Architecture

```mermaid
graph LR
  subgraph Frontend["Frontend (TypeScript)"]
    A[SteamClient lifecycle]
    B[UI panel]
    C[Status display]
    D[Configuration]
  end

  subgraph Backend["Backend (Python)"]
    E[File watcher\n(polling)]
    F[Journal parser]
    G[EDDN validator]
    H[EDDN submitter]
    I[Path finder]
    J[Settings manager]
    K[Activity log]
    L[Diagnostics]
    M[Constants]
  end

  Frontend -->|callable\(\)| Backend
  Backend -->|decky.emit\(\)| Frontend
```

**Frontend→Backend** communication uses Decky `callable()` (see [src/api.ts](src/api.ts)).
**Backend→Frontend** communication uses `decky.emit()` events (see [Emitted Events](#emitted-events) below).

## Installation

### From Decky Plugin Store

1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) on your Steam Deck
2. Install this plugin from the Decky plugin store

### Manual Install

1. Build and package the plugin:
   ```bash
   npm install
   npm run package
   ```
2. Copy `ed-journal-monitor.zip` to your Steam Deck (e.g. via SCP)
3. Enable Developer Mode in Decky settings
4. Install the zip directly via Decky's "Install Plugin from ZIP" option

## Configuration

On first launch, the plugin will automatically scan for your Elite Dangerous journal directory. If it's not found (e.g., ED not yet installed), it will re-scan when you start the game.

### Enable/Disable Monitor

Toggle the monitor on/off from the **Enabled** toggle at the top of the plugin panel. When disabled, the watcher will not start even if ED is running.

### Manual Journal Path

If auto-detection fails (non-Steam ED installs, Lutris, Heroic, flatpak, custom Wine prefixes):

1. Open the plugin panel in Decky
2. Enter the full path to your journal directory in "Manual Journal Path"
3. Click "Set Manual Path"

**Typical Proton journal path:**
```
~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
```

> **Note:** The path finder scans `drive_c/users/*/Saved Games/...` — the username may differ from `steamuser` depending on your Proton configuration.

You can also click **Re-scan for Journal Path** at any time to retry auto-detection.

### Uploader ID

Set your EDDN uploader ID in the plugin settings. This becomes the `uploaderID` field in EDDN message headers and helps EDDN identify your submissions. EDDN recommends using your CMDR name.

If no uploader ID is set, the plugin will automatically populate it from your CMDR name when Elite Dangerous loads a game session (detected from the `LoadGame` journal event). A warning is shown in the UI until this happens.

### Detailed Logging

Toggle **Detailed Logging** in the Diagnostics section to switch between INFO and DEBUG log verbosity. DEBUG logging produces richer diagnostic output for troubleshooting. This setting persists across restarts.

### All Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Master enable/disable for the monitor |
| `detailed_logging` | `false` | DEBUG vs INFO log verbosity |
| `uploader_id` | `""` | EDDN uploader ID (auto-set from CMDR name if empty) |
| `journal_path` | `null` | Auto-detected or manually set journal directory |
| `journal_path_source` | `null` | `"auto"` or `"manual"` — how the path was set |
| `poll_interval` | `10` | Seconds between journal directory polls |

## Development

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

## EDDN Event Coverage

Upload endpoint: `https://eddn.edcd.io:4430/upload/`

### journal/1 schema

| Event | Description |
|-------|-------------|
| FSDJump | System jump data |
| Scan | Body scan data |
| Location | Current location on load |
| Docked | Station docking event |
| CarrierJump | Fleet carrier jump arrival |
| SAASignalsFound | SAA scan signals found |

> **Note:** Market, Outfitting, and Shipyard are also reportable events but use dedicated schemas — see Auxiliary below. FSSSignalDiscovered, FSSDiscoveryScan, NavRoute, ApproachSettlement, and CodexEntry use their own dedicated schemas — see below.

### Auxiliary EDDN schemas

These events trigger reading a sidecar JSON file and use a dedicated schema:

| Journal trigger | Auxiliary file | Schema |
|-----------------|----------------|--------|
| Market | `Market.json` | `commodity/3` |
| Outfitting | `Outfitting.json` | `outfitting/2` |
| Shipyard | `Shipyard.json` | `shipyard/2` |
| NavRoute | `NavRoute.json` | `navroute/1` |

### Dedicated EDDN schemas

These events have their own EDDN schema (not journal/1):

| Event | Schema | Notes |
|-------|--------|-------|
| FSSSignalDiscovered | `fsssignaldiscovered/1` | Batched: individual signals accumulated and flushed on trigger events (FSSDiscoveryScan, SupercruiseEntry, Location, FSDJump, CarrierJump) |
| FSSDiscoveryScan | `fssdiscoveryscan/1` | Requires `BodyCount`, `NonBodyCount`; `SystemName` → `StarSystem` rename |
| ApproachSettlement | `approachsettlement/1` | Requires `Latitude`, `Longitude`, `BodyID`, `BodyName`, `MarketID`; `StationName` → `Name` rename |
| CodexEntry | `codexentry/1` | Requires `Name`, `Region`, `EntryID`, `BodyID`, `BodyName` |

### Events not sent to EDDN

These journal events have no EDDN schema and are not reported:

| Event | Reason |
|-------|--------|
| ApproachBody | No EDDN schema exists |
| LeaveBody | No EDDN schema exists |
| SAAScanComplete | No EDDN schema exists |

## UI Panel

The Decky plugin panel has five sections:

- **Status**: Enabled toggle, ED status (running/not running), Journal status (watching/found/not found), upload counts (✅ success / ❌ failed), last upload event & time
- **Configuration**: Journal path display, path source (auto/manual), re-scan button, manual journal path input, EDDN uploader ID input, auto-set warning when uploader ID is empty
- **Recent Errors**: Last 5 failed uploads with event type, timestamp, error classification, error message, and HTTP status
- **Recent Activity**: Last 10 upload attempts with success/failure indicator, event type, and timestamp
- **Diagnostics**: Detailed logging toggle, create diagnostic bundle button, bundle result (path + size)

## Event Flow

1. **ED starts** → SteamClient fires `AppLifetimeNotifications` (or fallback `/proc` scan for already-running ED) → frontend calls `setEdRunning(true)`
2. **Path discovery** → frontend calls `findJournalPath()` → backend scans Steam `libraryfolders.vdf` or uses cached path
3. **Watcher starts** → frontend calls `startWatcher()` → backend polls journal directory every 10s
4. **Event processing** → new journal lines are parsed → reportable events are validated against EDDN schema requirements → auxiliary sidecar files are read for Market/Outfitting/Shipyard/NavRoute → FSSSignalDiscovered events are batched → dedicated schema events use their own transforms
5. **Submission** → validated events are transformed (disallowed fields stripped, StarPos/horizons/odyssey augmented) → POSTed to EDDN with retry logic (3 retries, exponential backoff)
6. **UI updates** → backend emits `upload_success`/`upload_failed`/`activity_update`/`status_update` → frontend updates counters, activity list, and error display
7. **ED stops** → frontend calls `stopWatcher()` → watcher persists `last_active` timestamp for catch-up on next start

## Emitted Events

| Event | Direction | Trigger |
|-------|-----------|----------|
| `ed_state_change` | Backend→Frontend | ED running state changes |
| `upload_success` | Backend→Frontend | EDDN submission succeeds |
| `upload_failed` | Backend→Frontend | EDDN submission fails |
| `status_update` | Backend→Frontend | After every submission attempt |
| `activity_update` | Backend→Frontend | Activity log entry recorded (success or failure) |
| `commander_detected` | Backend→Frontend | CMDR name extracted from LoadGame event |

## Troubleshooting

### SSL/Certificate Errors

Decky Loader embeds Python 3.11 via PyInstaller, which may not find system CA certificates. If you see upload failures with SSL errors:

1. Set the `SSL_CERT_FILE` environment variable pointing to a CA bundle before launching Decky:
   ```bash
   export SSL_CERT_FILE=/etc/ssl/cert.pem
   ```
2. The plugin automatically tries: `SSL_CERT_FILE` env → certifi bundle → system CA paths (`/etc/ssl/cert.pem`, `/etc/ssl/certs/ca-certificates.crt`, `/etc/pki/tls/certs/ca-bundle.crt`) → fallback
3. If all paths fail, the default SSL context is used (will likely fail on Decky). Enable **Detailed Logging** to see which SSL source was selected.

### Journal Path Not Found

- Auto-detection only works for Steam installs (scans `libraryfolders.vdf`)
- Non-Steam installs (Lutris, Heroic, flatpak, custom Wine prefixes) require manual path entry
- If the watcher never starts when ED launches, check that the journal path is set in the Configuration section
- Click **Re-scan for Journal Path** to retry auto-detection after installing ED

### EDDN Submission Failures

- **HTTP 429 (Rate Limited)**: Transient — the plugin retries up to 3 times with exponential backoff. Repeated 429s in Recent Errors means EDDN is throttling; events will eventually succeed.
- **HTTP 4xx (Client Error)**: Permanent — the event failed validation. Check Recent Errors for the specific error message from EDDN.
- **HTTP 5xx (Server Error)**: Transient — EDDN is having issues. The plugin retries automatically.
- **Network Error**: Check your internet connection. The plugin retries automatically.

### Plugin Not Detecting ED Start

- Game lifecycle detection requires `SteamClient.GameSessions` which may be unavailable on some SteamOS versions — the plugin logs a warning but doesn't show this in the UI
- If ED was already running when the plugin loaded, it uses `/proc` scanning and journal file modification time heuristics to detect this
- As a workaround, you can manually toggle the **Enabled** switch off/on to trigger watcher startup

### Watcher Not Starting After System Resume

The plugin registers for suspend/resume notifications and checks consistency on resume. If the watcher is stale after resuming your Deck while ED is running, try toggling **Enabled** off and back on.

## Known Limitations

- **Polling-based watching**: Not inotify; 10s default interval means up to 10s delay before new events are picked up
- **PyInstaller SSL**: Decky's embedded Python may not find system CA certs; the `_build_ssl_context()` cascade mitigates but may still fail on some configurations
- **/proc scanning**: Process names are truncated to 15 characters by the Linux kernel (`EliteDangerous64.exe` → `EliteDangerous6`); detection may break if Frontier changes the executable name
- **SteamClient availability**: `SteamClient.GameSessions` and `SteamClient.System` may be undefined on some SteamOS versions
- **Activity log is in-memory**: Lost on plugin reload/unload; only the last 50 entries are retained
- **NavRoute requires sidecar file**: NavRoute data comes from `NavRoute.json` in the journal directory, routed to `navroute/1` schema
- **Signal batching**: FSSSignalDiscovered events are batched and flushed on trigger events; signals accumulated before a crash/reload are lost
- **ApproachSettlement Latitude/Longitude**: These fields are disallowed in journal/1 but required in approachsettlement/1; per-schema stripping handles this correctly

## Diagnostic Bundle

The **Create Diagnostic Bundle** button in the Diagnostics section creates a zip file at `$DECKY_PLUGIN_SETTINGS_DIR/ed-jm-diagnostics.zip` containing:

| File | Contents |
|------|----------|
| `runtime_state.json` | Python version, plugin version, watcher state, file positions, known files, settings summary, submitter stats |
| `settings.json` | Raw settings dump |
| `plugin.json` | Plugin metadata |
| `plugin.log` | Decky plugin log (if available) |

Share this zip file when requesting support.

## License

MIT
