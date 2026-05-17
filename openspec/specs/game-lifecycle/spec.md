## Requirements

### Requirement: Detect Elite Dangerous start
The frontend SHALL register with `SteamClient.GameSessions.RegisterForAppLifetimeNotifications` and detect when an app with AppID 359320 starts running (`bRunning: true`).

#### Scenario: Elite Dangerous launches
- **WHEN** SteamClient fires AppLifetimeNotification with `unAppID: 359320` and `bRunning: true`
- **THEN** the frontend SHALL call the backend `set_ed_running(true)` method
- **THEN** the frontend SHALL call the backend `start_watcher` method

#### Scenario: Elite Dangerous start resets upload statistics
- **WHEN** the backend `set_ed_running(true)` is called and the previous state was `ed_running: false`
- **THEN** the backend SHALL reset upload statistics (success count, fail count, last upload time, last upload event) to zero/empty
- **THEN** the backend SHALL emit a `status_update` event with the zeroed statistics

#### Scenario: Non-ED game launches
- **WHEN** SteamClient fires AppLifetimeNotification with `unAppID` not equal to 359320
- **THEN** the frontend SHALL ignore the event

### Requirement: Detect Elite Dangerous stop
The frontend SHALL detect when Elite Dangerous stops running via AppLifetimeNotification (`bRunning: false`).

#### Scenario: Elite Dangerous exits
- **WHEN** SteamClient fires AppLifetimeNotification with `unAppID: 359320` and `bRunning: false`
- **THEN** the frontend SHALL call the backend `set_ed_running(false)` method
- **THEN** the frontend SHALL call the backend `stop_watcher` method

#### Scenario: ED crashes or is force-killed
- **WHEN** SteamClient fires AppLifetimeNotification with `unAppID: 359320` and `bRunning: false` (crash scenario)
- **THEN** the frontend SHALL call the backend `set_ed_running(false)` method
- **THEN** the frontend SHALL call the backend `stop_watcher` method the same as a normal exit

### Requirement: Register and unregister lifecycle listeners
The plugin SHALL register SteamClient lifecycle listeners on mount and unregister them on dismount.

#### Scenario: Plugin loads
- **WHEN** the Decky plugin initializes
- **THEN** the frontend SHALL register for AppLifetimeNotifications

#### Scenario: Plugin unloads
- **WHEN** the Decky plugin dismounts
- **THEN** the frontend SHALL unregister all AppLifetimeNotification listeners

### Requirement: Trigger journal path re-scan on game start
When ED starts and the journal path is not yet known, the frontend SHALL trigger a backend re-scan for the journal directory.

#### Scenario: ED starts with no cached journal path
- **WHEN** ED starts and no journal path is cached in settings
- **THEN** the frontend SHALL call the backend `find_journal_path` method before starting the watcher
