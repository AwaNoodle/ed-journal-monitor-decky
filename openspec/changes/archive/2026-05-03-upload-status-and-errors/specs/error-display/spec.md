## ADDED Requirements

### Requirement: Display recent errors panel
The frontend SHALL display a "Recent Errors" panel section showing the last 5 failed upload entries with details.

#### Scenario: Errors exist
- **WHEN** there are failed entries in the activity log
- **THEN** the panel SHALL display up to 5 most recent errors, each showing: event type, timestamp (local time), error type, and error message

#### Scenario: No errors
- **WHEN** there are no failed entries in the activity log
- **THEN** the panel SHALL display "No errors" message

#### Scenario: New error arrives
- **WHEN** the backend emits an `activity_update` event with `outcome: "failure"`
- **THEN** the frontend SHALL add the error to the display (pushing out the oldest if more than 5)

### Requirement: Display recent activity feed
The frontend SHALL display a "Recent Activity" panel section showing the last 10 upload attempts (success and failure) as a compact feed.

#### Scenario: Activity entries exist
- **WHEN** there are entries in the activity log
- **THEN** the panel SHALL display up to 10 most recent entries, each as a single line with status icon (✅ or ❌), event type, and timestamp (local time)

#### Scenario: No activity
- **WHEN** the activity log is empty
- **THEN** the panel SHALL display "No activity yet" message

#### Scenario: New activity arrives
- **WHEN** the backend emits an `activity_update` event
- **THEN** the frontend SHALL add the entry to the activity feed (pushing out the oldest if more than 10)

### Requirement: Enhance last upload display with event name
The frontend SHALL display the event name alongside the last upload timestamp.

#### Scenario: Last upload was a successful FSDJump
- **WHEN** the last successful upload was a FSDJump event
- **THEN** the "Last Upload" field SHALL show both the timestamp and the event name (e.g. "FSDJump — 14:32:05")

#### Scenario: No uploads yet
- **WHEN** no successful uploads have occurred
- **THEN** the "Last Upload" field SHALL display "No uploads yet"
