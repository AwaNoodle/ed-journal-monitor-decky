# ED Journal Monitor Decky Plugin — Plan

## Status: Implementation Complete

## What Was Built
A Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN. All 50 tasks from the OpenSpec change are complete.

## Components Implemented
1. **Project scaffold** — Decky plugin template customized, builds clean
2. **Journal path detection** — VDF parser + compatdata scanner + settings cache + manual fallback
3. **Journal parser** — JSON line parsing, reportable event filtering, LoadGame/Fileheader handling
4. **Journal watcher** — Polling loop, position tracking, incremental reads, catch-up logic
5. **EDDN submission** — Message construction, field stripping, horizons/odyssey augmentation, HTTP POST with retry
6. **Frontend game lifecycle** — SteamClient AppLifetimeNotifications for ED 359320, suspend/resume handling
7. **Frontend UI panel** — Status, upload stats, enable/disable toggle, manual path input, uploader ID config
8. **Integration tests** — End-to-end pipeline, catch-up, SD card, no-root verification

## Test Results
67 tests, all passing.

## OpenSpec Change
- Change: `ed-journal-monitor-decky` at `openspec/changes/ed-journal-monitor-decky/`
- All artifacts complete (proposal, design, specs, tasks)

## Next Steps
- Test on actual Steam Deck hardware
- Publish to Decky plugin store
- Add commodity/3 and outfitting/2 EDDN schemas as future feature
