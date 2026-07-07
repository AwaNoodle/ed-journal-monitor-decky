## Purpose

Show a live, player-facing summary of the current Elite Dangerous game launch in the panel.

## Requirements

### Requirement: Session stats accumulation

The plugin SHALL maintain running statistics for the current ED game launch by observing the parsed journal event stream, independently of EDDN submission. The accumulator MUST observe every parsed event before the EDDN reportable-event filter and MUST NOT alter, block, or depend on the EDDN submission path.

The accumulated stats SHALL include: current star system, current commander, jumps made, cumulative distance travelled (light years), bodies scanned, and first-discovery count.

#### Scenario: FSDJump increments jumps and distance

- **WHEN** an `FSDJump` event is observed with a `JumpDist` value and `StarSystem`
- **THEN** the jumps count increments by one, the `JumpDist` is added to cumulative distance, and the current system is updated to `StarSystem`

#### Scenario: Detailed scan increments bodies scanned

- **WHEN** a `Scan` event is observed (Detailed or AutoScan)
- **THEN** the bodies-scanned count increments by one

#### Scenario: First-discovered scan increments first-discovery count

- **WHEN** a `Scan` event is observed with `WasDiscovered` equal to `false`
- **THEN** the first-discovery count increments by one (in addition to bodies scanned)

#### Scenario: Already-discovered scan does not increment first-discovery count

- **WHEN** a `Scan` event is observed with `WasDiscovered` equal to `true`
- **THEN** the bodies-scanned count increments but the first-discovery count does not change

#### Scenario: Non-stats events are ignored

- **WHEN** an observed event is not one the accumulator tracks
- **THEN** no counters change and no error is raised

#### Scenario: EDDN routing is unaffected

- **WHEN** the accumulator observes a reportable event
- **THEN** the event is still validated and submitted to EDDN exactly as before, unchanged by the accumulator

### Requirement: Session boundary and reset semantics

A session SHALL correspond to a single ED game launch. The accumulator MUST reset to zero at the same lifecycle hook that resets upload stats — when the backend is notified that ED has started (`set_ed_running(true)`) — and the reset MUST occur before the watcher's initial journal replay so that retroactive totals for the current launch are preserved.

The accumulator MUST additionally perform a soft reset when the active commander changes. It MUST NOT reset on journal file rolls (`Continued`), on `LoadGame` for the same commander (relog to menu, mode switch), or on suspend/resume.

#### Scenario: Reset on ED launch before replay

- **WHEN** the backend is notified that ED has started
- **THEN** session stats reset to zero, and the subsequent replay of the current journal file repopulates them with this launch's events

#### Scenario: Soft reset on commander change

- **WHEN** a `LoadGame` event is observed whose commander differs from the current session's commander
- **THEN** session stats reset to zero and begin accumulating for the new commander

#### Scenario: No reset on same-commander relog

- **WHEN** a `LoadGame` event is observed whose commander matches the current session's commander
- **THEN** session stats are preserved and continue accumulating

#### Scenario: No reset on journal file roll

- **WHEN** the journal rolls to a new file mid-session (a `Continued` event and a new `Journal.*.log`)
- **THEN** session stats are preserved and continue accumulating across the file boundary

### Requirement: Session stats frontend contract

The backend SHALL expose a `get_session_stats` callable that returns the current session stats so the panel can rehydrate when reopened, and SHALL emit a `session_update` event to the frontend when the stats change so the panel updates live.

#### Scenario: Rehydrate on panel open

- **WHEN** the panel is opened or reopened
- **THEN** it calls `get_session_stats` and displays the current session stats without waiting for a new event

#### Scenario: Live update on change

- **WHEN** the accumulator updates any session stat
- **THEN** the backend emits a `session_update` event carrying the current stats and the panel reflects the new values

#### Scenario: Reset reflected in frontend

- **WHEN** session stats reset (ED launch or commander change)
- **THEN** a `session_update` reflecting the zeroed stats is emitted and the panel shows the reset values

### Requirement: Session panel section

The plugin panel SHALL present a Session section, placed before the Status section, showing the current location prominently and the session counters (jumps, distance, bodies scanned, first discoveries) in a glanceable layout.

#### Scenario: Display current session at a glance

- **WHEN** the panel is shown during an active session
- **THEN** the Session section displays the current system and the session counters above the operational Status section

#### Scenario: Empty session state

- **WHEN** no session data is available yet (no events observed since launch)
- **THEN** the Session section renders a neutral empty state rather than stale or misleading numbers

### Requirement: Worth-scanning chip in the Session metric area

The Session section SHALL present an EDSM-sourced "worth scanning" chip for the current system within the existing metric area, using the red/yellow/green verdict from the `edsm-system-lookup` capability. The chip MUST be visibly attributed to EDSM (so the player understands it reflects EDSM's records, not confirmed ground truth) and MUST render a neutral state when a verdict is not available.

#### Scenario: Chip reflects the current verdict

- **WHEN** an EDSM worth-scanning verdict is available for the current system
- **THEN** the Session metric area SHALL show a chip in the corresponding colour (green/yellow/red), labelled as EDSM-sourced

#### Scenario: Neutral chip when lookups are disabled or unavailable

- **WHEN** EDSM auto-lookups are disabled, or a verdict is in flight or unavailable
- **THEN** the chip SHALL render a neutral state rather than a stale or misleading colour

#### Scenario: Chip updates on arrival in a new system

- **WHEN** the player arrives in a new system and a verdict is produced
- **THEN** the chip SHALL update live to reflect the new system's verdict
