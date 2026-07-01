## MODIFIED Requirements

### Requirement: Track and report upload statistics
The backend SHALL track per-target counts of successful and failed uploads and report them to the frontend as a target-keyed map aggregated by iterating the registered submission consumers (EDDN is one target among several). The map MUST NOT use hardcoded target keys, so that adding a further target requires no change to the reporting shape. The backend SHALL reset these statistics when Elite Dangerous starts a new session (transition from not running to running), so that counters reflect per-session totals.

#### Scenario: Statistics emitted on each upload

- **WHEN** an upload attempt completes (success or failure) for any target
- **THEN** the backend SHALL emit a `status_update` event carrying a per-target map of successful and failed counts, with that target's entry updated

#### Scenario: EDDN counts are isolated from other targets

- **WHEN** a non-EDDN target's upload succeeds or fails
- **THEN** the EDDN target's success and fail counts SHALL be unchanged

#### Scenario: Statistics reset on ED start

- **WHEN** Elite Dangerous transitions from not running to running (`set_ed_running(true)` is called and the previous state was `ed_running: false`)
- **THEN** the backend SHALL reset every target's success count to 0 and fail count to 0, and last upload time to null and last upload event to null
- **THEN** the backend SHALL emit a `status_update` event with the zeroed per-target statistics

#### Scenario: Statistics NOT reset on ED stop

- **WHEN** Elite Dangerous stops running (`set_ed_running(false)` is called)
- **THEN** the upload statistics SHALL NOT be modified
