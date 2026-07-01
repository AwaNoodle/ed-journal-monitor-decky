## MODIFIED Requirements

### Requirement: Display recent errors panel
The frontend SHALL display a "Recent Errors" panel section showing the last 5 failed upload entries with details, including the target each failed upload was sent to. Failures from any target (EDDN and EDSM) SHALL appear.

#### Scenario: Errors exist
- **WHEN** there are failed entries in the activity log
- **THEN** the panel SHALL display up to 5 most recent errors, each showing: event type, target, timestamp (local time), error type, and error message

#### Scenario: EDSM failure shown
- **WHEN** an EDSM submission fails (e.g. a bad-key `203`) and is recorded as a failure entry
- **THEN** the Recent Errors panel SHALL show that entry tagged with the `edsm` target and its message

#### Scenario: No errors
- **WHEN** there are no failed entries in the activity log
- **THEN** the panel SHALL display "No errors" message

#### Scenario: New error arrives
- **WHEN** the backend emits an `activity_update` event with `outcome: "failure"`
- **THEN** the frontend SHALL add the error to the display (pushing out the oldest if more than 5)

### Requirement: Display recent activity feed
The frontend SHALL display a "Recent Activity" panel section showing the last 10 upload attempts (success and failure) as a compact feed, each row tagged with the target it was sent to.

#### Scenario: Activity entries exist
- **WHEN** there are entries in the activity log
- **THEN** the panel SHALL display up to 10 most recent entries, each as a single line with status icon (✅ or ❌), event type, target badge, and timestamp (local time)

#### Scenario: Same event to both targets shows two rows
- **WHEN** an event is sent to both EDDN and EDSM
- **THEN** the feed SHALL show two rows for it — one tagged `eddn` and one tagged `edsm` — recorded when each target reports

#### Scenario: No activity
- **WHEN** the activity log is empty
- **THEN** the panel SHALL display "No activity yet" message

#### Scenario: New activity arrives
- **WHEN** the backend emits an `activity_update` event
- **THEN** the frontend SHALL add the entry to the activity feed (pushing out the oldest if more than 10)
