# worth-scanning-notification Specification

## Purpose

Surface a notifying arrival verdict over the running game via a Steam toast, with no quick access menu interaction required, so the decision to honk can be made from the cockpit.

## Requirements

### Requirement: Notification enable toggle

The plugin SHALL persist an enable/disable setting for worth-scanning notifications, defaulting to disabled. When disabled, no notification SHALL be raised regardless of verdict. The setting MUST be independent of the EDSM API key and of the EDDN and EDSM write paths.

#### Scenario: Notifications disabled by default

- **WHEN** the plugin is loaded with no prior notification setting persisted
- **THEN** worth-scanning notifications SHALL be disabled

#### Scenario: Notifications disabled suppresses all verdicts

- **WHEN** the notification setting is disabled and an arrival produces any verdict
- **THEN** no notification SHALL be raised

#### Scenario: Setting persists across restart

- **WHEN** the notification setting is changed
- **THEN** the plugin SHALL persist it and restore the same value on the next load

### Requirement: Verdict threshold setting

The plugin SHALL persist a verdict threshold setting controlling which verdicts raise a notification, defaulting to green-only. When the threshold is green-only, only a `green` verdict SHALL notify. When the threshold is all-verdicts, both `green` and `yellow` SHALL notify. A `red` verdict and a neutral "no verdict" state MUST never raise a notification at either threshold, because neither indicates a system worth scanning.

#### Scenario: Green-only threshold notifies on green

- **WHEN** notifications are enabled, the threshold is green-only, and the arrival verdict is green
- **THEN** a notification SHALL be raised

#### Scenario: Green-only threshold suppresses yellow

- **WHEN** notifications are enabled, the threshold is green-only, and the arrival verdict is yellow
- **THEN** no notification SHALL be raised

#### Scenario: All-verdicts threshold notifies on yellow

- **WHEN** notifications are enabled, the threshold is all-verdicts, and the arrival verdict is yellow
- **THEN** a notification SHALL be raised

#### Scenario: Red never notifies

- **WHEN** notifications are enabled at either threshold and the arrival verdict is red
- **THEN** no notification SHALL be raised

#### Scenario: Neutral verdict never notifies

- **WHEN** the lookup is disabled, in flight, or failed, so no verdict is available
- **THEN** no notification SHALL be raised

### Requirement: Notification decision made in the backend

The decision of whether a given arrival raises a notification SHALL be made in the backend and carried to the frontend as a single boolean on the worth-scanning payload. The frontend MUST NOT hold notification settings, thresholds, or notification state, so that changing a setting in the panel takes effect without any frontend state synchronisation.

#### Scenario: Backend emits the decision

- **WHEN** an arrival lookup produces a verdict
- **THEN** the backend SHALL compute the notify decision from the persisted settings and the verdict, and include it on the emitted payload

#### Scenario: Frontend does not re-derive the decision

- **WHEN** the frontend receives a worth-scanning payload
- **THEN** it SHALL raise a notification if and only if the payload's notify flag is true, without consulting settings

#### Scenario: Setting change applies without restart

- **WHEN** the user changes a notification setting while the game is running
- **THEN** the next arrival SHALL reflect the new setting

### Requirement: Notification is raised over the running game

When the notify decision is true, the plugin SHALL raise a Steam toast notification that is visible over the running game without the user opening the quick access menu. The notification SHALL identify the system by name and SHALL include the estimated system value and the top priority bodies when available. Activating the notification SHALL open the plugin's quick access tab so the full breakdown can be read.

#### Scenario: Toast raised on a notifying arrival

- **WHEN** a worth-scanning payload arrives with the notify flag true
- **THEN** the plugin SHALL raise a Steam toast naming the system, without requiring the quick access menu to be open

#### Scenario: Toast includes value context when available

- **WHEN** the payload carries an estimated value and priority bodies
- **THEN** the notification SHALL present them alongside the system name

#### Scenario: Toast omits value context when absent

- **WHEN** the payload carries a neutral value (no estimated value and no priority bodies)
- **THEN** the notification SHALL still be raised, naming the system, without empty or placeholder value text

#### Scenario: Activating the toast opens the panel

- **WHEN** the user activates the notification
- **THEN** the plugin's quick access tab SHALL be opened

#### Scenario: No sound is played

- **WHEN** a notification is raised
- **THEN** the plugin SHALL NOT request a notification sound

### Requirement: Notification listener outlives the panel

The worth-scanning notification listener SHALL be registered at plugin load and remain active for the lifetime of the plugin, independent of whether the panel content is mounted, and SHALL be disposed when the plugin unmounts. Notifications MUST be raised only from the emitted arrival event, never from a status rehydration, so that opening or refreshing the panel cannot replay a past notification.

#### Scenario: Notification raised while the panel is closed

- **WHEN** an arrival produces a notifying verdict and the plugin panel has never been opened this session
- **THEN** the notification SHALL still be raised

#### Scenario: Status rehydration does not notify

- **WHEN** the frontend fetches plugin status and receives a stored worth-scanning verdict
- **THEN** no notification SHALL be raised from that fetch

#### Scenario: Listener disposed on unmount

- **WHEN** the plugin unmounts
- **THEN** the notification listener SHALL be removed

### Requirement: Platform suppression is out of the plugin's control

The plugin SHALL document that Steam's own in-game notification preference and Do Not Disturb mode can suppress the toast, and SHALL NOT attempt to detect, override, or work around those platform settings.

#### Scenario: Documented caveat

- **WHEN** a user reads the plugin documentation for the notification feature
- **THEN** it SHALL state that Steam's in-game notification setting and Do Not Disturb can prevent the toast from appearing

#### Scenario: No override attempted

- **WHEN** the plugin raises a notification
- **THEN** it SHALL use the standard Steam toast path and SHALL NOT alter or bypass the user's platform notification settings
