## Context

The plugin submits Elite Dangerous journal events to EDDN. It has a mature three-tier dispatch in `watcher.py` — journal/1 events, dedicated-schema events (`DEDICATED_SCHEMA_EVENTS`), and auxiliary-file events (`AUXILIARY_FILES`) — backed by a per-event `REQUIRED_FIELDS` map and a recursive `_strip_disallowed` helper that removes EDDN-disallowed keys and all `*_Localised` keys at any nesting depth. The submitter already injects `uploaderID`, `softwareName`, `softwareVersion`, `gameversion`, and `gamebuild` into the header.

An audit against the live EDDN schema set (18 schemas) found four uncovered journal-sourced schemas, a missing optional field on `commodity/3`, and documentation drift. This change closes those gaps using only the existing patterns — no new architecture.

## Goals / Non-Goals

**Goals:**
- Add EDDN coverage for `ScanBaryCentre`, `FSSBodySignals`, `DockingGranted`, `DockingDenied`.
- Reconcile documentation with code and publish a standing coverage matrix.

**Non-Goals:**
- `blackmarket/1` — deprecated by EDDN.
- `commodity/3` `prohibited`/`economies` arrays — CAPI-sourced; the commodity-README forbids sending them from journal `Market.json` data, which is this plugin's only source.
- `fcmaterials_capi/1` — CAPI-sourced, not journal-sourced; outside this plugin's input model.
- Any UI, dashboard, multi-target (EDSM/Inara), or retry-queue work.

## Decisions

**1. Reuse the dedicated-schema path for all four new events.**
Each event gets a schema-ref constant in `constants.py`, membership in `REPORTABLE_EVENTS` and `DEDICATED_SCHEMA_EVENTS`, a `REQUIRED_FIELDS` entry, a `transform_*` method modeled on `transform_navbeacon_scan`, and a line in the `_process_dedicated_schema_event` dispatch dict. *Alternative considered:* a generic data-driven transform for "simple passthrough" schemas. Rejected — the existing code favors explicit per-event methods for readability and per-schema augmentation differences; matching that convention keeps the diff reviewable.

**2. StarPos/StarSystem augmentation is per-schema, SystemAddress-gated.**
`ScanBaryCentre` and `FSSBodySignals` require system coordinates and reuse the established augmentation guard (only apply cached `star_pos`/`star_system` when the event's `SystemAddress` matches `session_state.system_address`, preventing stale coordinates). Docking events are station-context and carry no system coordinates, so they get **no** StarPos/StarSystem augmentation — only `horizons`/`odyssey` flags. Because `validate()` otherwise requires StarPos (native or augmentable) for every non-`_STARPOS_EVENTS` event, the docking events are added to a new `_NO_STARPOS_EVENTS` exemption set so they validate without coordinates.

**3. Black-market / `prohibited` data is deliberately not implemented.**
The audit confirmed neither available path is valid for a journal-only plugin: `blackmarket/1` is deprecated, and the `commodity/3` `prohibited`/`economies` arrays are CAPI-sourced — the commodity-README states *"the Journal Market.json doesn't contain `economies` or `prohibited` data, leave these entirely out of the message. You MUST NOT send empty lists."* Emitting `prohibited` from `Market.json` would violate EDDN guidance, so `transform_commodity` is left unchanged. The finding is documented in the coverage audit. *Alternative considered:* sending `prohibited` from `Market.json`'s `Prohibited` field anyway. Rejected — direct conflict with the authoritative README (AGENTS.md mandates README compliance).

**4. Validation reuses `REQUIRED_FIELDS` + `validate()`.**
No new validation machinery. Required-field sets are derived from each schema README. Augmentation-dependent fields (StarPos/StarSystem) are enforced in the transform (returning a rejectable result) rather than in `REQUIRED_FIELDS`, consistent with how `FSSAllBodiesFound` handles StarPos today.

## Risks / Trade-offs

- **Schema READMEs are the source of truth and may evolve** → Cross-reference each README at implementation time (AGENTS.md mandate); the coverage matrix records the schema version checked against.
- **EDDN gateway rejecting a malformed new message** → Each transform has a unit test asserting `$schemaRef` and required payload fields; field-stripping reuses the proven `_strip_disallowed` path.

## Migration Plan

Additive, backwards-compatible. New events only start submitting once present in `REPORTABLE_EVENTS`. No settings migration, no data model changes. Rollback is reverting the change; in-flight behavior for existing schemas is unaffected.

## Open Questions

- None.
