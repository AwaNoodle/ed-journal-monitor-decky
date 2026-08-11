## MODIFIED Requirements

### Requirement: Next-in-route determination

The plugin SHALL determine the next system in the plotted route from `NavRoute.json` relative to the player's current system, updating when the route changes and after each jump. When there is no plotted route, the current system is the final hop, or the current system is not on the plotted route, the plugin SHALL expose an explicit "no next hop" state that identifies which of those conditions applies.

#### Scenario: Next hop derived from the plotted route

- **WHEN** a route is plotted and the player is at a system that is not the final hop
- **THEN** the plugin SHALL identify the next system in the route after the current system

#### Scenario: No route plotted

- **WHEN** there is no plotted route (no `NavRoute.json` or an empty/consumed route)
- **THEN** the plugin SHALL expose a "no next hop" state identifying the cause as no route

#### Scenario: Final hop reached

- **WHEN** a route is plotted and the player's current system is its final entry
- **THEN** the plugin SHALL expose a "no next hop" state identifying the cause as the final hop having been reached

#### Scenario: Off the plotted route

- **WHEN** a route is plotted and the player's current system is not an entry in it
- **THEN** the plugin SHALL expose a "no next hop" state identifying the cause as being off route

#### Scenario: Next hop advances after a jump

- **WHEN** the player jumps to the next system in the route
- **THEN** the plugin SHALL advance the next hop to the following system in the route

### Requirement: Next-hop preview lookup

When auto-lookups are enabled and a next hop exists, the plugin SHALL look up that next system via the existing per-system read and cache, and produce a next-hop preview containing at least the primary-star scoopability and, when available, the worth-scanning verdict and value summary for that system. The lookup MUST be non-blocking, contained on failure, and MUST NOT gate submission.

The preview payload SHALL carry a reason discriminator identifying why no next system is present, so that a consumer rendering the preview permanently can distinguish no route, final hop, off route, and lookups disabled from one another. The discriminator MUST be derived without issuing any additional request.

#### Scenario: Preview produced for the next hop

- **WHEN** a next hop exists and auto-lookups are enabled
- **THEN** the plugin SHALL produce a preview including the next system's primary-star scoopability and, if available, its verdict/value, with the reason indicating a next hop is present

#### Scenario: Next-hop lookup reuses the cache

- **WHEN** the next system has a cached, unexpired lookup result
- **THEN** the plugin SHALL use the cached result rather than issue a new request

#### Scenario: Preview unavailable

- **WHEN** auto-lookups are disabled, there is no next hop, or the lookup fails
- **THEN** the plugin SHALL expose a neutral "no preview" state

#### Scenario: Neutral preview states its cause

- **WHEN** a neutral preview is produced
- **THEN** its reason SHALL identify whether the cause is no route, the final hop, being off route, or auto-lookups being disabled

#### Scenario: Reason survives rehydration

- **WHEN** the panel rehydrates the stored next-hop preview via the status callable
- **THEN** the reason discriminator SHALL be present in the rehydrated payload
