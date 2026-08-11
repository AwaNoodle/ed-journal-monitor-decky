## MODIFIED Requirements

### Requirement: Display recent errors panel
Failed uploads SHALL be surfaced within the merged Data flow activity feed rather than in a separate panel section, so that a failure is read alongside the attempts that surrounded it. Each failure row SHALL show its details, including the target the failed upload was sent to. Failures from any target (EDDN and EDSM) SHALL appear. The Data flow section's collapsed header SHALL carry the failure count, and the section SHALL start expanded when that count is greater than zero.

#### Scenario: Errors exist
- **WHEN** there are failed entries in the activity log
- **THEN** the merged feed SHALL display each failure showing: event type, target, timestamp (local time), error type, and error message

#### Scenario: EDSM failure shown
- **WHEN** an EDSM submission fails (e.g. a bad-key `203`) and is recorded as a failure entry
- **THEN** the merged feed SHALL show that entry tagged with the `edsm` target and its message

#### Scenario: Failures distinguishable within the feed
- **WHEN** the merged feed contains both successful and failed entries
- **THEN** failures SHALL remain visually distinguishable from successes by their status marker and error detail

#### Scenario: No errors
- **WHEN** there are no failed entries in the activity log
- **THEN** the Data flow header SHALL show a zero failure count and the section SHALL start collapsed

#### Scenario: New error arrives
- **WHEN** the backend emits an `activity_update` event with `outcome: "failure"`
- **THEN** the frontend SHALL add the error to the merged feed and the Data flow header failure count SHALL increase

### Requirement: Display recent activity feed
The frontend SHALL display, within the Data flow section, a single time-ordered feed of recent upload attempts covering both successes and failures, each row tagged with the target it was sent to. The feed SHALL show the last 10 attempts.

#### Scenario: Activity entries exist
- **WHEN** there are entries in the activity log
- **THEN** the feed SHALL display up to 10 most recent entries, each with status icon (✅ or ❌), event type, target badge, and timestamp (local time)

#### Scenario: Same event to both targets shows two rows
- **WHEN** an event is sent to both EDDN and EDSM
- **THEN** the feed SHALL show two rows for it — one tagged `eddn` and one tagged `edsm` — recorded when each target reports

#### Scenario: No activity
- **WHEN** the activity log is empty
- **THEN** the feed SHALL display "No activity yet" message

#### Scenario: New activity arrives
- **WHEN** the backend emits an `activity_update` event
- **THEN** the frontend SHALL add the entry to the feed (pushing out the oldest if more than 10)

#### Scenario: Feed reachable without leaving the flight view
- **WHEN** the panel is opened and no failures have occurred
- **THEN** the feed SHALL be collapsed behind the Data flow header, contributing no focus stops until expanded
