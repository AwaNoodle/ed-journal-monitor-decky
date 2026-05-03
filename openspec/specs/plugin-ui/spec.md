## ADDED Requirements

### Requirement: Display plugin status panel
The frontend SHALL display a Decky UI panel showing the current state of the journal monitor.

#### Scenario: Plugin idle (ED not running)
- **WHEN** Elite Dangerous is not running
- **THEN** the panel SHALL show status "Idle — waiting for Elite Dangerous"

#### Scenario: Plugin watching (ED running)
- **WHEN** Elite Dangerous is running and the watcher is active
- **THEN** the panel SHALL show status "Watching — uploading journal events"

#### Scenario: Journal path not found
- **WHEN** the journal path is not detected and no manual path is set
- **THEN** the panel SHALL show status "Journal path not found" with an option to set it manually

### Requirement: Display upload statistics
The frontend SHALL display upload counts, last-upload time, and last-upload event name received from backend events.

#### Scenario: Statistics displayed
- **WHEN** the backend emits a `status_update` event
- **THEN** the panel SHALL update the displayed successful upload count and failed upload count

#### Scenario: Last upload time with event name
- **WHEN** the backend emits an `upload_success` event
- **THEN** the panel SHALL update the "Last Upload" timestamp display with both the event name and local time (e.g. "FSDJump — 14:32:05")

#### Scenario: No uploads yet
- **WHEN** no successful uploads have occurred since plugin start
- **THEN** the "Last Upload" field SHALL display "No uploads yet"

### Requirement: Enable and disable the monitor
The frontend SHALL provide a toggle to enable or disable the journal monitor.

#### Scenario: User disables monitor
- **WHEN** the user toggles the monitor off
- **THEN** the frontend SHALL call the backend to stop the watcher (if running)
- **THEN** the frontend SHALL NOT start the watcher on subsequent ED start events

#### Scenario: User re-enables monitor
- **WHEN** the user toggles the monitor on
- **THEN** the frontend SHALL check if ED is currently running
- **THEN** if ED is running, start the watcher immediately

### Requirement: Configure journal path manually
The frontend SHALL provide a text input for the user to set the journal directory path manually.

#### Scenario: User enters manual path
- **WHEN** the user enters a path and submits it
- **THEN** the frontend SHALL call the backend `set_journal_path` method
- **THEN** if valid, display a success message
- **THEN** if invalid, display an error message

### Requirement: Configure uploader ID
The frontend SHALL provide a text input for the user to set their EDDN uploader ID.

#### Scenario: User sets uploader ID
- **WHEN** the user enters an uploader ID and submits it
- **THEN** the frontend SHALL call the backend to save the uploader ID to settings

#### Scenario: No uploader ID set
- **WHEN** no uploader ID is configured
- **THEN** the panel SHALL show a notice that the uploader ID should be set before uploading

### Requirement: Display journal path
The frontend SHALL display the currently configured journal path.

#### Scenario: Auto-detected path
- **WHEN** the journal path was found via VDF scan
- **THEN** the panel SHALL display the path with an "Auto-detected" label

#### Scenario: Manually set path
- **WHEN** the journal path was set by the user
- **THEN** the panel SHALL display the path with a "Manual" label
