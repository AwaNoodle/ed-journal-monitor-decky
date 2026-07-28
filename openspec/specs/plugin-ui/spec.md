## Purpose

Present the plugin's status, per-target upload statistics, configuration, and activity to the user in the Decky panel.
## Requirements
### Requirement: Display plugin status panel
The frontend SHALL display a Decky UI panel showing the current state of the journal monitor with two independent status fields.

#### Scenario: Plugin idle (ED not running)
- **WHEN** Elite Dangerous is not running and the watcher is not running
- **THEN** the panel SHALL show "ED Status" as "⚪ Not Running"
- **THEN** the panel SHALL show "Journal Status" as "📂 Found" (if journal path exists) or "🔍 Not Found" (if no path)

#### Scenario: Plugin watching (ED running)
- **WHEN** Elite Dangerous is running and the watcher is active
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "🟢 Watching"

#### Scenario: Journal path not found
- **WHEN** the journal path is not detected and no manual path is set
- **THEN** "Journal Status" SHALL display "🔍 Not Found"

#### Scenario: ED running but watcher not active
- **WHEN** Elite Dangerous is running and the watcher is not running and a journal path exists
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "⚠️ Found, Not Watching"

### Requirement: Display upload statistics
The frontend SHALL display upload counts per target received from backend events, rendering the targets by mapping over the per-target statistics map rather than from hardcoded target keys, so that a new target appears without a UI change. EDDN SHALL retain its per-event activity display. EDSM's success/fail counts SHALL appear in the per-target rows; EDSM errors are surfaced per-event in the Recent Errors panel (see the `error-display` capability), not as a separate Status-panel block.

#### Scenario: Per-target statistics displayed

- **WHEN** the backend emits a `status_update` event with a per-target statistics map
- **THEN** the panel SHALL render each target's successful and failed upload counts by iterating the map

### Requirement: Enable and disable the monitor
The frontend SHALL provide a toggle to enable or disable the journal monitor.

#### Scenario: User disables monitor
- **WHEN** the user toggles the monitor off
- **THEN** the frontend SHALL call the backend to stop the watcher (if running)
- **THEN** the frontend SHALL NOT start the watcher on subsequent ED start events

#### Scenario: User re-enables monitor
- **WHEN** the user toggles the monitor on
- **THEN** the frontend SHALL check if ED is currently running
- **THEN** if ED is running, start the watcher immediately

### Requirement: Configure journal path manually
The frontend SHALL provide a text input for the user to set the journal directory path manually.

#### Scenario: User enters manual path
- **WHEN** the user enters a path and submits it
- **THEN** the frontend SHALL call the backend `set_journal_path` method
- **THEN** if valid, display a success message
- **THEN** if invalid, display an error message

### Requirement: Configure uploader ID
The frontend SHALL provide a text input for the user to set their EDDN uploader ID.

#### Scenario: User sets uploader ID
- **WHEN** the user enters an uploader ID and submits it
- **THEN** the frontend SHALL call the backend to save the uploader ID to settings

#### Scenario: No uploader ID set
- **WHEN** no uploader ID is configured
- **THEN** the panel SHALL show a notice that the uploader ID should be set before uploading

### Requirement: Display journal path
The frontend SHALL display the currently configured journal path.

#### Scenario: Auto-detected path
- **WHEN** the journal path was found via VDF scan
- **THEN** the panel SHALL display the path with an "Auto-detected" label

#### Scenario: Manually set path
- **WHEN** the journal path was set by the user
- **THEN** the panel SHALL display the path with a "Manual" label

### Requirement: Display diagnostics section
The frontend SHALL display a Diagnostics section in the panel with a detailed logging toggle and a bundle creation button.

#### Scenario: Diagnostics section visible
- **WHEN** the plugin panel is displayed
- **THEN** a Diagnostics section SHALL be visible with a "Detailed Logging" toggle and a "Create Diagnostic Bundle" button

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

