## Why

Steam Deck and handheld PC users playing Elite Dangerous have no easy way to contribute their journal data to the Elite Dangerous Data Network (EDDN). Existing tools (EDMarketConnector, EDDiscovery) are desktop applications unsuitable for the Steam Deck's controller-first interface and resource-constrained environment. A Decky plugin integrated into the Steam UI provides a native, hands-off experience: detect when the game starts, watch for journal changes, upload to EDDN, and stop when the game exits.

## What Changes

- New Decky plugin that monitors Elite Dangerous journal files and submits reportable events to EDDN
- Detects ED game start/stop via SteamClient API lifecycle events
- Auto-discovers the ED journal directory by scanning Steam library configuration (no root access required)
- Polls journal files for new entries during gameplay, with position tracking for incremental processing
- Validates events against EDDN schemas, strips disallowed fields, and augments with required metadata (horizons/odyssey flags)
- Uploads validated events to EDDN with exponential backoff retry logic
- Persists last-active timestamp when ED exits, enabling catch-up on next session
- Provides a Decky UI panel for status, configuration, and manual path entry as fallback

## Capabilities

### New Capabilities
- `game-lifecycle`: Detection of Elite Dangerous start/stop via SteamClient API, triggering watcher start/stop and journal path re-scan
- `journal-path-detection`: Auto-discovery of the ED journal directory by parsing Steam's libraryfolders.vdf and scanning compatdata, with settings cache and manual fallback
- `journal-watcher`: Polling-based file watcher that tracks positions, reads new journal lines, and filters EDDN-reportable events
- `eddn-submission`: Event validation against EDDN journal/1 schema, field stripping, horizons/odyssey augmentation, HTTP submission with retry logic
- `plugin-ui`: Decky UI panel showing watcher status, upload counts, last-upload time, and manual journal path configuration

### Modified Capabilities
<!-- No existing capabilities to modify -->

## Impact

- New Decky plugin project scaffolded from official template (TypeScript frontend + Python backend)
- Python backend ports core logic from existing TypeScript Docker project at `/Users/mark/sandbox/personal/ed-journal-monitor`
- No root flag required — all operations use user-accessible filesystem paths and SteamClient frontend APIs
- Dependencies: Python stdlib (json, pathlib, urllib, asyncio, re) + Decky plugin framework; frontend uses @decky/api, @decky/ui
- EDDN API: POST to `https://eddn.edcd.io:4430/upload/` — no auth required, rate-limited
