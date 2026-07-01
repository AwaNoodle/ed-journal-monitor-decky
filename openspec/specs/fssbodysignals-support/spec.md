## Purpose

Submit FSSBodySignals journal events to EDDN via the fssbodysignals/1 schema.

## Requirements

### Requirement: Parse FSSBodySignals journal events
The backend SHALL recognize `FSSBodySignals` as a reportable journal event and route it through the dedicated schema path.

#### Scenario: FSSBodySignals event detected in journal
- **WHEN** the watcher reads a journal line with `"event": "FSSBodySignals"`
- **THEN** the parser SHALL return a `ParsedEvent` with event type `FSSBodySignals`
- **AND** the watcher SHALL route it to the dedicated schema transform dispatch

#### Scenario: FSSBodySignals not in REPORTABLE_EVENTS
- **WHEN** `FSSBodySignals` has not been added to `REPORTABLE_EVENTS`
- **THEN** the event SHALL NOT be processed for EDDN submission

### Requirement: Validate FSSBodySignals against EDDN schema requirements
The backend SHALL validate `FSSBodySignals` events have all required fields before submission.

#### Scenario: Valid FSSBodySignals event
- **WHEN** an FSSBodySignals event contains `timestamp`, `BodyName`, `BodyID`, `SystemAddress`, and `Signals`
- **AND** `StarSystem` and `StarPos` are available via session-state augmentation (matching `SystemAddress`)
- **THEN** the backend SHALL consider the event valid

#### Scenario: FSSBodySignals missing required fields
- **WHEN** an FSSBodySignals event is missing any of `timestamp`, `BodyName`, `BodyID`, `SystemAddress`, or `Signals`
- **THEN** the backend SHALL reject the event

#### Scenario: FSSBodySignals with augmentation failure
- **WHEN** session state has no cached `StarPos`/`StarSystem`, or `SystemAddress` does not match the cached position
- **THEN** the backend SHALL reject the event because `StarSystem` and `StarPos` are required by the schema

### Requirement: Transform FSSBodySignals to fssbodysignals/1 schema
The backend SHALL transform a validated FSSBodySignals event into an EDDN message conforming to `https://eddn.edcd.io/schemas/fssbodysignals/1`.

#### Scenario: Successful transform
- **WHEN** a valid FSSBodySignals event is transformed
- **THEN** the message SHALL contain `$schemaRef: "https://eddn.edcd.io/schemas/fssbodysignals/1"`
- **AND** the payload SHALL include `timestamp`, `event: "FSSBodySignals"`, `BodyName`, `BodyID`, `SystemAddress`, `Signals`, `StarSystem`, `StarPos`, `horizons`, and `odyssey`
- **AND** `StarSystem` and `StarPos` SHALL be augmented from session state when not present in the journal event

#### Scenario: Nested Localised fields stripped from Signals
- **WHEN** an FSSBodySignals event contains `*_Localised` keys inside the `Signals[]` array (e.g. `Type_Localised`)
- **THEN** the backend SHALL remove all `*_Localised` keys at every nesting level before submission
- **AND** the base `Type` field in each signal SHALL be preserved
