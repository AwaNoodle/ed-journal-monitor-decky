## MODIFIED Requirements

### Requirement: Display plugin status panel
The frontend SHALL display a Decky UI panel showing the current state of the journal monitor, including a Diagnostics section.

#### Scenario: Plugin idle (ED not running)
- **WHEN** Elite Dangerous is not running
- **THEN** the panel SHALL show status "Idle — waiting for Elite Dangerous"

#### Scenario: Plugin watching (ED running)
- **WHEN** Elite Dangerous is running and the watcher is active
- **THEN** the panel SHALL show status "Watching — uploading journal events"

#### Scenario: Journal path not found
- **WHEN** the journal path is not detected and no manual path is set
- **THEN** the panel SHALL show status "Journal path not found" with an option to set it manually

## ADDED Requirements

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
