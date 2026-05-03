## 1. Project Scaffold

- [x] 1.1 Clone Decky plugin template and initialize project structure (package.json, tsconfig, rollup.config, plugin.json, main.py)
- [x] 1.2 Configure plugin.json with name, author, flags (no root), api_version
- [x] 1.3 Set up Python backend directory structure (main.py, modules for watcher, parser, validator, submitter, path_finder)
- [x] 1.4 Verify plugin builds and loads in Decky with a minimal "hello world" frontend and backend

## 2. Journal Path Detection

- [x] 2.1 Implement VDF parser: read `libraryfolders.vdf`, extract all library paths via regex
- [x] 2.2 Implement compatdata scanner: for each library, glob `compatdata/359320/pfx/drive_c/users/*/Saved Games/Frontier Developments/Elite Dangerous/` and validate presence of `Journal*.log`
- [x] 2.3 Implement settings-based cache: save/load journal path from `DECKY_PLUGIN_SETTINGS_DIR`, validate on load
- [x] 2.4 Implement `find_journal_path` callable: cascade through cached → VDF scan → return None
- [x] 2.5 Implement `set_journal_path` callable: accept manual path, validate, save to settings
- [x] 2.6 Add unit tests for VDF parsing with sample libraryfolders.vdf content
- [x] 2.7 Add unit tests for compatdata scanning with mock directory structure

## 3. Journal Parser

- [x] 3.1 Implement JSON line parser: read each line, parse with `json.loads()`, validate `timestamp` and `event` fields exist
- [x] 3.2 Implement reportable event filter: return True for `FSDJump`, `Scan`, `Location`, `Docked`, `FSSDiscoveryScan`
- [x] 3.3 Implement `LoadGame` event handler: extract and store `horizons` and `odyssey` flags in session state
- [x] 3.4 Implement `Fileheader` event handler: extract game version for `softwareVersion` in EDDN header
- [x] 3.5 Add unit tests for parser with sample journal lines (port from existing TS test fixtures)

## 4. Journal Watcher

- [x] 4.1 Implement polling loop using `asyncio`: list directory, find `Journal*.log` files, compare with known state
- [x] 4.2 Implement file position tracking: `Map<filepath, int>` for last-read line number, read only new lines
- [x] 4.3 Implement `start_watcher` callable: begin polling on configured interval, process events through parser → validator → submitter pipeline
- [x] 4.4 Implement `stop_watcher` callable: stop polling loop, persist last-active timestamp to `DECKY_PLUGIN_RUNTIME_DIR`
- [x] 4.5 Implement catch-up logic on start: if last-active timestamp exists, process files modified after that timestamp
- [x] 4.6 Implement first-run logic: if no last-active timestamp, only process current date's journal files
- [x] 4.7 Add unit tests for position tracking and incremental reading

## 5. EDDN Submission

- [x] 5.1 Implement EDDN message construction: `$schemaRef`, `header` (uploaderID, softwareName, softwareVersion, gatewayTimestamp), `message` payload
- [x] 5.2 Implement field stripping: remove EDDN-disallowed fields from each event type before submission
- [x] 5.3 Implement `horizons`/`odyssey` augmentation: inject boolean flags into message payload from session state
- [x] 5.4 Implement schema validation for reportable events (FSDJump, Scan, Location, Docked, FSSDiscoveryScan) — required fields check per event type
- [x] 5.5 Implement HTTP submission via `urllib.request`: POST JSON to `https://eddn.edcd.io:4430/upload/`
- [x] 5.6 Implement exponential backoff retry: max 3 retries, handle 429/5xx/timeout, skip on 4xx (non-429)
- [x] 5.7 Implement upload statistics tracking: count successes and failures, emit `status_update` via `decky.emit()`
- [x] 5.8 Implement `upload_success` and `upload_failed` event emissions to frontend
- [x] 5.9 Add unit tests for message construction, field stripping, augmentation
- [x] 5.10 Add unit tests for submission with mocked HTTP responses (success, rate limit, server error)

## 6. Frontend — Game Lifecycle

- [x] 6.1 Implement `SteamClient.GameSessions.RegisterForAppLifetimeNotifications` registration with AppID 359320 filter
- [x] 6.2 On ED start (`bRunning: true`): call `find_journal_path` if needed, then call `start_watcher`
- [x] 6.3 On ED stop (`bRunning: false`): call `stop_watcher`
- [x] 6.4 Register listeners on plugin mount, unregister on dismount
- [x] 6.5 Add event listeners for Decky suspend/resume (optional, for catch-up on resume)

## 7. Frontend — UI Panel

- [x] 7.1 Implement status display: idle/watching/error states based on backend events
- [x] 7.2 Implement upload statistics display: success count, fail count, last-upload time from `status_update` events
- [x] 7.3 Implement enable/disable toggle: call backend to start/stop, suppress auto-start when disabled
- [x] 7.4 Implement manual journal path input: text field + submit, call `set_journal_path`, show success/error
- [x] 7.5 Implement uploader ID input: text field + submit, save to settings
- [x] 7.6 Implement current journal path display with auto-detected vs manual label
- [x] 7.7 Add plugin icon and title view

## 8. Integration and Testing

- [x] 8.1 End-to-end test: plugin loads → ED starts → watcher starts → journal events parsed → EDDN submission attempted (dry-run mode)
- [x] 8.2 Test catch-up scenario: ED runs, watcher stops, ED continues, watcher restarts → missed events processed
- [x] 8.3 Test SD card scenario: journal on SD card, card ejected and reinserted
- [x] 8.4 Test with real Elite Dangerous journal files (copy fixtures to test directory)
- [x] 8.5 Verify no root flag needed: all operations work as deck user
