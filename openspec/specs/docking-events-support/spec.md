## Purpose

Submit DockingGranted and DockingDenied journal events to EDDN via their dedicated schemas.

## Requirements

### Requirement: Parse DockingGranted and DockingDenied journal events
The backend SHALL recognize `DockingGranted` and `DockingDenied` as reportable journal events and route them through the dedicated schema path.

#### Scenario: DockingGranted event detected in journal
- **WHEN** the watcher reads a journal line with `"event": "DockingGranted"`
- **THEN** the parser SHALL return a `ParsedEvent` with event type `DockingGranted`
- **AND** the watcher SHALL route it to the dedicated schema transform dispatch

#### Scenario: DockingDenied event detected in journal
- **WHEN** the watcher reads a journal line with `"event": "DockingDenied"`
- **THEN** the parser SHALL return a `ParsedEvent` with event type `DockingDenied`
- **AND** the watcher SHALL route it to the dedicated schema transform dispatch

#### Scenario: Docking events not in REPORTABLE_EVENTS
- **WHEN** `DockingGranted` or `DockingDenied` has not been added to `REPORTABLE_EVENTS`
- **THEN** that event SHALL NOT be processed for EDDN submission

### Requirement: Validate docking events against EDDN schema requirements
The backend SHALL validate docking events have all required fields before submission.

#### Scenario: Valid DockingGranted event
- **WHEN** a DockingGranted event contains `timestamp`, `MarketID`, and `StationName`
- **THEN** the backend SHALL consider the event valid

#### Scenario: Valid DockingDenied event
- **WHEN** a DockingDenied event contains `timestamp`, `MarketID`, `StationName`, and `Reason`
- **THEN** the backend SHALL consider the event valid

#### Scenario: DockingGranted missing required fields
- **WHEN** a DockingGranted event is missing any of `timestamp`, `MarketID`, or `StationName`
- **THEN** the backend SHALL reject the event

#### Scenario: DockingDenied missing required fields
- **WHEN** a DockingDenied event is missing any of `timestamp`, `MarketID`, `StationName`, or `Reason`
- **THEN** the backend SHALL reject the event

### Requirement: Transform DockingGranted to dockinggranted/1 schema
The backend SHALL transform a validated DockingGranted event into an EDDN message conforming to `https://eddn.edcd.io/schemas/dockinggranted/1`.

#### Scenario: Successful DockingGranted transform
- **WHEN** a valid DockingGranted event is transformed
- **THEN** the message SHALL contain `$schemaRef: "https://eddn.edcd.io/schemas/dockinggranted/1"`
- **AND** the payload SHALL include `timestamp`, `event: "DockingGranted"`, `MarketID`, `StationName`, `horizons`, and `odyssey`, plus `LandingPad` and `StationType` when present in the journal event
- **AND** the backend SHALL NOT augment `StarPos` or `StarSystem` (not part of this station-context schema)

### Requirement: Transform DockingDenied to dockingdenied/1 schema
The backend SHALL transform a validated DockingDenied event into an EDDN message conforming to `https://eddn.edcd.io/schemas/dockingdenied/1`.

#### Scenario: Successful DockingDenied transform
- **WHEN** a valid DockingDenied event is transformed
- **THEN** the message SHALL contain `$schemaRef: "https://eddn.edcd.io/schemas/dockingdenied/1"`
- **AND** the payload SHALL include `timestamp`, `event: "DockingDenied"`, `Reason`, `MarketID`, `StationName`, `horizons`, and `odyssey`, plus `StationType` when present in the journal event
- **AND** the `Reason_Localised` key SHALL be stripped while the base `Reason` field is preserved
