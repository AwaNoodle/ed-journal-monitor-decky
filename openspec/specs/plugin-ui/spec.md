## Requirements

### Requirement: Display plugin status panel
The frontend SHALL display a Decky UI panel showing the current state of the journal monitor with two independent status fields.

#### Scenario: Plugin idle (ED not running)
- **WHEN** Elite Dangerous is not running and the watcher is not running
- **THEN** the panel SHALL show "ED Status" as "⚪ Not Running"
- **THEN** the panel SHALL show "Journal Status" as "📂 Found" (if journal path exists) or "🔍 Not Found" (if no path)

#### Scenario: Plugin watching (ED running)
- **WHEN** Elite Dangerous is running and the watcher is active
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "🟢 Watching & Uploading"

#### Scenario: Journal path not found
- **WHEN** the journal path is not detected and no manual path is set
- **THEN** "Journal Status" SHALL display "🔍 Not Found"

#### Scenario: ED running but watcher not active
- **WHEN** Elite Dangerous is running and the watcher is not running and a journal path exists
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "⚠️ Found, Not Watching"

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

### Requirement: Display diagnostics section
The frontend SHALL display a Diagnostics section in the panel with a detailed logging toggle and a bundle creation button.

#### Scenario: Diagnostics section visible
- **WHEN** the plugin panel is displayed
- **THEN** a Diagnostics section SHALL be visible with a "Detailed Logging" toggle and a "Create Diagnostic Bundle" button

#### Scenario: Detailed logging toggle
- **WHEN** the user toggles "Detailed Logging" on
- **THEN** the frontend SHALL call `set_detailed_logging(true)`
- **WHEN** the user toggles "Detailed Logging" off
- **THEN** the frontend SHALL call `set_detailed_logging(false)`

#### Scenario: Create diagnostic bundle
- **WHEN** the user clicks "Create Diagnostic Bundle"
- **THEN** the frontend SHALL call `create_diagnostics()`
- **THEN** the panel SHALL display the zip file path

#### Scenario: Bundle creation fails
- **WHEN** `create_diagnostics()` returns `{ "success": false }`
- **THEN** the panel SHALL display an error message
