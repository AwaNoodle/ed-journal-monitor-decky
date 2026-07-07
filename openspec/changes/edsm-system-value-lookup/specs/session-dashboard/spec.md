## ADDED Requirements

### Requirement: System value display in the Session metric area

The Session section SHALL present an EDSM-sourced system value display for the current system within the metric area, showing the total estimated scan value and the top priority bodies from the `edsm-system-lookup` value summary. The display MUST be attributed to EDSM, MUST convey that the figure is an estimate/floor, and MUST render a neutral state when a value is unavailable.

#### Scenario: Value shown for the current system

- **WHEN** an EDSM system value summary is available for the current system
- **THEN** the metric area SHALL show the total estimated value and the top priority bodies, labelled as EDSM-sourced

#### Scenario: Neutral state when value unavailable

- **WHEN** auto-lookups are disabled, or the value is in flight or unavailable
- **THEN** the value display SHALL render a neutral state rather than a stale or misleading figure

#### Scenario: Value updates on arrival in a new system

- **WHEN** the player arrives in a new system and a value summary is produced
- **THEN** the value display SHALL update live to reflect the new system
