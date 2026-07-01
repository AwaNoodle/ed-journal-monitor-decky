## Purpose

Package logs, settings, and runtime state into a downloadable diagnostic bundle for offline troubleshooting.

## Requirements

### Requirement: Create diagnostic bundle
The system SHALL provide a `create_diagnostics()` callable that packages plugin log, settings, runtime state, and metadata into a zip file.

#### Scenario: Successful bundle creation
- **WHEN** the frontend calls `create_diagnostics()`
- **THEN** the system SHALL create a zip file at `DECKY_PLUGIN_SETTINGS_DIR/ed-jm-diagnostics.zip`
- **THEN** the zip SHALL contain `plugin.log`, `settings.json`, `runtime_state.json`, and `plugin.json`
- **THEN** the callable SHALL return `{ "success": true, "path": "<zip_path>", "size": <bytes> }`

#### Scenario: Log file missing
- **WHEN** the plugin log file does not exist at `DECKY_PLUGIN_LOG`
- **THEN** the system SHALL still create the bundle, omitting `plugin.log` from the zip
- **THEN** the callable SHALL return `{ "success": true, "path": "<zip_path>", "size": <bytes> }`

### Requirement: Runtime state snapshot
The `runtime_state.json` in the bundle SHALL capture a snapshot of live plugin state at the time of creation.

#### Scenario: Runtime state contents
- **WHEN** a diagnostic bundle is created
- **THEN** `runtime_state.json` SHALL include: watcher running status, journal path and source, submitter stats (success/fail counts), file positions, known files, poll interval, Python version, and Decky version

### Requirement: Bundle overwrites on each creation
The system SHALL overwrite any previously existing diagnostic bundle on each call.

#### Scenario: Repeated creation
- **WHEN** `create_diagnostics()` is called and a previous zip exists
- **THEN** the previous zip SHALL be replaced with the new bundle

### Requirement: Bundle uses stdlib only
The diagnostic bundle creation SHALL use only Python stdlib modules (`zipfile`, `json`, `os`, `pathlib`).

#### Scenario: No external dependencies
- **WHEN** the diagnostics module is imported
- **THEN** it SHALL NOT import any third-party packages
