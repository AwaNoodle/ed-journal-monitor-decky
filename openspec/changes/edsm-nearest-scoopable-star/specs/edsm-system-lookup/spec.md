## ADDED Requirements

### Requirement: Sphere-systems read

The EDSM read client SHALL support querying `api-v1/sphere-systems` around a given system within a bounded radius, requesting primary-star information, using the same custom User-Agent, shared SSL context, and no API key as the other read calls. A failure MUST be contained (return unavailable, no raise, no submission impact).

#### Scenario: Sphere query returns nearby systems

- **WHEN** a sphere query is issued for the current system within the configured radius
- **THEN** the client SHALL return the nearby systems with distance and primary-star information

#### Scenario: Sphere query failure contained

- **WHEN** the sphere query fails (network/timeout/non-200/malformed)
- **THEN** the client SHALL return an unavailable result and SHALL NOT affect submission

### Requirement: Nearest scoopable star lookup

The plugin SHALL provide an on-demand lookup that finds, from a sphere query around the current system, the closest system whose primary star is scoopable (KGBFOAM), returning its system name, distance, and star class. The lookup MUST be gated by the EDSM auto-lookup toggle and MUST NOT run automatically on every arrival.

#### Scenario: Nearest scoopable star found

- **WHEN** the user invokes the nearest-scoopable-star lookup and the sphere result contains at least one scoopable primary star
- **THEN** the plugin SHALL return the closest such system with its distance and star class

#### Scenario: No scoopable star within radius

- **WHEN** the sphere result contains no scoopable primary star within the radius
- **THEN** the plugin SHALL return an explicit "none found within radius" result

#### Scenario: Lookup blocked when disabled

- **WHEN** the EDSM auto-lookup toggle is disabled
- **THEN** invoking the nearest-scoopable-star lookup SHALL make no EDSM request and return a disabled state
