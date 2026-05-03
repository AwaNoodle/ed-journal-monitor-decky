## Context

A working TypeScript Docker-based ED journal monitor exists at `/Users/mark/sandbox/personal/ed-journal-monitor`. It watches journal files via chokidar polling, parses JSON lines, validates against EDDN schemas (zod), and submits via axios with retry logic. The Decky plugin ports this logic to Python and adds Steam Deck-specific integration: game lifecycle detection, auto journal path discovery, and a UI panel.

Decky plugins have a split architecture: a TypeScript frontend running in the Steam UI process (with access to SteamClient/Router APIs) and a Python backend (with filesystem/network access). They communicate via `callable()` (frontend→backend) and `decky.emit()` (backend→frontend).

Reference projects:
- **SDH-PauseGames** — demonstrates `SteamClient.GameSessions.RegisterForAppLifetimeNotifications` for game start/stop detection
- **SimpleDeckyTDP** — demonstrates `Router.MainRunningApp` for current game identification
- **decky-plugin-template** — official scaffold with `@decky/api`, `@decky/ui`, Python `main.py`

## Goals / Non-Goals

**Goals:**
- Hands-off operation: plugin detects ED start, watches journals, uploads to EDDN, stops when ED exits
- No root access required — all operations use user-accessible paths
- Auto-discover journal directory from Steam configuration; manual fallback for edge cases
- MVP EDDN coverage: `journal/1` schema events (FSDJump, Scan, Location, Docked, FSSDiscoveryScan)
- Port proven logic from existing TypeScript implementation

**Non-Goals:**
- `commodity/3` and `outfitting/2` EDDN schemas (future feature, tracked)
- Root flag or `/proc` inspection for path detection
- Native Linux (non-Proton) ED installs as primary target (manual path fallback covers this)
- Inotify/watchdog-based file watching — polling is sufficient and simpler
- UI for browsing event history or upload details
- Multi-commander support

## Decisions

### 1. Python backend, TypeScript frontend
**Choice**: Python backend (port from TS), TypeScript frontend (standard Decky).  
**Alternatives considered**: Node subprocess (reuse TS code as-is), all-Python (no Decky UI).  
**Rationale**: Decky convention. Python is the standard backend language. Running a second Node runtime on a Steam Deck is wasteful. The logic is straightforward JSON parsing + HTTP POST — no TS-specific advantage.

### 2. No root flag
**Choice**: Plugin runs without the `_root` flag.  
**Alternatives considered**: Root flag for `/proc/<pid>/environ` inspection.  
**Rationale**: Users distrust plugins requesting root. VDF scan + compatdata glob finds the journal path without root. All file reads and HTTP calls work as the deck user. The only thing root enables (process env inspection) is unnecessary given the VDF approach.

### 3. Polling over inotify
**Choice**: Poll journal directory on a configurable interval (default 10s).  
**Alternatives considered**: watchdog/pyinotify, chokidar-style hybrid.  
**Rationale**: Consistent with the existing Docker implementation. Journal files are append-only and change infrequently (30s-2min between events during gameplay). Polling is simple, reliable, and low-overhead on SD card storage. No kernel watch limits to worry about.

### 4. VDF-based journal path detection
**Choice**: Parse `~/.local/share/Steam/config/libraryfolders.vdf` to find Steam libraries, then glob `compatdata/359320/pfx/drive_c/users/*/Saved Games/Frontier Developments/Elite Dangerous/`. Cache found path in plugin settings. Re-scan on ED start event. Manual UI fallback.  
**Alternatives considered**: `/proc/<pid>/environ` for `STEAM_COMPAT_DATA_PATH`, hardcoded path.  
**Rationale**: VDF scan works without root, works before ED is running, handles SD card libraries. Hardcoded path breaks with SD cards. Process inspection requires root or same-user luck.

### 5. SteamClient lifecycle for game detection
**Choice**: Frontend uses `SteamClient.GameSessions.RegisterForAppLifetimeNotifications` to detect ED (AppID 359320) start/stop, then calls backend to start/stop the watcher.  
**Alternatives considered**: Polling `Router.MainRunningApp`, polling `ps` for process.  
**Rationale**: Event-driven, no polling needed on frontend. PauseGames proves this works. `Router.MainRunningApp` is synchronous-only (no notifications). `ps` polling is crude and needs root for reliability.

### 6. EDDN journal/1 schema for MVP
**Choice**: Support FSDJump, Scan, Location, Docked, FSSDiscoveryScan events mapped to `journal/1` schema.  
**Alternatives considered**: All EDDN schemas from day one.  
**Rationale**: These are the highest-volume, most-valuable events. Commodity/outfitting require reading separate JSON files the game writes alongside journals — additional complexity for later.

### 7. Field stripping and augmentation
**Choice**: Explicitly strip EDDN-disallowed fields (e.g., `ActiveFine`, `Crew`) and augment with `horizons`/`odyssey` booleans from `LoadGame` event state.  
**Rationale**: EDDN rejects messages with disallowed fields. The `horizons`/`odyssey` flags are required by the current `journal/1` schema. The `LoadGame` event fires at session start and contains these flags — the watcher must capture and persist them for the session.

## Risks / Trade-offs

- **VDF format stability** → Steam has used this format for years; unlikely to change. Mitigation: manual path fallback covers format breakage.
- **Steam Deck sleep/suspend** → Deck may suspend mid-game; watcher polling stops during suspend. Mitigation: on resume, position-based catch-up processes any missed entries. The `RegisterForOnResumeFromSuspend` event (seen in PauseGames) can trigger a re-scan.
- **EDDN rate limiting** → Rapid events (e.g., multiple scans) could hit 429. Mitigation: exponential backoff retry (ported from existing submitter).
- **Large journal files on SD card** → Reading full files each poll is wasteful. Mitigation: position tracking (only read new lines from last position), consistent with existing watcher.
- **Proton prefix path varies by username** → `steamuser` vs Linux username. Mitigation: glob pattern `users/*/Saved Games/...` handles both.
- **Plugin crash loses position state** → In-memory position map lost on crash. Mitigation: persist last-active timestamp to `DECKY_PLUGIN_RUNTIME_DIR`; on restart, re-process from that timestamp (may cause some duplicate uploads, but EDDN handles dedup).
