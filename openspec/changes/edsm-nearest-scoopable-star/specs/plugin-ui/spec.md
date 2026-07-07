## ADDED Requirements

### Requirement: Nearest scoopable star action

The panel SHALL provide an on-demand action to find the nearest scoopable star from the current system, and SHALL display the result — nearest system name, distance, and star class — with distinct in-flight, none-found, unavailable, and disabled states. The action MUST be visibly EDSM-sourced.

#### Scenario: User requests nearest scoopable star

- **WHEN** the user triggers the nearest-scoopable-star action while auto-lookups are enabled
- **THEN** the frontend SHALL call the backend and show an in-flight state, then display the nearest scoopable system, distance, and class

#### Scenario: None found within radius

- **WHEN** the backend reports no scoopable star within the radius
- **THEN** the panel SHALL show a clear "none found nearby" message rather than an empty or error state

#### Scenario: Action disabled when lookups are off

- **WHEN** EDSM auto-lookups are disabled
- **THEN** the panel SHALL indicate the action is unavailable and SHALL NOT trigger an EDSM request
