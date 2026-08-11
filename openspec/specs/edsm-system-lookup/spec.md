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

### Requirement: Notify flag on the worth-scanning payload

The worth-scanning payload emitted on arrival SHALL carry a notify flag indicating whether this arrival warrants a user-facing notification, derived from the persisted notification settings and the derived verdict. The flag MUST be additive to the existing payload — the system, verdict, source, value, and priority-body fields, and all existing consumers of them, are unchanged.

#### Scenario: Notify flag accompanies the verdict

- **WHEN** an arrival lookup emits a worth-scanning payload
- **THEN** the payload SHALL include a notify flag alongside the existing verdict fields

#### Scenario: Existing payload fields unchanged

- **WHEN** a consumer reads the system, verdict, source, value, or priority-body fields of the payload
- **THEN** those fields SHALL have the same meaning and shape as before this change

#### Scenario: Value-fetch failure still emits a notify decision

- **WHEN** the verdict is derived but the estimated-value fetch fails
- **THEN** the payload SHALL still carry a notify flag derived from the verdict, with neutral value fields

### Requirement: Notify flag excluded from rehydration state

The stored worth-scanning state used to rehydrate the panel on a status request MUST NOT include the notify flag, so that a status fetch structurally cannot cause a notification to be raised.

#### Scenario: Stored verdict omits the flag

- **WHEN** the backend stores the latest worth-scanning payload for rehydration
- **THEN** the stored value SHALL omit the notify flag

#### Scenario: Status response omits the flag

- **WHEN** the frontend requests plugin status
- **THEN** the returned worth-scanning state SHALL NOT contain a notify flag

### Requirement: Notification does not affect lookup behaviour

Adding the notify decision MUST NOT change when lookups fire, how they are cached, how failures are contained, or how submission proceeds. The decision is derived from an already-computed verdict and MUST NOT issue any additional network request.

#### Scenario: No additional requests

- **WHEN** the notify decision is computed for an arrival
- **THEN** no EDSM request SHALL be issued beyond those the lookup already performs

#### Scenario: Submission still unaffected

- **WHEN** the notify decision is computed, at any setting combination
- **THEN** EDDN submission and EDSM forwarding for the same events SHALL proceed unaffected

### Requirement: Notification suppression is not deduplicated

The notify decision SHALL be made per emitted verdict, with no additional per-session or per-system suppression beyond the lookup's existing guard against re-triggering for the system the player is already in. Re-entering a previously notified system after visiting another SHALL therefore notify again.

#### Scenario: Revisited system notifies again

- **WHEN** the player jumps from a notifying system to another system and then back, and both arrivals produce a notifying verdict
- **THEN** a notification SHALL be raised on each arrival

#### Scenario: No repeat while in the same system

- **WHEN** further events are observed for the system the player is already in
- **THEN** no additional worth-scanning payload — and therefore no additional notification — SHALL be produced
