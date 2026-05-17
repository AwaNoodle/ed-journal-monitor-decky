## MODIFIED Requirements

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
