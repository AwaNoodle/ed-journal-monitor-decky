# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.2] - 2026-06-23

### Changed

- Removed the **Last Upload** row from the status panel — upload events are already visible in the Recent Activity section
- Journal Status active state simplified from "🟢 Watching & Uploading" to "🟢 Watching"

## [0.2.1] - 2026-06-22

### Added

- EDDN submission for `FSSAllBodiesFound` events (fssallbodiesfound/1 schema)

### Fixed

- Recent Activity list layout changed from right-biased to left-biased alignment. Event type and timestamp now display on separate lines, flush left, improving readability in the narrow Steam Deck panel.
- Recent Activity section moved to appear immediately after Status (above Configuration), making upload activity visible without scrolling past configuration fields.

## [0.1.0] - 2026-05-16

### Added

- Elite Dangerous journal file monitoring via polling watcher (Steam Deck compatible)
- EDDN submission for 11 schema types: journal events, commodity, outfitting, shipyard, FSS/SAE signals, navroute, FC materials
- Auto-detection of journal path via Steam `libraryfolders.vdf` scan with manual override
- Game lifecycle detection (start/stop/suspend/resume) via SteamClient events
- Per-event validation with disallowed-field stripping and StarPos augmentation
- Retry logic with exponential backoff and jitter for EDDN submission failures
- Activity log (in-memory circular buffer, 50 entries) with success/failure tracking
- Diagnostic bundle generation for troubleshooting
- Detailed logging toggle (DEBUG/INFO) persisted to settings
- SSL context cascade for PyInstaller-embedded Python certificate resolution
- Frontend UI panel with status, configuration, recent errors, recent activity, and diagnostics
