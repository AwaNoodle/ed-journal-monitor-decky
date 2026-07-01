## MODIFIED Requirements

### Requirement: Display upload statistics
The frontend SHALL display upload counts per target received from backend events, rendering the targets by mapping over the per-target statistics map rather than from hardcoded target keys, so that a new target appears without a UI change. EDDN SHALL retain its per-event activity display. EDSM's success/fail counts SHALL appear in the per-target rows; EDSM errors are surfaced per-event in the Recent Errors panel (see the `error-display` capability), not as a separate Status-panel block.

#### Scenario: Per-target statistics displayed

- **WHEN** the backend emits a `status_update` event with a per-target statistics map
- **THEN** the panel SHALL render each target's successful and failed upload counts by iterating the map

## ADDED Requirements

### Requirement: Configure EDSM credentials
The frontend SHALL provide inputs for the user to set their EDSM commander name and API key, with a link to where the API key is generated, and SHALL state that EDSM uploads identifiable flight logs under the user's named EDSM account.

#### Scenario: User sets EDSM credentials

- **WHEN** the user enters an EDSM commander name and API key and submits them
- **THEN** the frontend SHALL call the backend to save the EDSM credentials to settings

#### Scenario: Identifiability notice shown

- **WHEN** the EDSM credential inputs are displayed
- **THEN** the panel SHALL show a notice that flight logs upload under the user's named EDSM identity, distinct from anonymous EDDN

#### Scenario: EDSM inactive without API key

- **WHEN** no EDSM API key is configured
- **THEN** the panel SHALL indicate EDSM is inactive and that an API key is required to enable it
