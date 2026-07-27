## ADDED Requirements

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
