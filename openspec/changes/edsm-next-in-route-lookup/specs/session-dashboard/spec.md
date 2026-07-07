## ADDED Requirements

### Requirement: Next-hop preview in the Session metric area

The Session section SHALL present an EDSM-sourced "next hop" preview for the next system in the plotted route within the metric area, showing at least the next system name and its primary-star scoopability (fuel safety), and its worth-scanning verdict/value when available. The preview MUST be attributed to EDSM and MUST render a neutral state when there is no route or no data.

#### Scenario: Next-hop preview shown

- **WHEN** a next-hop preview is available for the plotted route
- **THEN** the metric area SHALL show the next system name and its scoopability (and verdict/value if available), labelled as EDSM-sourced

#### Scenario: Neutral state with no route

- **WHEN** there is no plotted route, no next hop, or auto-lookups are disabled
- **THEN** the next-hop preview SHALL render a neutral state rather than stale data

#### Scenario: Preview advances after a jump

- **WHEN** the player jumps to the next system in the route
- **THEN** the next-hop preview SHALL update to reflect the new following system
