## MODIFIED Requirements

### Requirement: Detect Elite Dangerous start
The frontend SHALL register with `SteamClient.GameSessions.RegisterForAppLifetimeNotifications` and detect when an app with AppID 359320 starts running (`bRunning: true`).

#### Scenario: Elite Dangerous launches
- **WHEN** SteamClient fires AppLifetimeNotification with `unAppID: 359320` and `bRunning: true`
- **THEN** the frontend SHALL call the backend `set_ed_running(true)` method
- **THEN** the frontend SHALL call the backend `start_watcher` method

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
