## ADDED Requirements

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
