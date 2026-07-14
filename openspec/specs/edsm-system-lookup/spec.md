# edsm-system-lookup Specification

## Purpose

Provide a read-side EDSM integration that fetches public system data on arrival, derives a "worth scanning" verdict, and surfaces it to the frontend — without an API key and without affecting the EDDN or EDSM write paths.

## Requirements

### Requirement: EDSM read client for public system data

The plugin SHALL provide a read-side EDSM client that issues GET requests to EDSM's public `api-system-v1` endpoints. The client MUST send the plugin's custom User-Agent (EDSM rejects the default urllib User-Agent behind Cloudflare) and MUST use the shared `build_ssl_context()`. The read client MUST be separate from the write-only journal-forwarding client and MUST NOT require an API key, because the system endpoints are public.

#### Scenario: Fetch known system bodies

- **WHEN** a system lookup is requested for a system name that EDSM knows
- **THEN** the client SHALL request `api-system-v1/bodies` for that system with the custom User-Agent and shared SSL context, and return the parsed body list

#### Scenario: System unknown to EDSM

- **WHEN** a system lookup is requested for a system EDSM has no record of
- **THEN** the client SHALL return an explicit "unknown to EDSM" result rather than an error

#### Scenario: EDSM read failure is contained

- **WHEN** an EDSM read request fails (network error, timeout, non-200, or malformed response)
- **THEN** the client SHALL return an "unavailable" result and SHALL NOT raise into, retry against, or otherwise affect the EDDN or EDSM-write submission paths

### Requirement: Per-system lookup cache

The plugin SHALL cache system lookup results keyed by system name with a time-to-live, so that re-entering a previously looked-up system within the TTL does not issue a new EDSM request.

#### Scenario: Cache hit on re-entry

- **WHEN** the player arrives in a system whose lookup result is already cached and unexpired
- **THEN** the plugin SHALL use the cached result and SHALL NOT issue a new EDSM request

#### Scenario: Cache miss after expiry

- **WHEN** the player arrives in a system whose cached result has exceeded its TTL
- **THEN** the plugin SHALL issue a fresh EDSM request and update the cache

### Requirement: Arrival-triggered lookup

When EDSM auto-lookups are enabled, the plugin SHALL trigger at most one system lookup per system entry, on arrival events (`FSDJump` and `Location`). The lookup MUST run without blocking or gating event parsing, EDDN submission, or EDSM forwarding.

#### Scenario: Lookup fires once on arrival

- **WHEN** an `FSDJump` or `Location` event is observed for a system and auto-lookups are enabled
- **THEN** the plugin SHALL trigger a single lookup for that system

#### Scenario: No duplicate lookup for the same system

- **WHEN** additional events are observed for the system the player is already in
- **THEN** the plugin SHALL NOT trigger an additional lookup for that same system

#### Scenario: Lookup never gates submission

- **WHEN** a lookup is in flight or fails
- **THEN** EDDN submission and EDSM forwarding for the same events SHALL proceed unaffected

### Requirement: Auto-lookup enable toggle

The plugin SHALL persist an enable/disable setting for EDSM auto-lookups, independent of the EDSM forwarding API key. When disabled, the plugin SHALL make no EDSM read requests.

#### Scenario: Lookups disabled

- **WHEN** the auto-lookup setting is disabled
- **THEN** no EDSM read requests SHALL be made on arrival, regardless of whether an EDSM API key is set

#### Scenario: Lookups enabled without an API key

- **WHEN** the auto-lookup setting is enabled and no EDSM API key is configured
- **THEN** arrival lookups SHALL still be performed, because the system endpoints are public

#### Scenario: Setting persists across restart

- **WHEN** the auto-lookup setting is changed
- **THEN** the plugin SHALL persist it and restore the same value on the next load

### Requirement: Worth-scanning verdict

The plugin SHALL derive a "worth scanning" verdict for the arrived system from EDSM's known bodies, with three levels:

- **green** — the system is unknown to EDSM, or none of its known bodies are FSS-discovered
- **yellow** — some but not all known bodies are FSS-discovered
- **red** — all known bodies are FSS-discovered (mapping status is not available on the `api-system-v1/bodies` endpoint)

The verdict MUST be attributed to EDSM as its source, and MUST be understood to reflect only bodies EDSM knows about (it cannot account for bodies nobody has uploaded yet).

> **API note (confirmed 2026-07-06):** The `api-system-v1/bodies` endpoint does not expose an `isMapped` field. Discovery status is determined solely by the presence of the `discovery` dict on each body. Mapped-only filtering is not possible with this endpoint.

#### Scenario: Green for a virgin or unknown system

- **WHEN** the system is unknown to EDSM, or EDSM knows bodies but none are FSS-discovered
- **THEN** the verdict SHALL be green

#### Scenario: Yellow for a partially explored system

- **WHEN** EDSM knows some bodies that are FSS-discovered and others that are not
- **THEN** the verdict SHALL be yellow

#### Scenario: Red for a fully tagged system

- **WHEN** every body EDSM knows for the system is FSS-discovered
- **THEN** the verdict SHALL be red

#### Scenario: Verdict unavailable

- **WHEN** the lookup is disabled, in flight, or failed
- **THEN** the plugin SHALL expose a neutral "no verdict" state rather than a misleading colour

### Requirement: System value fetch

The arrival lookup SHALL additionally fetch `api-system-v1/estimated-value` for the arrived system, using the same read client (custom User-Agent, shared SSL context, no API key), the same per-system TTL cache, and the same auto-lookup toggle gate as the bodies lookup. A value fetch failure MUST be contained exactly like other read failures and MUST NOT affect submission.

#### Scenario: Value fetched on arrival

- **WHEN** auto-lookups are enabled and the player arrives in a system
- **THEN** the plugin SHALL fetch the system's estimated value and cache it per system alongside the bodies result

#### Scenario: Value fetch cached on re-entry

- **WHEN** the player re-enters a system whose value result is cached and unexpired
- **THEN** the plugin SHALL use the cached value and SHALL NOT issue a new request

#### Scenario: Value unavailable

- **WHEN** the value fetch is disabled, in flight, or fails
- **THEN** the plugin SHALL expose a neutral "no value" state rather than a misleading number

### Requirement: System value summary

The plugin SHALL derive a system value summary from the estimated-value response: the system's total estimated scan value and a ranked list of priority bodies (highest estimated value first), each with an identifying body name/type and its estimated value. The summary MUST be attributed to EDSM and MUST be treated as a floor — it reflects only EDSM's known bodies and excludes the first-mapped bonus the player would earn.

#### Scenario: Summary with priority bodies

- **WHEN** EDSM returns an estimated value with valued bodies for the system
- **THEN** the summary SHALL include the total estimated value and a ranked list of the highest-value bodies

#### Scenario: Summary for a system with no valued bodies

- **WHEN** EDSM knows the system but reports no valued bodies
- **THEN** the summary SHALL report a zero/empty value state rather than an error

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
