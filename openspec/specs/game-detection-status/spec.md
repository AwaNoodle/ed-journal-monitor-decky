## Purpose

Detect and report whether Elite Dangerous is running and the journal watcher's status.

## Requirements

### Requirement: Backend tracks ED running state
The backend SHALL maintain an in-memory `ed_running` boolean that reflects whether Elite Dangerous is currently running.

#### Scenario: Plugin initializes
- **WHEN** the plugin backend starts
- **THEN** `ed_running` SHALL default to `false`

#### Scenario: Frontend reports ED started
- **WHEN** the frontend calls `set_ed_running(true)`
- **THEN** the backend SHALL set `ed_running` to `true`

#### Scenario: Frontend reports ED stopped
- **WHEN** the frontend calls `set_ed_running(false)`
- **THEN** the backend SHALL set `ed_running` to `false`

### Requirement: set_ed_running callable
The backend SHALL expose a `set_ed_running` callable that accepts a boolean argument.

#### Scenario: Callable invoked with true
- **WHEN** `set_ed_running(true)` is called
- **THEN** the backend SHALL update `ed_running` to `true`
- **THEN** the backend SHALL emit an `ed_state_change` event with `{ed_running: true}`

#### Scenario: Callable invoked with false
- **WHEN** `set_ed_running(false)` is called
- **THEN** the backend SHALL update `ed_running` to `false`
- **THEN** the backend SHALL emit an `ed_state_change` event with `{ed_running: false}`

### Requirement: ed_state_change event
The backend SHALL emit a `ed_state_change` event whenever the ED running state changes.

#### Scenario: ED starts
- **WHEN** `set_ed_running(true)` is called and the previous state was `false`
- **THEN** the backend SHALL emit `ed_state_change` with `{ed_running: true}`

#### Scenario: ED stops
- **WHEN** `set_ed_running(false)` is called and the previous state was `true`
- **THEN** the backend SHALL emit `ed_state_change` with `{ed_running: false}`

#### Scenario: Redundant call (no state change)
- **WHEN** `set_ed_running(true)` is called but `ed_running` is already `true`
- **THEN** the backend SHALL NOT emit an `ed_state_change` event

### Requirement: get_status returns ed_running
The `get_status` callable SHALL include the `ed_running` field in its response.

#### Scenario: Status requested while ED is running
- **WHEN** `get_status()` is called and `ed_running` is `true`
- **THEN** the response SHALL include `"ed_running": true`

#### Scenario: Status requested while ED is not running
- **WHEN** `get_status()` is called and `ed_running` is `false`
- **THEN** the response SHALL include `"ed_running": false`

### Requirement: Two independent status fields in UI
The UI SHALL display two independent status fields labeled "ED Status" and "Journal Status".

#### Scenario: ED not running, journal not found
- **WHEN** `ed_running` is `false` and no journal path is set
- **THEN** "ED Status" SHALL display "⚪ Not Running"
- **THEN** "Journal Status" SHALL display "🔍 Not Found"

#### Scenario: ED running, journal not found
- **WHEN** `ed_running` is `true` and no journal path is set
- **THEN** "ED Status" SHALL display "🟢 Running"
- **THEN** "Journal Status" SHALL display "🔍 Not Found"

#### Scenario: ED not running, journal found, watcher not running
- **WHEN** `ed_running` is `false` and a journal path exists but the watcher is not running
- **THEN** "ED Status" SHALL display "⚪ Not Running"
- **THEN** "Journal Status" SHALL display "📂 Found" (neutral, no warning)

#### Scenario: ED running, journal found, watcher not running
- **WHEN** `ed_running` is `true` and a journal path exists but the watcher is not running
- **THEN** "ED Status" SHALL display "🟢 Running"
- **THEN** "Journal Status" SHALL display "⚠️ Found, Not Watching"

#### Scenario: ED running, watcher active
- **WHEN** `ed_running` is `true` and the watcher is running
- **THEN** "ED Status" SHALL display "🟢 Running"
- **THEN** "Journal Status" SHALL display "🟢 Watching"

#### Scenario: ED not running, watcher active
- **WHEN** `ed_running` is `false` and the watcher is running
- **THEN** "ED Status" SHALL display "⚪ Not Running"
- **THEN** "Journal Status" SHALL display "🟢 Watching"

### Requirement: UI listens to ed_state_change event
The frontend SHALL listen for the `ed_state_change` backend event and update the ED Status display in real-time.

#### Scenario: Event received with ed_running true
- **WHEN** the frontend receives an `ed_state_change` event with `{ed_running: true}`
- **THEN** the ED Status field SHALL update to "🟢 Running"

#### Scenario: Event received with ed_running false
- **WHEN** the frontend receives an `ed_state_change` event with `{ed_running: false}`
- **THEN** the ED Status field SHALL update to "⚪ Not Running"
