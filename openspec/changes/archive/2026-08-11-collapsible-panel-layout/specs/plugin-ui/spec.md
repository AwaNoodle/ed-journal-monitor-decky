## ADDED Requirements

### Requirement: Collapsible panel sections

The panel SHALL provide a collapsible section control whose collapsed children are not rendered, so that collapsed content contributes no gamepad focus stops. Each collapsible section header MUST itself be a single focusable element that toggles the section, and MUST indicate its expanded/collapsed state visually.

#### Scenario: Collapsed section is skipped by directional navigation

- **WHEN** a section is collapsed and the user navigates the panel with the D-pad
- **THEN** focus SHALL move from the section header directly to the next element outside the section, without stopping on any of the section's contents

#### Scenario: Expanding a section reveals its controls

- **WHEN** the user activates a collapsed section header
- **THEN** the section's contents SHALL render and become reachable by directional navigation

#### Scenario: Header indicates state

- **WHEN** a collapsible section is displayed
- **THEN** its header SHALL visually indicate whether it is expanded or collapsed

### Requirement: Frequency-ordered panel layout

The panel SHALL be ordered by how often the player reads each part, not by subject grouping. A health strip, a Navigation section, and a Session section SHALL always be visible and MUST NOT be collapsible. Data flow, Setup, and Troubleshooting SHALL be collapsible sections presented after them, in that order.

#### Scenario: Default panel state

- **WHEN** the panel is opened
- **THEN** the health strip, Navigation, and Session SHALL be visible, and Data flow, Setup, and Troubleshooting SHALL be collapsed

#### Scenario: In-flight content requires no navigation through setup

- **WHEN** the panel is opened during an active session
- **THEN** the current system, its worth-scanning verdict, and the next hop SHALL be readable without expanding any section

### Requirement: Collapsed section state summaries

Each collapsible section header SHALL display a summary of the state of its contents, so that the common check can be satisfied without expanding the section. The Data flow header MUST show the aggregate successful and failed upload counts.

#### Scenario: Upload health readable while collapsed

- **WHEN** Data flow is collapsed and uploads have occurred
- **THEN** its header SHALL show the aggregate success and failure counts across all targets

#### Scenario: Setup state readable while collapsed

- **WHEN** Setup is collapsed
- **THEN** its header SHALL summarise configuration state sufficiently to indicate whether setup is complete

### Requirement: Collapse state resets on panel open

Collapse state SHALL NOT be persisted. Every time the panel is opened, all collapsible sections SHALL start collapsed, except that Data flow SHALL start expanded when the failed upload count is greater than zero.

#### Scenario: Sections reset between panel opens

- **WHEN** the user expands a section, closes the panel, and reopens it
- **THEN** that section SHALL be collapsed again

#### Scenario: Errors auto-expand data flow

- **WHEN** the panel is opened and the failed upload count is greater than zero
- **THEN** Data flow SHALL start expanded

#### Scenario: No errors leaves data flow collapsed

- **WHEN** the panel is opened and the failed upload count is zero
- **THEN** Data flow SHALL start collapsed

### Requirement: Consolidated health strip

The panel SHALL present operational health as a single always-visible line at the top, replacing the separate ED Status and Journal Status fields. The line SHALL report the most severe applicable state, and MUST NOT be a focusable element.

#### Scenario: Healthy state

- **WHEN** Elite Dangerous is running, the monitor is enabled, and the watcher is active
- **THEN** the strip SHALL indicate the plugin is watching, and SHALL show the detected commander when one is known

#### Scenario: Waiting for the game

- **WHEN** a journal path exists, the monitor is enabled, and Elite Dangerous is not running
- **THEN** the strip SHALL indicate the plugin is ready and waiting for Elite Dangerous

#### Scenario: Monitor disabled

- **WHEN** the monitor is disabled by the user
- **THEN** the strip SHALL indicate that watching is paused

#### Scenario: Running but not watching

- **WHEN** Elite Dangerous is running, a journal path exists, and the watcher is not active
- **THEN** the strip SHALL indicate a warning state

#### Scenario: No journal path

- **WHEN** no journal path is detected and none is set manually
- **THEN** the strip SHALL indicate that no journal path is configured and direct the user to Setup

#### Scenario: Most severe state wins

- **WHEN** more than one non-healthy condition applies
- **THEN** the strip SHALL report the most severe one

### Requirement: EDSM settings split by access path

EDSM settings SHALL be presented as two separate groups within Setup: an account group holding the commander name, API key, and identifiability notice; and a lookups group holding the auto-lookup toggle and the notification controls. The grouping MUST make clear that lookups require no API key and are independent of the account credentials.

#### Scenario: Account and lookups presented separately

- **WHEN** Setup is expanded
- **THEN** EDSM account settings and EDSM lookup settings SHALL appear as two distinct groups

#### Scenario: Lookups usable without credentials

- **WHEN** no EDSM API key is configured
- **THEN** the EDSM lookup toggle SHALL remain available and operable

## MODIFIED Requirements

### Requirement: Display upload statistics
The frontend SHALL display upload counts per target received from backend events, rendering the targets by mapping over the per-target statistics map rather than from hardcoded target keys, so that a new target appears without a UI change. The per-target counts SHALL be presented within the Data flow section, whose collapsed header carries the aggregate counts. EDDN SHALL retain its per-event activity display. EDSM's success/fail counts SHALL appear in the per-target rows; EDSM errors are surfaced per-event in the merged activity feed (see the `error-display` capability), not as a separate block.

#### Scenario: Per-target statistics displayed

- **WHEN** the backend emits a `status_update` event with a per-target statistics map
- **THEN** the panel SHALL render each target's successful and failed upload counts by iterating the map

#### Scenario: Aggregate counts shown on the collapsed header

- **WHEN** Data flow is collapsed
- **THEN** the header SHALL show the success and failure counts summed across all targets

### Requirement: Enable and disable the monitor
The frontend SHALL provide a toggle to enable or disable the journal monitor, located within the Setup section's journal path group. The disabled state MUST remain visible without expanding Setup, via the health strip.

#### Scenario: User disables monitor
- **WHEN** the user toggles the monitor off
- **THEN** the frontend SHALL call the backend to stop the watcher (if running)
- **THEN** the frontend SHALL NOT start the watcher on subsequent ED start events
- **THEN** the health strip SHALL indicate that watching is paused

#### Scenario: User re-enables monitor
- **WHEN** the user toggles the monitor on
- **THEN** the frontend SHALL check if ED is currently running
- **THEN** if ED is running, start the watcher immediately

### Requirement: Nearest scoopable star action

The panel SHALL provide an on-demand action to find the nearest scoopable star from the current system, presented within the Navigation section, and SHALL display the result — nearest system name, distance, and star class — with distinct in-flight, none-found, and unavailable states. The action MUST be visibly EDSM-sourced. When EDSM auto-lookups are disabled the action SHALL be self-enabling: it MUST state that activating it will enable lookups, and activating it MUST enable lookups and then perform the search in a single activation.

#### Scenario: User requests nearest scoopable star

- **WHEN** the user triggers the nearest-scoopable-star action while auto-lookups are enabled
- **THEN** the frontend SHALL call the backend and show an in-flight state, then display the nearest scoopable system, distance, and class

#### Scenario: None found within radius

- **WHEN** the backend reports no scoopable star within the radius
- **THEN** the panel SHALL show a clear "none found nearby" message rather than an empty or error state

#### Scenario: Action self-enables when lookups are off

- **WHEN** EDSM auto-lookups are disabled
- **THEN** the action SHALL state that activating it will enable lookups
- **WHEN** the user activates it
- **THEN** the frontend SHALL persist the enabled setting and then perform the search without requiring a second activation

#### Scenario: Self-enabling before the current system is known

- **WHEN** the user activates the action while lookups are disabled and no current system is known yet
- **THEN** lookups SHALL be enabled and the panel SHALL show the unavailable state, rather than suppressing all feedback

### Requirement: Display diagnostics section
The frontend SHALL present a Troubleshooting section, collapsed by default, containing a detailed logging toggle and a bundle creation button.

#### Scenario: Diagnostics section visible
- **WHEN** the Troubleshooting section is expanded
- **THEN** a "Detailed Logging" toggle and a "Create Diagnostic Bundle" button SHALL be visible

#### Scenario: Detailed logging toggle
- **WHEN** the user toggles "Detailed Logging" on
- **THEN** the frontend SHALL call `set_detailed_logging(true)`
- **WHEN** the user toggles "Detailed Logging" off
- **THEN** the frontend SHALL call `set_detailed_logging(false)`

#### Scenario: Create diagnostic bundle
- **WHEN** the user clicks "Create Diagnostic Bundle"
- **THEN** the frontend SHALL call `create_diagnostics()`
- **THEN** the panel SHALL display the zip file path

#### Scenario: Bundle creation fails
- **WHEN** `create_diagnostics()` returns `{ "success": false }`
- **THEN** the panel SHALL display an error message

## REMOVED Requirements

### Requirement: Display plugin status panel

**Reason**: The two independent status fields (ED Status, Journal Status) are replaced by the single worst-state-wins health strip, which conveys the same states in one always-visible line without consuming vertical space or focus stops.

**Migration**: Covered by the `Consolidated health strip` requirement above, whose scenarios map one-to-one onto the removed field combinations.

### Requirement: EDSM settings presented as one section

**Reason**: Grouping write credentials, keyless read lookups, and notification preferences under a single vendor-named heading implied that the API key gates lookups, which it does not.

**Migration**: Covered by the `EDSM settings split by access path` requirement above; both groups remain adjacent within Setup, so the settings are still grouped, but by access path rather than vendor.
