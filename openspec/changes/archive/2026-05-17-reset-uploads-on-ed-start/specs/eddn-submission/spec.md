## MODIFIED Requirements

### Requirement: Track and report upload statistics
The backend SHALL track counts of successful and failed uploads and report them to the frontend. The backend SHALL reset these statistics when Elite Dangerous starts a new session (transition from not running to running), so that counters reflect per-session totals.

#### Scenario: Statistics emitted on each upload
- **WHEN** an upload attempt completes (success or failure)
- **THEN** the backend SHALL emit a `status_update` event with total successful and failed counts

#### Scenario: Statistics reset on ED start
- **WHEN** Elite Dangerous transitions from not running to running (`set_ed_running(true)` is called and the previous state was `ed_running: false`)
- **THEN** the backend SHALL reset success count to 0, fail count to 0, last upload time to null, and last upload event to null
- **THEN** the backend SHALL emit a `status_update` event with the zeroed statistics

#### Scenario: Statistics NOT reset on ED stop
- **WHEN** Elite Dangerous stops running (`set_ed_running(false)` is called)
- **THEN** the upload statistics SHALL NOT be modified
