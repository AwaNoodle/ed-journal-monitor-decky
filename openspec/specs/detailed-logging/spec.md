## Purpose

Let the user toggle verbose (DEBUG) backend logging for troubleshooting, persisted across restarts.

## Requirements

### Requirement: Toggle detailed logging
The system SHALL provide a `set_detailed_logging(enabled)` callable that adjusts the `decky.logger` log level.

#### Scenario: Enable detailed logging
- **WHEN** the frontend calls `set_detailed_logging(true)`
- **THEN** the system SHALL set `decky.logger` level to DEBUG
- **THEN** the setting SHALL be persisted in plugin settings

#### Scenario: Disable detailed logging
- **WHEN** the frontend calls `set_detailed_logging(false)`
- **THEN** the system SHALL set `decky.logger` level to INFO
- **THEN** the setting SHALL be persisted in plugin settings

### Requirement: Default logging level
The system SHALL default to INFO log level when no detailed logging preference is set.

#### Scenario: First run with no saved preference
- **WHEN** the plugin loads and `detailed_logging` is not in settings
- **THEN** `decky.logger` level SHALL be INFO

#### Scenario: Plugin restart with saved preference
- **WHEN** the plugin loads and `detailed_logging` is true in settings
- **THEN** `decky.logger` level SHALL be set to DEBUG
