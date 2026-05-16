# Plan: Implement FCMaterials and NavBeaconScan EDDN Schemas

## Overview
Add support for two new EDDN schemas:
1. **navbeaconscan/1** — NavBeaconScan journal event (dedicated schema)
2. **fcmaterials_journal/1** — FCMaterials.json auxiliary file (auxiliary schema)

---

## Schema Analysis

### NavBeaconScan → navbeaconscan/1
- **Source:** Journal event `NavBeaconScan`
- **Required fields:** `timestamp`, `event`, `StarSystem`, `StarPos`, `SystemAddress`, `NumBodies`
- **Augmentations required:** horizons, odyssey, StarSystem (from session_state), StarPos (from session_state)
- **Pattern:** Dedicated schema event (like FSSDiscoveryScan, ApproachSettlement, CodexEntry)
- **Disallowed:** `_Localised` keys (all levels), `additionalProperties: false`

### FCMaterials → fcmaterials_journal/1
- **Source:** Journal event `FCMaterials` + sidecar `FCMaterials.json`
- **Required fields:** `timestamp`, `event`, `MarketID`, `CarrierName`, `CarrierID`, `Items`
- **Items required:** `id`, `Name`, `Price`, `Stock`, `Demand`
- **Disallowed in Items:** `_Localised` keys
- **Augmentations required:** horizons, odyssey
- **Pattern:** Auxiliary file event (like Market, Outfitting, Shipyard, NavRoute)
- **`additionalProperties: false`** — strict schema

---

## Task Breakdown

### Phase 1: Tests First

#### NavBeaconScan Tests
1. `test_navbeaconscan_required_fields_valid` — valid event passes validation
2. `test_navbeaconscan_missing_num_bodies_rejected` — missing NumBodies fails validation
3. `test_navbeaconscan_transform_basic` — transforms with correct schema ref
4. `test_navbeaconscan_transform_augments_star_pos` — StarPos from session_state
5. `test_navbeaconscan_transform_augments_star_system` — StarSystem from session_state
6. `test_navbeaconscan_transform_strips_localised` — _Localised stripped recursively
7. `test_navbeaconscan_transform_rejects_wrong_system` — SystemAddress mismatch
8. `test_navbeaconscan_in_reportable_events` — constants check
9. Integration: watcher routes to dedicated schema transform + submission

#### FCMaterials Tests
1. `test_fcmaterials_transform_basic` — transforms valid FCMaterials.json
2. `test_fcmaterials_transform_strips_localised` — _Localised stripped from Items
3. `test_fcmaterials_transform_empty_items_returns_none` — no Items → None
4. `test_fcmaterials_transform_missing_marketid_returns_none`
5. `test_fcmaterials_transform_missing_carrierid_returns_none`
6. `test_fcmaterials_transform_missing_carriername_returns_none`
7. `test_fcmaterials_transform_augments_horizons_odyssey`
8. `test_fcmaterials_in_auxiliary_files` — constants check
9. `test_fcmaterials_schema_ref` — correct fcmaterials_journal/1 ref
10. Integration: FCMaterials event triggers FCMaterials.json read + submission

### Phase 2: Implementation

#### Constants (constants.py)
- Add `EDDN_NAVBEACONSCAN_1_SCHEMA_REF`
- Add `EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF`
- Add `NavBeaconScan` to `REPORTABLE_EVENTS`
- Add `FCMaterials` to `REPORTABLE_EVENTS`
- Add `NavBeaconScan` to `DEDICATED_SCHEMA_EVENTS`
- Add `FCMaterials` to `AUXILIARY_FILES` with schema type `"fcmaterials"`
- Update `AuxiliarySchemaType` Literal to include `"fcmaterials"`

#### Validator (validator.py)
- Add `NavBeaconScan` to `REQUIRED_FIELDS` with: `["timestamp", "NumBodies"]`
  - StarSystem/StarPos/SystemAddress augmented from session_state
- Add `transform_navbeacon_scan()` method:
  - Strip _Localised recursively
  - Augment StarPos from session_state (with SystemAddress cross-check)
  - Augment StarSystem from session_state (with SystemAddress cross-check)
  - Add horizons/odyssey
  - Return EDDN message with `EDDN_NAVBEACONSCAN_1_SCHEMA_REF`
- Add `transform_fc_materials()` method:
  - Validate required fields (MarketID, CarrierName, CarrierID, Items)
  - Strip _Localised from each Item
  - Add horizons/odyssey
  - Return EDDN message with `EDDN_FCMATERIALS_JOURNAL_1_SCHEMA_REF`
  - Return None if missing required fields or empty Items

#### Watcher (watcher.py)
- Add `NavBeaconScan` to `_process_dedicated_schema_event` dispatch
- FCMaterials handled automatically via AUXILIARY_FILES + auxiliary flow
  - Need to add dispatch in `_prepare_auxiliary_submission` for `"fcmaterials"` schema

### Phase 3: Integration Tests
- Watcher routing tests for both events
- End-to-end flow: event detection → parse → validate → transform → submit

---

## File Changes Summary
| File | Changes |
|------|---------|
| `src/modules/constants.py` | 2 new schema refs, 2 new reportable events, 1 new dedicated entry, 1 new auxiliary entry, update Literal type |
| `src/modules/validator.py` | 1 new required fields entry, 2 new transform methods |
| `src/modules/watcher.py` | 1 new dispatch entry for dedicated schema, 1 for auxiliary |
| `tests/test_validator.py` | ~15 new tests |
| `tests/test_constants.py` | ~6 new tests |
| `tests/test_watcher.py` | ~4 new integration tests |
