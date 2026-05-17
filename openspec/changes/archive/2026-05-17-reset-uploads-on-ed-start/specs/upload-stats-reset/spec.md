## ADDED Requirements

### Requirement: Reset upload statistics on Elite Dangerous start
The backend SHALL reset all upload statistics (success count, fail count, last upload time, last upload event) when Elite Dangerous transitions from not running to running.

#### Scenario: ED starts — counters reset to zero
- **WHEN** `set_ed_running(true)` is called and the previous state was `ed_running: false`
- **THEN** the success count SHALL be set to 0
- **THEN** the fail count SHALL be set to 0
- **THEN** the last upload time SHALL be set to null
- **THEN** the last upload event SHALL be set to null

#### Scenario: ED starts — status_update emitted with zeroed stats
- **WHEN** `set_ed_running(true)` resets the statistics
- **THEN** a `status_update` event SHALL be emitted to the frontend with the zeroed statistics

#### Scenario: ED stops — counters are NOT reset
- **WHEN** `set_ed_running(false)` is called
- **THEN** the upload statistics SHALL NOT be modified

#### Scenario: No-op call — counters are NOT reset
- **WHEN** `set_ed_running(true)` is called but `ed_running` is already `true`
- **THEN** the upload statistics SHALL NOT be modified

#### Scenario: Activity log is NOT cleared on reset
- **WHEN** upload statistics are reset on ED start
- **THEN** the activity log entries SHALL remain unchanged
