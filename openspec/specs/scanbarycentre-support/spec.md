## ADDED Requirements

### Requirement: Parse ScanBaryCentre journal events
The backend SHALL recognize `ScanBaryCentre` as a reportable journal event and route it through the dedicated schema path.

#### Scenario: ScanBaryCentre event detected in journal
- **WHEN** the watcher reads a journal line with `"event": "ScanBaryCentre"`
- **THEN** the parser SHALL return a `ParsedEvent` with event type `ScanBaryCentre`
- **AND** the watcher SHALL route it to the dedicated schema transform dispatch

#### Scenario: ScanBaryCentre not in REPORTABLE_EVENTS
- **WHEN** `ScanBaryCentre` has not been added to `REPORTABLE_EVENTS`
- **THEN** the event SHALL NOT be processed for EDDN submission

### Requirement: Validate ScanBaryCentre against EDDN schema requirements
The backend SHALL validate `ScanBaryCentre` events have all required fields before submission.

#### Scenario: Valid ScanBaryCentre event
- **WHEN** a ScanBaryCentre event contains `timestamp`, `SystemAddress`, and `BodyID`
- **AND** `StarPos` is available via session-state augmentation (matching `SystemAddress`)
- **THEN** the backend SHALL consider the event valid

#### Scenario: ScanBaryCentre missing required fields
- **WHEN** a ScanBaryCentre event is missing any of `timestamp`, `SystemAddress`, or `BodyID`
- **THEN** the backend SHALL reject the event

#### Scenario: ScanBaryCentre with StarPos augmentation failure
- **WHEN** session state has no cached `StarPos`, or `SystemAddress` does not match the cached position
- **THEN** the backend SHALL reject the event because `StarPos` is required by the schema

### Requirement: Transform ScanBaryCentre to scanbarycentre/1 schema
The backend SHALL transform a validated ScanBaryCentre event into an EDDN message conforming to `https://eddn.edcd.io/schemas/scanbarycentre/1`.

#### Scenario: Successful transform
- **WHEN** a valid ScanBaryCentre event is transformed
- **THEN** the message SHALL contain `$schemaRef: "https://eddn.edcd.io/schemas/scanbarycentre/1"`
- **AND** the payload SHALL include `timestamp`, `event: "ScanBaryCentre"`, `StarSystem`, `StarPos`, `SystemAddress`, `BodyID`, `horizons`, and `odyssey`
- **AND** `StarPos` SHALL be augmented from session state when not present in the journal event
- **AND** `StarSystem` SHALL be augmented from session state when not present in the journal event

#### Scenario: Localised and disallowed fields stripped
- **WHEN** a ScanBaryCentre event contains any `*_Localised` keys or EDDN-disallowed fields
- **THEN** the backend SHALL remove them before submission
