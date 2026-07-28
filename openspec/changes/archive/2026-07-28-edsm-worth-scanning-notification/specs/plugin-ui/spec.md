## ADDED Requirements

### Requirement: Configure worth-scanning notifications

The EDSM configuration section SHALL provide a toggle for the user to enable or disable worth-scanning notifications, and a control to choose whether notifications fire on green verdicts only or on green and yellow verdicts. Both controls SHALL reflect the currently persisted settings and SHALL persist changes through the backend.

#### Scenario: User enables notifications

- **WHEN** the user turns the notification toggle on
- **THEN** the frontend SHALL call the backend to persist the enabled setting

#### Scenario: User disables notifications

- **WHEN** the user turns the notification toggle off
- **THEN** the frontend SHALL call the backend to persist the disabled setting, after which no notification is raised on arrival

#### Scenario: User widens the verdict threshold

- **WHEN** the user changes the verdict control from green-only to all verdicts
- **THEN** the frontend SHALL call the backend to persist the new threshold

#### Scenario: Controls reflect saved settings

- **WHEN** the EDSM configuration section is displayed
- **THEN** the notification toggle and verdict control SHALL reflect the currently persisted settings

### Requirement: Notification controls depend on auto-lookups

The notification controls SHALL be presented as dependent on EDSM auto-lookups. When auto-lookups are disabled the controls MUST be shown in a visibly inactive state, because without lookups there is no verdict to notify on.

#### Scenario: Controls inactive when lookups are off

- **WHEN** EDSM auto-lookups are disabled
- **THEN** the notification toggle and verdict control SHALL be shown in a visibly inactive state

#### Scenario: Controls active when lookups are on

- **WHEN** EDSM auto-lookups are enabled
- **THEN** the notification toggle and verdict control SHALL be active and adjustable

### Requirement: EDSM settings presented as one section

The EDSM credentials, auto-lookup toggle, and notification controls SHALL be presented together as a single labelled EDSM section, so related settings are grouped rather than interleaved with unrelated plugin settings.

#### Scenario: EDSM settings grouped

- **WHEN** the configuration UI is displayed
- **THEN** the EDSM credentials, auto-lookup toggle, and notification controls SHALL appear together under one EDSM section heading

### Requirement: Panel rendering unaffected by notifications

The panel's existing worth-scanning display SHALL be unchanged by the notification feature. The panel MUST continue to render the verdict, value, and priority bodies for the current system regardless of whether a notification was raised for it.

#### Scenario: Panel shows verdict when notifications are off

- **WHEN** notifications are disabled and an arrival produces a verdict
- **THEN** the panel SHALL display that verdict exactly as before this change

#### Scenario: Panel shows verdict for a suppressed verdict

- **WHEN** an arrival produces a red verdict, which never notifies
- **THEN** the panel SHALL still display the red verdict and its value context
