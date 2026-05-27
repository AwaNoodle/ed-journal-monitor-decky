## ADDED Requirements

### Requirement: Parse FSSAllBodiesFound journal events
The backend SHALL recognize `FSSAllBodiesFound` as a reportable journal event and process it through the dedicated schema routing path.

#### Scenario: FSSAllBodiesFound event detected in journal
- **WHEN** the watcher reads a journal line with `"event": "FSSAllBodiesFound"`
- **THEN** the parser SHALL return a `ParsedEvent` with event type `FSSAllBodiesFound`
- **THEN** the watcher SHALL route it to the dedicated schema transform dispatch

#### Scenario: FSSAllBodiesFound not in REPORTABLE_EVENTS
- **WHEN** `FSSAllBodiesFound` has not been added to `REPORTABLE_EVENTS`
- **THEN** the event SHALL NOT be processed for EDDN submission

### Requirement: Validate FSSAllBodiesFound against EDDN schema requirements
The backend SHALL validate `FSSAllBodiesFound` events have all required fields before submission.

#### Scenario: Valid FSSAllBodiesFound event
- **WHEN** an FSSAllBodiesFound event contains `timestamp`, `SystemName`, `SystemAddress`, and `Count`
- **AND** `StarPos` is available via session state augmentation (matching SystemAddress)
- **THEN** the backend SHALL consider the event valid

#### Scenario: FSSAllBodiesFound missing required fields
- **WHEN** an FSSAllBodiesFound event is missing any of `timestamp`, `SystemName`, `SystemAddress`, or `Count`
- **THEN** the backend SHALL reject the event

#### Scenario: FSSAllBodiesFound with StarPos augmentation failure
- **WHEN** session state has no cached StarPos, or SystemAddress does not match the cached position
- **THEN** the backend SHALL reject the event (StarPos is required by the schema)

### Requirement: Transform FSSAllBodiesFound to fssallbodiesfound/1 schema
The backend SHALL transform a validated FSSAllBodiesFound event into an EDDN message conforming to `https://eddn.edcd.io/schemas/fssallbodiesfound/1`.

#### Scenario: Successful transform
- **WHEN** a valid FSSAllBodiesFound event is transformed
- **THEN** the message SHALL contain `$schemaRef: "https://eddn.edcd.io/schemas/fssallbodiesfound/1"`
- **AND** the message payload SHALL include `timestamp`, `event: "FSSAllBodiesFound"`, `SystemName`, `StarPos`, `SystemAddress`, `Count`, `horizons`, and `odyssey`
- **AND** `Count` SHALL be passed through unchanged from the journal event
- **AND** `StarPos` SHALL be augmented from session state if not present in the journal event

#### Scenario: StarPos augmentation with SystemAddress cross-check
- **WHEN** the journal event lacks StarPos and session state has a cached position
- **AND** the event's SystemAddress matches the cached SystemAddress
- **THEN** StarPos SHALL be set from session state

#### Scenario: StarPos augmentation with SystemAddress mismatch
- **WHEN** the event's SystemAddress differs from the cached SystemAddress
- **THEN** StarPos SHALL NOT be augmented (the event should have been rejected during validation)

### Requirement: Submit FSSAllBodiesFound to EDDN
The backend SHALL submit the transformed FSSAllBodiesFound message to EDDN with game version and build headers.

#### Scenario: Successful submission
- **WHEN** the transformed message is submitted
- **THEN** the header SHALL include `gameversion` and `gamebuild` from session state (if available)
- **AND** the submitter SHALL POST to the EDDN upload endpoint
- **AND** on success, an `upload_success` event SHALL be emitted with event name `FSSAllBodiesFound`
