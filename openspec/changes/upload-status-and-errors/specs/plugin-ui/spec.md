## MODIFIED Requirements

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
