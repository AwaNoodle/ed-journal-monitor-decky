## MODIFIED Requirements

### Requirement: Session panel section

The plugin panel SHALL present a Session section showing the session counters (jumps, distance, bodies scanned, first discoveries) in a glanceable layout. The current location, its worth-scanning verdict, and the next-hop preview SHALL be presented in a separate always-visible Navigation section placed above Session, so that in-flight navigation information is the first thing read. Neither section SHALL be collapsible.

#### Scenario: Display current session at a glance

- **WHEN** the panel is shown during an active session
- **THEN** the Navigation section displays the current system and next hop, and the Session section displays the session counters below it

#### Scenario: Empty session state

- **WHEN** no session data is available yet (no events observed since launch)
- **THEN** the Session section renders a neutral empty state rather than stale or misleading numbers

#### Scenario: Sections always visible

- **WHEN** the panel is opened
- **THEN** the Navigation and Session sections SHALL be visible without any expansion

### Requirement: Worth-scanning chip in the Session metric area

The Navigation section SHALL present an EDSM-sourced "worth scanning" chip for the current system, using the red/yellow/green verdict from the `edsm-system-lookup` capability. The chip MUST be visibly attributed to EDSM (so the player understands it reflects EDSM's records, not confirmed ground truth) and MUST render a neutral state when a verdict is not available.

#### Scenario: Chip reflects the current verdict

- **WHEN** an EDSM worth-scanning verdict is available for the current system
- **THEN** the Navigation section SHALL show a chip in the corresponding colour (green/yellow/red), labelled as EDSM-sourced

#### Scenario: Neutral chip when lookups are disabled or unavailable

- **WHEN** EDSM auto-lookups are disabled, or a verdict is in flight or unavailable
- **THEN** the chip SHALL render a neutral state rather than a stale or misleading colour

#### Scenario: Chip updates on arrival in a new system

- **WHEN** the player arrives in a new system and a verdict is produced
- **THEN** the chip SHALL update live to reflect the new system's verdict

### Requirement: System value display in the Session metric area

The Navigation section SHALL present an EDSM-sourced system value display for the current system, showing the total estimated scan value and the top priority bodies from the `edsm-system-lookup` value summary. The display MUST be attributed to EDSM, MUST convey that the figure is an estimate/floor, and MUST render a neutral state when a value is unavailable.

#### Scenario: Value shown for the current system

- **WHEN** an EDSM system value summary is available for the current system
- **THEN** the Navigation section SHALL show the total estimated value and the top priority bodies, labelled as EDSM-sourced

#### Scenario: Neutral state when value unavailable

- **WHEN** auto-lookups are disabled, or the value is in flight or unavailable
- **THEN** the value display SHALL render a neutral state rather than a stale or misleading figure

#### Scenario: Value updates on arrival in a new system

- **WHEN** the player arrives in a new system and a value summary is produced
- **THEN** the value display SHALL update live to reflect the new system

### Requirement: Next-hop preview in the Session metric area

The Navigation section SHALL permanently present an EDSM-sourced "next hop" preview for the next system in the plotted route, showing at least the next system name and its primary-star scoopability (fuel safety), and its worth-scanning verdict/value when available. The preview MUST be attributed to EDSM. The block SHALL be rendered in all states rather than hidden when there is no next hop, and MUST occupy a stable footprint so that the surrounding layout does not shift as routes change. When there is no next hop, the block MUST state which condition applies, using the reason discriminator from the `edsm-system-lookup` capability.

#### Scenario: Next-hop preview shown

- **WHEN** a next-hop preview is available for the plotted route
- **THEN** the Navigation section SHALL show the next system name and its scoopability (and verdict/value if available), labelled as EDSM-sourced

#### Scenario: No route plotted

- **WHEN** the preview reason indicates no plotted route
- **THEN** the block SHALL render and state that no route is plotted

#### Scenario: Final hop reached

- **WHEN** the preview reason indicates the final hop has been reached
- **THEN** the block SHALL render and state that the destination has been reached, rather than presenting the same text as having no route

#### Scenario: Lookups disabled

- **WHEN** the preview reason indicates auto-lookups are disabled
- **THEN** the block SHALL render and direct the user to enable EDSM lookups

#### Scenario: Layout stable across states

- **WHEN** the next-hop state changes between having a hop and not having one
- **THEN** the block's footprint SHALL remain stable and the position of surrounding content SHALL NOT shift

#### Scenario: Preview advances after a jump

- **WHEN** the player jumps to the next system in the route
- **THEN** the next-hop preview SHALL update to reflect the new following system
