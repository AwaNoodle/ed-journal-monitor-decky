## ADDED Requirements

### Requirement: Configure EDSM auto-lookups

The EDSM configuration section SHALL provide a toggle for the user to enable or disable EDSM auto-lookups, separate from the EDSM credentials.

#### Scenario: User enables auto-lookups

- **WHEN** the user turns the EDSM auto-lookup toggle on
- **THEN** the frontend SHALL call the backend to persist the enabled setting

#### Scenario: User disables auto-lookups

- **WHEN** the user turns the EDSM auto-lookup toggle off
- **THEN** the frontend SHALL call the backend to persist the disabled setting, after which no EDSM read requests are made

#### Scenario: Toggle state reflects saved setting

- **WHEN** the EDSM configuration section is displayed
- **THEN** the auto-lookup toggle SHALL reflect the currently persisted setting
