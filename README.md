# ED Journal Monitor — Decky Plugin

[![Build](https://github.com/AwaNoodle/ed-journal-monitor-decky/actions/workflows/build.yml/badge.svg)](https://github.com/AwaNoodle/ed-journal-monitor-decky/actions/workflows/build.yml)
[![GitHub Release](https://img.shields.io/github/v/release/AwaNoodle/ed-journal-monitor-decky)](https://github.com/AwaNoodle/ed-journal-monitor-decky/releases)

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

## Installation

### From Decky Plugin Store

1. Install [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) on your Steam Deck
2. Install this plugin from the Decky plugin store *(pending acceptance — use Manual Install for now)*

### Manual Install

1. Build and package the plugin:
   ```bash
   npm install
   npm run package
   ```
2. Copy `ed-journal-monitor.zip` to your Steam Deck:
   - **USB**: Switch to Desktop Mode, connect via USB, and copy the file to `~/Documents/`
   - **SCP**: `scp ed-journal-monitor.zip deck@<steamdeck-ip>:~/Documents/`
3. Enable Developer Mode in Decky settings
4. Install the zip directly via Decky's "Install Plugin from ZIP" option

## UI Panel

The Decky plugin panel has five sections:

- **Status**: Enabled toggle, ED status (running/not running), Journal status (watching/found/not found), upload counts (✅ success / ❌ failed), last upload event & time
- **Configuration**: Journal path display, path source (auto/manual), re-scan button, manual journal path input, EDDN uploader ID input, notification when no uploader ID is set
- **Recent Errors**: Last 5 failed uploads with event type, timestamp, error classification, error message, and HTTP status
- **Recent Activity**: Last 10 upload attempts with success/failure indicator, event type, and timestamp
- **Diagnostics**: Detailed logging toggle, create diagnostic bundle button, bundle result (path + size)


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

The plugin will automatically populate the uploader ID from your CMDR name when you start a new game. This identifies your submissions on the EDDN network.

You can also set it manually in the plugin settings. EDDN recommends using your CMDR name.

### Detailed Logging

Toggle **Detailed Logging** in the Diagnostics section to switch between INFO and DEBUG log verbosity. DEBUG logging produces richer diagnostic output for troubleshooting. This setting persists across restarts.

## Verifying Your Submissions

Once Elite Dangerous is running and the plugin shows **Journal: Watching**, your events should be submitted automatically. Here are a few ways to confirm your data is reaching EDDN:

- **[EDDN Status Page](https://eddn.edcd.io/)** — Shows a live feed of all EDDN submissions across all users. Look for your `uploaderID` (your CMDR name) in the messages.
- **EDSM** — If your EDSM account is linked, visit your commander profile on [edsm.net](https://www.edsm.net/) and check that your recent jumps and scans appear.
- **[eddn-tail](https://github.com/AwaNoodle/eddn-tail)** — A lightweight CLI tool that tails the EDDN live feed. Filter by your uploader ID or by the system you're currently in to see your submissions in real time:
  ```bash
  # Filter by your CMDR name
  eddn-tail --uploader "Your CMDR Name"
  # Or filter by system
  eddn-tail --system "Sol"
  ```

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

### Dedicated Schema Events

Events with their own EDDN schema (not journal/1):

| Event | Schema | Notes |
|-------|--------|-------|
| FSSSignalDiscovered | [fsssignaldiscovered/1](https://github.com/EDCD/EDDN/blob/live/schemas/fsssignaldiscovered/1/README.md) | Batched: signals accumulated and flushed on trigger events (FSSDiscoveryScan, SupercruiseEntry, Location, FSDJump, CarrierJump) |
| FSSDiscoveryScan | [fssdiscoveryscan/1](https://github.com/EDCD/EDDN/blob/live/schemas/fssdiscoveryscan/1/README.md) | Requires `BodyCount`, `NonBodyCount`; `SystemName` → `StarSystem` rename |
| ApproachSettlement | [approachsettlement/1](https://github.com/EDCD/EDDN/blob/live/schemas/approachsettlement/1/README.md) | Requires `Latitude`, `Longitude`, `BodyID`, `BodyName`, `MarketID`; `StationName` → `Name` rename |
| CodexEntry | [codexentry/1](https://github.com/EDCD/EDDN/blob/live/schemas/codexentry/1/README.md) | Requires `Name`, `Region`, `EntryID`, `BodyID`, `BodyName` |

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues and solutions.

## Diagnostic Bundle

The **Create Diagnostic Bundle** button in the Diagnostics section creates a zip file at `$DECKY_PLUGIN_SETTINGS_DIR/ed-jm-diagnostics.zip` containing:

| File | Contents |
|------|----------|
| `runtime_state.json` | Python version, plugin version, watcher state, file positions, known files, settings summary, submitter stats |
| `settings.json` | Raw settings dump |
| `plugin.json` | Plugin metadata |
| `plugin.log` | Decky plugin log (if available) |

Share this zip file when requesting support.

## Development

See [developer-guide.md](developer-guide.md) for architecture details, known limitations, and development setup.

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

## License

MIT
