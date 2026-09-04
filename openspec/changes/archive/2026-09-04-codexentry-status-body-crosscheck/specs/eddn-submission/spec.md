## ADDED Requirements

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
