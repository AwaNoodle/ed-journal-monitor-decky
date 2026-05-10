# ED Journal Monitor — Decky Plugin

A [Decky](https://github.com/SteamDeckHomebrew/decky-loader) plugin for Steam Deck that monitors Elite Dangerous journal files and submits events to the [Elite Dangerous Data Network (EDDN)](https://eddn.edcd.io/).

## Features

- **Hands-off operation**: Automatically detects when Elite Dangerous starts and stops, beginning/ending journal monitoring accordingly
- **Auto-discovery**: Finds the ED journal directory by scanning Steam's library configuration — no manual setup required
- **EDDN submission**: Validates and submits journal/1 events plus Market/Outfitting/Shipyard auxiliary schemas to EDDN
- **No root access required**: All operations use user-accessible filesystem paths
- **Steam Deck optimized**: Lightweight polling-based watcher, minimal resource usage
- **Diagnostic bundle**: Package log files, settings, and runtime state into a zip for offline troubleshooting
- **Detailed logging toggle**: Increase log verbosity from INFO to DEBUG for richer diagnostic capture
- **Activity log & error display**: See recent upload activity and errors in real-time, with event-level detail on failures

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
  end

  Frontend <--> Backend
```

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

### Manual Setup

If auto-detection fails (non-Steam ED installs, Lutris, etc.):

1. Open the plugin panel in Decky
2. Enter the full path to your journal directory in "Manual Journal Path"
3. Click "Set Manual Path"

**Typical Proton journal path:**
```
~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
```

### Uploader ID

Set your EDDN uploader ID in the plugin settings. This helps EDDN identify your submissions.

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
source .venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v
```

### Lint / Typecheck

```bash
npm run lint:ts
npm run lint:py
```

## EDDN Event Coverage

### journal/1 schema

| Event | Description |
|-------|-------------|
| FSDJump | System jump data |
| Scan | Body scan data |
| Location | Current location on load |
| Docked | Station docking event |
| FSSDiscoveryScan | Full system scan data |
| NavRoute | Planned route data (from `NavRoute.json`) |
| ApproachBody | Body approach telemetry |
| LeaveBody | Body departure telemetry |
| ApproachSettlement | Settlement approach telemetry |
| CarrierJump | Fleet carrier jump arrival |
| FSSSignalDiscovered | FSS signal discovery |
| SAAScanComplete | Detailed surface scan completion |

### Auxiliary EDDN schemas

| Journal trigger | Auxiliary file | Schema |
|-----------------|----------------|--------|
| Market | `Market.json` | `commodity/3` |
| Outfitting | `Outfitting.json` | `outfitting/2` |
| Shipyard | `Shipyard.json` | `shipyard/2` |

## License

MIT
