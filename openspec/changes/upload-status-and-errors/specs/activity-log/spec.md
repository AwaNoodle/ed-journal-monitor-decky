## ADDED Requirements

### Requirement: Maintain in-memory activity log
The backend SHALL maintain a circular buffer of the last 50 upload activity entries, stored in a dedicated `ActivityLog` module.

#### Scenario: Successful upload recorded
- **WHEN** the submitter successfully uploads an event to EDDN
- **THEN** the ActivityLog SHALL append an entry with `outcome: "success"`, `event_type`, `timestamp`, and `error_type: null`, `error_message: null`, `http_status: null`

#### Scenario: Failed upload recorded
- **WHEN** the submitter fails to upload an event (after all retries exhausted)
- **THEN** the ActivityLog SHALL append an entry with `outcome: "failure"`, `event_type`, `timestamp`, `error_type` (one of "http_error", "network_error", "validation_error"), `error_message`, and `http_status` if applicable

#### Scenario: Buffer at capacity
- **WHEN** 50 entries already exist and a new entry is appended
- **THEN** the oldest entry SHALL be discarded and the new entry added

#### Scenario: Plugin restart
- **WHEN** the plugin restarts
- **THEN** the ActivityLog SHALL start empty (no persistence)

### Requirement: Expose activity log via callable
The backend SHALL provide a `get_recent_activity` callable that returns recent activity entries.

#### Scenario: Fetch all recent activity
- **WHEN** the frontend calls `get_recent_activity` with no arguments
- **THEN** the backend SHALL return the last 50 entries (or fewer if less are available) as an array, newest first

#### Scenario: Fetch recent activity with limit
- **WHEN** the frontend calls `get_recent_activity` with a `limit` parameter (e.g. 10)
- **THEN** the backend SHALL return at most that many entries, newest first

#### Scenario: Fetch only errors
- **WHEN** the frontend calls `get_recent_activity` with `outcome: "failure"` filter
- **THEN** the backend SHALL return only entries where `outcome` is `"failure"`, newest first, up to the limit

### Requirement: Emit real-time activity updates
The backend SHALL emit an `activity_update` event to the frontend each time a new entry is added to the activity log.

#### Scenario: Activity entry added
- **WHEN** a new entry is appended to the ActivityLog
- **THEN** the backend SHALL emit an `activity_update` event containing the new entry

### Requirement: Activity entry structure
Each activity entry SHALL be a dict with the following fields: `timestamp` (ISO 8601 string), `event_type` (string, e.g. "FSDJump"), `outcome` ("success" or "failure"), `error_type` (string or null: "http_error", "network_error", "validation_error"), `error_message` (string or null), `http_status` (integer or null).

#### Scenario: Success entry structure
- **WHEN** a successful upload is recorded
- **THEN** the entry SHALL have `outcome: "success"`, `error_type: null`, `error_message: null`, `http_status: null`, and populated `timestamp` and `event_type`

#### Scenario: HTTP error entry structure
- **WHEN** a failed upload due to HTTP error is recorded
- **THEN** the entry SHALL have `outcome: "failure"`, `error_type: "http_error"`, `error_message` with the HTTP reason, and `http_status` with the status code

#### Scenario: Network error entry structure
- **WHEN** a failed upload due to network/timeout error is recorded
- **THEN** the entry SHALL have `outcome: "failure"`, `error_type: "network_error"`, `error_message` with the exception message, and `http_status: null`
