## Purpose

Submit validated Elite Dangerous journal events to the Elite Dangerous Data Network (EDDN) as anonymized, schema-conformant messages.
## Requirements
### Requirement: Validate events against EDDN journal/1 schema
The backend SHALL validate each reportable event against the appropriate EDDN schema before submission.

#### Scenario: Valid FSDJump event
- **WHEN** an FSDJump event contains required fields (`timestamp`, `StarSystem`, `SystemAddress`, `StarPos`, `JumpDist`, `FuelUsed`, `FuelLevel`)
- **THEN** the backend SHALL consider the event valid

#### Scenario: Event missing required fields
- **WHEN** an event is missing fields required by its EDDN schema
- **THEN** the backend SHALL log a validation error and skip the event

### Requirement: Strip EDDN-disallowed fields
The backend SHALL remove fields from journal events that EDDN does not accept before constructing the submission message.

#### Scenario: FSDJump with disallowed fields
- **WHEN** an FSDJump event contains fields such as `ActiveFine`, `Crew`, or other EDDN-disallowed fields
- **THEN** the backend SHALL remove those fields before submission

#### Scenario: Docked event with disallowed fields
- **WHEN** a Docked event contains fields not accepted by the EDDN journal/1 schema
- **THEN** the backend SHALL remove those fields before submission

### Requirement: Augment events with horizons and odyssey flags
The backend SHALL add `horizons` and `odyssey` boolean flags to every EDDN journal message, derived from the `LoadGame` event of the current session.

#### Scenario: LoadGame captured with horizons and odyssey true
- **WHEN** the watcher processes a `LoadGame` event with both expansions active
- **THEN** the backend SHALL set `horizons: true` and `odyssey: true` on all subsequent EDDN messages for that session

#### Scenario: No LoadGame event captured yet
- **WHEN** the watcher has not yet seen a `LoadGame` event in the current session
- **THEN** the backend SHALL default to `horizons: true` and `odyssey: true` (current standard assumption)

### Requirement: Construct EDDN message with proper header
The backend SHALL construct EDDN messages with the required `$schemaRef`, `header`, and `message` structure.

#### Scenario: EDDN message construction
- **WHEN** a validated, stripped, and augmented event is ready for submission
- **THEN** the backend SHALL construct a message with `$schemaRef: "https://eddn.edcd.io/schemas/journal/1"`, `header` containing `uploaderID`, `softwareName`, `softwareVersion`, and `gatewayTimestamp`, and `message` containing the event payload

### Requirement: Submit events to EDDN via HTTP POST
The backend SHALL submit validated EDDN messages to `https://eddn.edcd.io:4430/upload/` via HTTP POST.

#### Scenario: Successful submission
- **WHEN** the backend POSTs a valid EDDN message
- **AND** EDDN responds with HTTP 200
- **THEN** the backend SHALL log success and emit a `upload_success` event to the frontend

#### Scenario: EDDN returns client error (4xx)
- **WHEN** EDDN responds with a 4xx status (other than 429)
- **THEN** the backend SHALL log the error and NOT retry the submission

### Requirement: Retry submissions with exponential backoff
The backend SHALL retry failed submissions (server errors, rate limits, timeouts) with exponential backoff.

#### Scenario: EDDN rate limit (429)
- **WHEN** EDDN responds with HTTP 429
- **THEN** the backend SHALL retry after an exponential delay (max 3 retries)

#### Scenario: EDDN server error (5xx)
- **WHEN** EDDN responds with HTTP 5xx
- **THEN** the backend SHALL retry after an exponential delay (max 3 retries)

#### Scenario: Network timeout
- **WHEN** the HTTP request times out
- **THEN** the backend SHALL retry after an exponential delay (max 3 retries)

#### Scenario: All retries exhausted
- **WHEN** the maximum number of retries is reached without success
- **THEN** the backend SHALL log failure and emit an `upload_failed` event to the frontend

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

### Requirement: Configurable uploader ID and software info
The backend SHALL use configurable `uploaderID`, `softwareName`, and `softwareVersion` values in EDDN message headers.

#### Scenario: Default values
- **WHEN** no custom values are configured
- **THEN** the backend SHALL use `softwareName: "ED Journal Monitor Decky"` and `softwareVersion` from `package.json`/`plugin.json`

#### Scenario: Custom uploader ID
- **WHEN** the user configures a custom `uploaderID` via the UI
- **THEN** the backend SHALL use that value in the EDDN header

### Requirement: Track current body from journal events
The backend SHALL track the current body name and body ID from journal events in session state, following `codexentry-README.md`'s rules: recorded from `ApproachBody`, `Location`, and `CarrierJump`; cleared on `LeaveBody`, `FSDJump`, and at a session boundary (`Fileheader`); and left untouched by `SupercruiseEntry`.

#### Scenario: ApproachBody records the body
- **WHEN** the parser processes an `ApproachBody` event carrying a body name and body ID
- **THEN** the backend SHALL record both as the current journal body

#### Scenario: Location records the body
- **WHEN** the parser processes a `Location` or `CarrierJump` event that carries a body name and body ID
- **THEN** the backend SHALL record both as the current journal body

#### Scenario: LeaveBody and FSDJump clear the body
- **WHEN** the parser processes a `LeaveBody` or `FSDJump` event
- **THEN** the backend SHALL clear both the tracked body name and body ID

#### Scenario: SupercruiseEntry does not clear the body
- **WHEN** the parser processes a `SupercruiseEntry` event while a body is tracked
- **THEN** the backend SHALL leave the tracked body name and body ID unchanged, because the player can re-descend to the body without a fresh `ApproachBody` event

#### Scenario: New session clears the body
- **WHEN** the parser processes a `Fileheader` event
- **THEN** the backend SHALL clear the tracked body name and body ID

### Requirement: Read the current body name from Status.json
The backend SHALL read `BodyName` from `Status.json` in the journal directory when processing a `CodexEntry` event, and SHALL treat the value as usable only when `Status.json`'s own `timestamp` is within a bounded window of the `CodexEntry` event's timestamp. Any failure to obtain a trustworthy value MUST resolve to "no status body name" without raising and without affecting submission of the rest of the message.

#### Scenario: Status body name read for a live codex entry
- **WHEN** a `CodexEntry` is processed and `Status.json` contains a `BodyName` with a timestamp within the freshness window of the event
- **THEN** the backend SHALL use that value as the status body name

#### Scenario: Stale Status.json rejected
- **WHEN** a `CodexEntry` is processed whose timestamp differs from `Status.json`'s timestamp by more than the freshness window — for example a codex entry replayed from a previous session during catch-up
- **THEN** the backend SHALL treat the status body name as unavailable

#### Scenario: Status.json missing, unreadable, or malformed
- **WHEN** `Status.json` is absent, unreadable, not a JSON object, mid-write on every attempt, has no `timestamp`, or has an empty or non-string `BodyName`
- **THEN** the backend SHALL treat the status body name as unavailable and SHALL still submit the codex entry

#### Scenario: Timestamp without a UTC offset
- **WHEN** either `Status.json`'s timestamp or the event's timestamp carries no UTC offset
- **THEN** the backend SHALL read it as UTC and apply the freshness window to it, rather than failing the codex entry

#### Scenario: Status.json read only for codex entries
- **WHEN** the watcher processes any event other than `CodexEntry`
- **THEN** the backend SHALL NOT read `Status.json`

### Requirement: Cross-check CodexEntry body fields before submission
The backend SHALL set the codexentry/1 message's `BodyName` only from the `Status.json` value, and `BodyID` only when the tracked journal body name matches that value. In every other case both keys MUST be absent from the message — never present with `null`, `""`, or an un-cross-checked journal value.

#### Scenario: Status body name matches the tracked journal body
- **WHEN** a `CodexEntry` is transformed while the status body name is set and equals the tracked journal body name, and a journal body ID is known
- **THEN** the message SHALL carry `BodyName` set to the status body name and `BodyID` set to the tracked journal body ID

#### Scenario: Status body name disagrees with the tracked journal body
- **WHEN** a `CodexEntry` is transformed while the status body name is set but differs from the tracked journal body name — the close-orbiting binary case
- **THEN** the message SHALL carry `BodyName` set to the status body name and SHALL NOT contain a `BodyID` key

#### Scenario: No status body name
- **WHEN** a `CodexEntry` is transformed while no status body name is available
- **THEN** the message SHALL contain neither a `BodyName` key nor a `BodyID` key, even if the journal event itself supplied them

#### Scenario: Journal-supplied body fields are not trusted
- **WHEN** the `CodexEntry` journal event itself carries `BodyName` and/or `BodyID`
- **THEN** the backend SHALL discard those values and apply the cross-check rules above, so a submitted `BodyID` is always one whose body name both sources agree on
