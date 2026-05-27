## Context

The plugin currently supports 17 reportable EDDN events across three routing categories: journal/1 (generic), dedicated schemas (FSSDiscoveryScan, ApproachSettlement, CodexEntry, NavBeaconScan), and auxiliary files (Market, Outfitting, Shipyard, NavRoute, FCMaterials). FSSAllBodiesFound is an event from the Elite Dangerous journal triggered when a commander has scanned all bodies in a star system. EDDN accepts it via the `fssallbodiesfound/1` schema but the plugin does not yet support it.

## Goals / Non-Goals

**Goals:**
- Parse `FSSAllBodiesFound` journal events and route them through the dedicated schema path
- Validate required fields per the EDDN schema
- Transform into a valid `fssallbodiesfound/1` message with StarPos augmentation and horizons/odyssey flags
- Submit to EDDN with gameversion/gamebuild headers (handled by existing submitter)
- Add tests for validation and transform

**Non-Goals:**
- No batching (single-event submission, unlike FSSSignalDiscovered)
- No new dependencies or architectural changes
- No UI changes (event appears in existing activity log automatically)

## Decisions

### Route as a dedicated schema event

FSSAllBodiesFound uses its own EDDN schema (`fssallbodiesfound/1`), not the generic journal/1 schema. It fits the existing `DEDICATED_SCHEMA_EVENTS` pattern alongside FSSDiscoveryScan and NavBeaconScan — same routing, same transform dispatch, same validation approach.

**Alternatives considered:**
- *journal/1 routing*: Would require stripping fields and re-adding them per EDDN rules, but the dedicated schema has a different structure (SystemName vs StarSystem, explicit Count field). Dedicated schema is cleaner.

### Reuse existing StarPos augmentation pattern

The journal event does not include `StarPos`. The schema requires it. We reuse the same pattern as FSSDiscoveryScan: augment from `session_state.star_pos` (cached from the last FSDJump/CarrierJump/Location), with SystemAddress cross-check to prevent stale coordinates.

**Alternatives considered:** None — this is the established pattern for all events lacking native StarPos.

### Count field: direct passthrough

The journal's `Count` maps 1:1 to the schema's `Count` (number of bodies in the system). No transformation needed.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| StarPos stale if no FSDJump/Location/CarrierJump seen in current session | Validation rejects the event (same as existing events that need StarPos augmentation) |
| SystemAddress mismatch between event and cached position | Cross-check already built into augmentation logic — event is rejected if mismatched |
| Schema changes in future EDDN updates | Schema ref is versioned (`/1`); future versions would require explicit update |
