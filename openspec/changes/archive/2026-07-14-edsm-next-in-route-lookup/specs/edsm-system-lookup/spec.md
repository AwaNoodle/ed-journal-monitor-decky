## ADDED Requirements

### Requirement: Next-in-route determination

The plugin SHALL determine the next system in the plotted route from `NavRoute.json` relative to the player's current system, updating when the route changes and after each jump. When there is no plotted route, or the current system is the final hop, the plugin SHALL expose an explicit "no next hop" state.

#### Scenario: Next hop derived from the plotted route

- **WHEN** a route is plotted and the player is at a system that is not the final hop
- **THEN** the plugin SHALL identify the next system in the route after the current system

#### Scenario: No route plotted

- **WHEN** there is no plotted route (no `NavRoute.json` or an empty/consumed route)
- **THEN** the plugin SHALL expose a "no next hop" state

#### Scenario: Next hop advances after a jump

- **WHEN** the player jumps to the next system in the route
- **THEN** the plugin SHALL advance the next hop to the following system in the route

### Requirement: Next-hop preview lookup

When auto-lookups are enabled and a next hop exists, the plugin SHALL look up that next system via the existing per-system read and cache, and produce a next-hop preview containing at least the primary-star scoopability and, when available, the worth-scanning verdict and value summary for that system. The lookup MUST be non-blocking, contained on failure, and MUST NOT gate submission.

#### Scenario: Preview produced for the next hop

- **WHEN** a next hop exists and auto-lookups are enabled
- **THEN** the plugin SHALL produce a preview including the next system's primary-star scoopability and, if available, its verdict/value

#### Scenario: Next-hop lookup reuses the cache

- **WHEN** the next system has a cached, unexpired lookup result
- **THEN** the plugin SHALL use the cached result rather than issue a new request

#### Scenario: Preview unavailable

- **WHEN** auto-lookups are disabled, there is no next hop, or the lookup fails
- **THEN** the plugin SHALL expose a neutral "no preview" state
