## Purpose

Watch the Elite Dangerous journal directory for new events and route them for submission.

## Requirements

### Requirement: Start watcher when ED launches
The backend SHALL begin monitoring the journal directory when instructed by the frontend (triggered by ED game start).

#### Scenario: ED starts with known journal path
- **WHEN** the frontend calls `start_watcher` and a valid journal path is configured
- **THEN** the backend SHALL begin polling the journal directory for new/changed files

#### Scenario: ED starts with no known journal path
- **WHEN** the frontend calls `start_watcher` and no journal path is configured
- **THEN** the backend SHALL NOT start polling
- **THEN** the backend SHALL report status as "waiting for journal path"

### Requirement: Stop watcher when ED exits
The backend SHALL stop monitoring and persist state when instructed by the frontend (triggered by ED game stop).

#### Scenario: ED exits normally
- **WHEN** the frontend calls `stop_watcher`
- **THEN** the backend SHALL stop the polling loop
- **THEN** the backend SHALL persist the last-active timestamp to `DECKY_PLUGIN_RUNTIME_DIR`

#### Scenario: Watcher not running when stop called
- **WHEN** the frontend calls `stop_watcher` but the watcher is not running
- **THEN** the backend SHALL do nothing (no-op)

### Requirement: Poll journal directory on configurable interval
The backend SHALL poll the journal directory for changes at a configurable interval (default 10 seconds).

#### Scenario: Polling detects new journal file
- **WHEN** a new `Journal*.log` file appears in the journal directory
- **THEN** the backend SHALL process all lines in the new file from the beginning

#### Scenario: Polling detects appended content
- **WHEN** an existing `Journal*.log` file has new content appended since last read
- **THEN** the backend SHALL read only the new lines from the last processed position

#### Scenario: Polling interval configured by user
- **WHEN** the user sets a custom poll interval in the UI
- **THEN** the backend SHALL use that interval for subsequent polling cycles

### Requirement: Track file positions for incremental processing
The backend SHALL track the last-read line position for each journal file to avoid reprocessing.

#### Scenario: File read incrementally
- **WHEN** a journal file has 100 lines and the watcher last processed up to line 80
- **THEN** the backend SHALL read only lines 81-100 on the next poll

#### Scenario: New file processed from start
- **WHEN** a journal file is encountered for the first time
- **THEN** the backend SHALL process all lines from line 1

### Requirement: Filter EDDN-reportable events
The backend SHALL filter journal events to only those reportable to EDDN under the `journal/1` schema.

#### Scenario: Reportable event detected
- **WHEN** a parsed journal event has type `FSDJump`, `Scan`, `Location`, `Docked`, or `FSSDiscoveryScan`
- **THEN** the backend SHALL pass the event to the EDDN submission pipeline

#### Scenario: Non-reportable event detected
- **WHEN** a parsed journal event has a type not in the reportable set
- **THEN** the backend SHALL skip the event

#### Scenario: Fileheader or LoadGame event
- **WHEN** a `Fileheader` event is encountered
- **THEN** the backend SHALL extract game version info for the software version header
- **WHEN** a `LoadGame` event is encountered
- **THEN** the backend SHALL extract and store `horizons` and `odyssey` flags for use in EDDN message augmentation

### Requirement: Parse journal lines as JSON
The backend SHALL parse each line in journal files as a JSON object.

#### Scenario: Valid JSON line
- **WHEN** a journal line contains valid JSON with `timestamp` and `event` fields
- **THEN** the backend SHALL return the parsed event object

#### Scenario: Invalid JSON line
- **WHEN** a journal line contains invalid JSON or is blank
- **THEN** the backend SHALL skip the line and log a warning

### Requirement: Catch up on missed events after restart
The backend SHALL process journal events that occurred while the watcher was not running.

#### Scenario: Watcher restarts with last-active timestamp
- **WHEN** the watcher starts and a last-active timestamp exists from a previous session
- **THEN** the backend SHALL process all journal files with modification times after the timestamp
- **THEN** the backend SHALL submit any reportable events found

#### Scenario: No last-active timestamp (first run)
- **WHEN** the watcher starts and no last-active timestamp exists
- **THEN** the backend SHALL process only events from the current date's journal files
