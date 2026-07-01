## ADDED Requirements

### Requirement: Forward raw journal events to EDSM as a stream consumer
The plugin SHALL forward parsed journal events to EDSM's journal API as a stream consumer that observes the same raw parsed-event stream as EDDN, before the EDDN reportable-event filter. The EDSM consumer MUST forward events verbatim (the raw journal line, no EDDN-style transform) and MUST NOT alter, block, or depend on the EDDN submission path.

#### Scenario: EDSM observes the raw event stream

- **WHEN** the watcher parses a journal event
- **THEN** the EDSM consumer's `observe` is called with the parsed event before the EDDN `is_reportable` filter, and the event is queued verbatim for EDSM forwarding

#### Scenario: EDDN path is unaffected by EDSM

- **WHEN** the EDSM consumer observes or forwards an event
- **THEN** the EDDN validation, transformation, and submission for that event are unchanged

#### Scenario: EDSM disabled when no API key is configured

- **WHEN** no EDSM API key is configured
- **THEN** the EDSM consumer SHALL NOT contact EDSM and SHALL NOT queue events for forwarding

### Requirement: Filter events using the EDSM discard list
The EDSM consumer SHALL fetch EDSM's discard list at consumer start, cache it for the session, and forward only events whose `event` name is not in the list. The discard filter is distinct from the EDDN reportable-event filter.

#### Scenario: Discard list fetched and cached at start

- **WHEN** the EDSM consumer starts a session with valid credentials
- **THEN** it fetches the discard list from EDSM and caches it as a set of event names for the session

#### Scenario: Discarded events are not forwarded

- **WHEN** an observed event's `event` name is in the cached discard list
- **THEN** the EDSM consumer SHALL NOT forward that event

#### Scenario: Accepted events are forwarded

- **WHEN** an observed event's `event` name is not in the cached discard list
- **THEN** the EDSM consumer SHALL queue that event for forwarding

#### Scenario: Discard fetch failure fails safe

- **WHEN** the discard list cannot be fetched
- **THEN** the EDSM consumer SHALL NOT forward events and SHALL surface the condition, without affecting EDDN, and SHALL retry fetching with backoff

### Requirement: Batch and flush events to the EDSM journal endpoint
The EDSM consumer SHALL accumulate accepted events in journal order and POST them to `api-journal-v1` as a batch, flushing on a size or time threshold and forcing a flush when the session stops. Each request MUST include the configured commander name, API key, software name/version, game version/build, and the batched messages.

#### Scenario: Flush on threshold

- **WHEN** the queued event count reaches the size threshold or the time threshold elapses
- **THEN** the EDSM consumer SHALL POST the queued events as a batch and clear the queue on success

#### Scenario: Forced flush on session stop

- **WHEN** the session stops
- **THEN** the EDSM consumer SHALL flush any queued events before shutting down

#### Scenario: Only the Live game version is forwarded

- **WHEN** the current session is a Legacy game version
- **THEN** the EDSM consumer SHALL NOT forward events

#### Scenario: Request carries required parameters

- **WHEN** the EDSM consumer POSTs a batch
- **THEN** the request SHALL include `commanderName`, `apiKey`, `fromSoftware`, `fromSoftwareVersion`, `fromGameVersion`, `fromGameBuild`, and `message` containing the batched journal lines

### Requirement: Classify EDSM responses and handle rate limits
The EDSM consumer SHALL classify EDSM responses by `msgnum` and react accordingly, and SHALL honor EDSM rate-limit headers. Fatal request errors MUST NOT be retried; transient server errors MUST be retried; rate-limit exhaustion MUST defer further requests until reset.

#### Scenario: Success response

- **WHEN** EDSM returns a 1xx `msgnum`
- **THEN** the batch is treated as successfully submitted

#### Scenario: Fatal request error is not retried

- **WHEN** EDSM returns a 2xx `msgnum` (e.g. 203 bad credentials, 205 blacklisted software, 208 Legacy not supported)
- **THEN** the EDSM consumer SHALL NOT retry the batch and SHALL surface a clear user-facing error

#### Scenario: Transient server error is retried

- **WHEN** EDSM returns a 5xx `msgnum` or the request fails with a network error
- **THEN** the EDSM consumer SHALL retry with backoff and retain the events for resend

#### Scenario: Rate limit exhausted

- **WHEN** the EDSM rate-limit header indicates no remaining quota
- **THEN** the EDSM consumer SHALL wait until the reset time before sending again

### Requirement: EDSM credentials and identifiable-upload consent
The plugin SHALL store an EDSM commander name and API key as settings, and SHALL treat the presence of an API key as the opt-in for identifiable uploads. EDSM uploads are tied to a named account and MUST be off by default.

#### Scenario: Saving credentials enables EDSM

- **WHEN** the user saves an EDSM commander name and API key
- **THEN** the plugin SHALL persist them and the EDSM consumer SHALL become active for the next session

#### Scenario: Default off without consent

- **WHEN** the plugin starts with no EDSM API key configured
- **THEN** EDSM forwarding SHALL be inactive

#### Scenario: Invalid credentials surfaced

- **WHEN** EDSM rejects a submission with a missing/invalid credential `msgnum` (201, 202, or 203)
- **THEN** the plugin SHALL surface a clear "check your EDSM credentials" error and SHALL NOT retry on those codes

### Requirement: Per-EDSM statistics with per-session reset and failure isolation
The EDSM consumer SHALL track its own success and failure counts and its last response message, expose them under its consumer name for per-target stats aggregation, and reset them when Elite Dangerous starts a new session. EDSM failures MUST NOT affect EDDN statistics, and EDDN failures MUST NOT affect EDSM statistics.

#### Scenario: EDSM stats reported independently

- **WHEN** an EDSM batch completes (success or failure)
- **THEN** the EDSM consumer's own success/fail counts and last `msgnum`/`msg` are updated and reported under its consumer name, leaving EDDN counts unchanged

#### Scenario: EDSM stats reset on ED start

- **WHEN** Elite Dangerous transitions from not running to running
- **THEN** the EDSM consumer's success and failure counts SHALL reset to zero

#### Scenario: EDSM failure does not affect EDDN

- **WHEN** an EDSM submission fails
- **THEN** the EDDN success and failure counts SHALL be unchanged and EDDN submission SHALL continue normally
