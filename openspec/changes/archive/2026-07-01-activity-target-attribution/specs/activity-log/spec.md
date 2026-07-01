## MODIFIED Requirements

### Requirement: Maintain in-memory activity log
The backend SHALL maintain a circular buffer of the last 50 upload activity entries, stored in a dedicated `ActivityLog` module. Entries SHALL be recorded for any submission target (EDDN and EDSM), each tagged with the target it was sent to.

#### Scenario: Successful EDDN upload recorded
- **WHEN** the EDDN submitter successfully uploads an event
- **THEN** the ActivityLog SHALL append an entry with `outcome: "success"`, `target: "eddn"`, `event_type`, `timestamp`, and `error_type: null`, `error_message: null`, `http_status: null`

#### Scenario: Failed EDDN upload recorded
- **WHEN** the EDDN submitter fails to upload an event (after all retries exhausted)
- **THEN** the ActivityLog SHALL append an entry with `outcome: "failure"`, `target: "eddn"`, `event_type`, `timestamp`, `error_type` (one of "http_error", "network_error", "validation_error"), `error_message`, and `http_status` if applicable

#### Scenario: EDSM batch success records one entry per event
- **WHEN** an EDSM batch receives a terminal success response
- **THEN** the ActivityLog SHALL append one entry per event in that batch, each with `outcome: "success"`, `target: "edsm"`, its `event_type`, and `timestamp`

#### Scenario: EDSM fatal response records failures per event
- **WHEN** an EDSM batch receives a terminal fatal response (a 2xx `msgnum` such as 203)
- **THEN** the ActivityLog SHALL append one failure entry per event in that batch, each with `outcome: "failure"`, `target: "edsm"`, `error_type: "edsm"`, and `error_message` containing the `msgnum` and message

#### Scenario: EDSM transient response records nothing
- **WHEN** an EDSM batch receives a transient response (a 5xx `msgnum` or a network error) and the events are retained for retry
- **THEN** the ActivityLog SHALL NOT append entries for that batch until it settles with a terminal response

#### Scenario: Buffer at capacity
- **WHEN** 50 entries already exist and a new entry is appended
- **THEN** the oldest entry SHALL be discarded and the new entry added

#### Scenario: Plugin restart
- **WHEN** the plugin restarts
- **THEN** the ActivityLog SHALL start empty (no persistence)

### Requirement: Activity entry structure
Each activity entry SHALL be a dict with the following fields: `timestamp` (ISO 8601 string), `event_type` (string, e.g. "FSDJump"), `target` (`UploadTarget`: "eddn" or "edsm"), `outcome` ("success" or "failure"), `error_type` (string or null: "http_error", "network_error", "validation_error", "edsm"), `error_message` (string or null), `http_status` (integer or null).

#### Scenario: Success entry structure
- **WHEN** a successful upload is recorded
- **THEN** the entry SHALL have `outcome: "success"`, a `target` of "eddn" or "edsm", `error_type: null`, `error_message: null`, `http_status: null`, and populated `timestamp` and `event_type`

#### Scenario: EDDN HTTP error entry structure
- **WHEN** a failed EDDN upload due to HTTP error is recorded
- **THEN** the entry SHALL have `outcome: "failure"`, `target: "eddn"`, `error_type: "http_error"`, `error_message` with the HTTP reason, and `http_status` with the status code

#### Scenario: EDDN network error entry structure
- **WHEN** a failed EDDN upload due to network/timeout error is recorded
- **THEN** the entry SHALL have `outcome: "failure"`, `target: "eddn"`, `error_type: "network_error"`, `error_message` with the exception message, and `http_status: null`

#### Scenario: EDSM error entry structure
- **WHEN** a failed EDSM submission is recorded
- **THEN** the entry SHALL have `outcome: "failure"`, `target: "edsm"`, `error_type: "edsm"`, `error_message` containing the `msgnum` and EDSM message, and `http_status: null`
