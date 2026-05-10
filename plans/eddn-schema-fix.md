# Plan: Fix EDDN Schema Mismatches

## Root Cause
Multiple events are sent to `journal/1` schema but EDDN rejects them — they belong to dedicated schemas. Live Decky log confirms:
```
EDDN client error 400: 'FSSSignalDiscovered' is not one of ['Docked', 'FSDJump', 'Scan', 'Location', 'SAASignalsFound', 'CarrierJump', 'CodexEntry']
```

## Scope

### Events to FIX (dedicated EDDN schemas exist)
| Event | Current schema | Correct schema | Key changes |
|-------|---------------|----------------|-------------|
| FSSSignalDiscovered | journal/1 | **fsssignaldiscovered/1** | Batching into `signals[]`, flush triggers |
| FSSDiscoveryScan | journal/1 | **fssdiscoveryscan/1** | Requires `BodyCount`, `NonBodyCount`, `StarSystem` (not `SystemName`), augmented `StarPos` |
| NavRoute | journal/1 (auxiliary "journal") | **navroute/1** | Route entries need `StarClass`/`StarPos`; message-level requires only `timestamp`, `event`, `Route` + augmented horizons/odyssey |
| ApproachSettlement | journal/1 | **approachsettlement/1** | **StationName→Name field rename**; requires `BodyID`, `BodyName`, `MarketID`, `Latitude`, `Longitude`, `StarSystem`, `StarPos`, `SystemAddress`; Latitude/Longitude must NOT be stripped |
| CodexEntry | not implemented | **codexentry/1** | New event; requires `Name`, `Region`, `EntryID`, `BodyID`, `BodyName`, `StarSystem`, `StarPos`, `SystemAddress` |

### Events to ADD to journal/1
| Event | Notes |
|-------|-------|
| SAASignalsFound | In journal/1 enum but missing from REPORTABLE_EVENTS; REQUIRED_FIELDS: `["timestamp", "StarSystem", "SystemAddress"]` |

### Events to REMOVE (no EDDN schema)
| Event | Reason |
|-------|--------|
| ApproachBody | No EDDN schema accepts this |
| LeaveBody | No EDDN schema accepts this |
| SAAScanComplete | No EDDN schema accepts this |

### Bugs to FIX
1. **Latitude/Longitude in EDDN_DISALLOWED_FIELDS** — stripped for all events including approachsettlement/1 which requires them. Fix: remove from global set, add per-schema stripping with `keep_fields` override.
2. **CodexEntry fields VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered** — disallowed in journal/1 but valid in codexentry/1. Same per-schema stripping needed.
3. **MyReputation in Factions[]** — verify EDDN_FACTIONS_DISALLOWED_FIELDS is applied correctly.
4. **StationName→Name rename for ApproachSettlement** — the EDDN schema uses `Name`, the journal uses `StationName`. Transform must rename.
5. **StarPos augmentation failure for Docked** during initial scan before session_state is populated.

---

## Implementation Tasks

### Task 1: Update constants.py
- Add schema ref constants:
  - `EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/fsssignaldiscovered/1"`
  - `EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/fssdiscoveryscan/1"`
  - `EDDN_NAVROUTE_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/navroute/1"`
  - `EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/approachsettlement/1"`
  - `EDDN_CODEXENTRY_1_SCHEMA_REF = "https://eddn.edcd.io/schemas/codexentry/1"`
- Update REPORTABLE_EVENTS: remove ApproachBody, LeaveBody, SAAScanComplete; add SAASignalsFound, CodexEntry
- Update AUXILIARY_FILES: change NavRoute schema from "journal" to "navroute"
- Add DEDICATED_SCHEMA_EVENTS dict:
  ```python
  DEDICATED_SCHEMA_EVENTS: dict[str, dict[str, str]] = {
      "FSSSignalDiscovered": {"schema": "fsssignaldiscovered", "schema_ref": EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF},
      "FSSDiscoveryScan": {"schema": "fssdiscoveryscan", "schema_ref": EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF},
      "ApproachSettlement": {"schema": "approachsettlement", "schema_ref": EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF},
      "CodexEntry": {"schema": "codexentry", "schema_ref": EDDN_CODEXENTRY_1_SCHEMA_REF},
  }
  ```
- Remove Latitude, Longitude from EDDN_DISALLOWED_FIELDS
- Add `JOURNAL_1_ONLY_DISALLOWED = {"Latitude", "Longitude", "VoucherAmount", "Traits", "IsNewEntry", "NewTraitsDiscovered"}` — fields disallowed in journal/1 but valid in some dedicated schemas
- Add FSS_SIGNAL_DISALLOWED_FIELDS = `{"TimeRemaining", "event", "timestamp"}` — stripped from individual signals before batching

### Task 2: Update validator.py
- Add REQUIRED_FIELDS for SAASignalsFound: `["timestamp", "StarSystem", "SystemAddress"]`
- Update REQUIRED_FIELDS for ApproachSettlement: `["timestamp", "StarSystem", "SystemAddress", "BodyID", "BodyName", "Name", "MarketID", "Latitude", "Longitude"]` — note "Name" not "StationName"
- Modify `_strip_disallowed(obj, keep_fields=None)` — if `keep_fields` is provided, those keys are preserved even if they'd otherwise be stripped. Used for approachsettlement/1 (keep Latitude, Longitude) and codexentry/1 (keep VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered).
- For journal/1 `transform()`: add JOURNAL_1_ONLY_DISALLOWED to the stripping pass (Latitude, Longitude, VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered are disallowed in journal/1 specifically)
- Add `transform_fss_signal_discovered(signals_batch, session_state)`:
  - Builds fsssignaldiscovered/1 message with `signals[]` array
  - Message-level: timestamp (last signal), event, StarSystem, StarPos, SystemAddress, horizons, odyssey
  - Each signal: SignalName (required), plus optional IsStation, USSType, SpawningState, SpawningFaction, ThreatLevel, SignalType, SpawningPower, OpposingPower
  - Strip _Localised keys from signals
  - Schema ref: fsssignaldiscovered/1
- Add `transform_fss_discovery_scan(event, session_state)`:
  - Strip disallowed + _Localised, then build message
  - Requires: timestamp, StarSystem, StarPos, SystemAddress, BodyCount, NonBodyCount, horizons, odyssey
  - Optional: Progress
  - Augment StarPos from session_state if missing
  - Schema ref: fssdiscoveryscan/1
- Add `transform_navroute(auxiliary_data, session_state)`:
  - Strip disallowed + _Localised on message payload
  - Strip _Localised from Route entries
  - Message-level: timestamp, event, Route, StarSystem, StarPos, SystemAddress, horizons, odyssey
  - Augment StarPos/StarSystem/SystemAddress at message level from session_state if missing
  - Route entries: keep StarSystem, SystemAddress, StarPos, StarClass, Populated, NeutronStar as-is from NavRoute.json
  - Schema ref: navroute/1
- Add `transform_approach_settlement(event, session_state)`:
  - Strip disallowed + _Localised BUT keep Latitude, Longitude (pass keep_fields={"Latitude", "Longitude"})
  - Rename StationName→Name in message
  - Requires: timestamp, StarSystem, StarPos, SystemAddress, BodyID, BodyName, Name, MarketID, Latitude, Longitude, horizons, odyssey
  - Augment StarPos/StarSystem from session_state if missing
  - Schema ref: approachsettlement/1
- Add `transform_codex_entry(event, session_state)`:
  - Strip disallowed + _Localised BUT keep VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered (pass keep_fields)
  - Also strip JOURNAL_1_ONLY_DISALLOWED for journal/1 — but for codexentry/1, keep them
  - Requires: timestamp, StarSystem, StarPos, SystemAddress, Name, Region, EntryID, BodyID, BodyName, horizons, odyssey
  - Augment StarPos/StarSystem from session_state if missing
  - Schema ref: codexentry/1
- Verify Factions[] stripping includes MyReputation (already in EDDN_FACTIONS_DISALLOWED_FIELDS)

### Task 3: Add signal batcher module (src/modules/signal_batcher.py)
New module for FSSSignalDiscovered batching:
```python
class SignalBatcher:
    """Batches FSSSignalDiscovered events and flushes on trigger events."""
    
    FLUSH_TRIGGER_EVENTS = {"FSSDiscoveryScan", "SupercruiseEntry", "Location", "FSDJump", "CarrierJump", "Shutdown", "Music"}
    
    def __init__(self):
        self._signals: list[dict] = []
        self._last_timestamp: str | None = None
        self._system_address: int | None = None
        self._star_system: str | None = None
        self._star_pos: list[float] | None = None
    
    def add_signal(self, event: ParsedEvent) -> None:
        """Add a FSSSignalDiscovered event to the batch.
        
        Extracts all fields from raw event EXCEPT TimeRemaining, event, timestamp,
        and _Localised keys. Preserves SignalType, SpawningPower, OpposingPower
        etc. alongside the standard fields.
        """
        # Extract signal data from event.raw, stripping FSS_SIGNAL_DISALLOWED_FIELDS and _Localised
        # Update _last_timestamp, _system_address, _star_system, _star_pos from event.raw
    
    def should_flush(self, event_type: str) -> bool:
        """Check if an incoming event should trigger a flush."""
        return event_type in self.FLUSH_TRIGGER_EVENTS
    
    def is_system_change(self, event_type: str) -> bool:
        """Check if event indicates a system change (clears batch)."""
        return event_type in {"FSDJump", "Location", "CarrierJump"}
    
    def flush(self) -> dict | None:
        """Return accumulated batch data for transform, or None if empty.
        
        Returns dict with: signals, last_timestamp, system_address, star_system, star_pos
        Clears internal state.
        """
        if not self._signals:
            return None
        result = {
            "signals": self._signals,
            "last_timestamp": self._last_timestamp,
            "system_address": self._system_address,
            "star_system": self._star_system,
            "star_pos": self._star_pos,
        }
        self._signals = []
        self._last_timestamp = None
        return result
    
    def clear(self) -> None:
        """Discard accumulated signals (e.g., on system change)."""
        self._signals = []
        self._last_timestamp = None
```

### Task 4: Update watcher.py
The `_process_reportable_event()` method needs a new routing structure:

```python
async def _process_reportable_event(self, event, source_filepath=None):
    event_type = event.event_type
    
    # 1. FSSSignalDiscovered → batch (not immediate submit)
    if event_type == "FSSSignalDiscovered":
        self._signal_batcher.add_signal(event)
        return
    
    # 2. Check if this event should flush the signal batcher
    if self._signal_batcher.should_flush(event_type):
        batch = self._signal_batcher.flush()
        if batch:
            message = self.validator.transform_fss_signal_discovered(batch, self.parser.session_state)
            if message:
                await self.submitter.submit(message, event_name="FSSSignalDiscovered")
        # If system change, clear any remaining batch (already handled by flush)
    
    # 3. Dedicated schema events (FSSDiscoveryScan, ApproachSettlement, CodexEntry)
    if event_type in DEDICATED_SCHEMA_EVENTS:
        if event_type == "FSSDiscoveryScan":
            validated = self.validator.validate(event, self.parser.session_state)
            if not validated:
                return
            message = self.validator.transform_fss_discovery_scan(event, self.parser.session_state)
        elif event_type == "ApproachSettlement":
            validated = self.validator.validate(event, self.parser.session_state)
            if not validated:
                return
            message = self.validator.transform_approach_settlement(event, self.parser.session_state)
        elif event_type == "CodexEntry":
            validated = self.validator.validate(event, self.parser.session_state)
            if not validated:
                return
            message = self.validator.transform_codex_entry(event, self.parser.session_state)
        if message:
            await self.submitter.submit(message, event_name=event_type)
        return
    
    # 4. Auxiliary file events (Market, Outfitting, Shipyard, NavRoute)
    if event_type in AUXILIARY_FILES:
        # ... existing logic, but NavRoute now routes to transform_navroute
        # The _prepare_auxiliary_submission transformers dict needs a "navroute" entry
        # pointing to validator.transform_navroute
        ...
    
    # 5. Journal/1 events (FSDJump, Scan, Location, Docked, CarrierJump, SAASignalsFound)
    validated = self.validator.validate(event, self.parser.session_state)
    if not validated:
        return
    message = self.validator.transform(event, self.parser.session_state)
    await self.submitter.submit(message)
```

- Add SignalBatcher instance to `__init__`
- Add `"navroute"` entry to the `transformers` dict in `_prepare_auxiliary_submission()` pointing to `validator.transform_navroute`
- Import DEDICATED_SCHEMA_EVENTS from constants

### Task 5: Update main.py
- Import SignalBatcher
- Pass SignalBatcher to JournalWatcher constructor

### Task 6: Update README.md and AGENTS.md
- Update EDDN event coverage tables
- Remove ApproachBody, LeaveBody, SAAScanComplete from journal/1 table
- Add dedicated schema tables for fsssignaldiscovered/1, fssdiscoveryscan/1, navroute/1, approachsettlement/1, codexentry/1
- Add SAASignalsFound to journal/1 table
- Document signal batching behavior
- Update module list to include signal_batcher.py

---

## Test Plan (write tests FIRST)

### test_constants.py
- Verify REPORTABLE_EVENTS does NOT contain ApproachBody, LeaveBody, SAAScanComplete
- Verify REPORTABLE_EVENTS DOES contain SAASignalsFound, CodexEntry
- Verify new schema ref constants are correct URLs
- Verify Latitude/Longitude removed from EDDN_DISALLOWED_FIELDS
- Verify JOURNAL_1_ONLY_DISALLOWED contains Latitude, Longitude, VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered
- Verify AUXILIARY_FILES NavRoute schema is "navroute"
- Verify DEDICATED_SCHEMA_EVENTS has correct entries for FSSSignalDiscovered, FSSDiscoveryScan, ApproachSettlement, CodexEntry

### test_signal_batcher.py (NEW)
- Test add_signal accumulates signals correctly
- Test flush returns correct batch data
- Test flush clears internal state
- Test should_flush returns True for trigger events (FSSDiscoveryScan, SupercruiseEntry, Location, FSDJump, CarrierJump, Shutdown, Music)
- Test should_flush returns False for non-trigger events
- Test empty flush returns None
- Test is_system_change for FSDJump, Location, CarrierJump
- Test signal field extraction preserves all fields (SignalName, IsStation, USSType, SpawningState, SpawningFaction, ThreatLevel, SignalType, SpawningPower, OpposingPower)
- Test disallowed fields stripped (TimeRemaining, event, timestamp)
- Test _Localised keys stripped from signals
- Test batch with multiple signals from different events

### test_validator.py (updates)
- **Update parametrized tests**: remove ApproachBody, LeaveBody, SAAScanComplete test cases; add SAASignalsFound, CodexEntry, FSSDiscoveryScan, ApproachSettlement (dedicated schema) cases
- Test SAASignalsFound REQUIRED_FIELDS
- Test transform_fss_signal_discovered with valid batch
- Test transform_fss_signal_discovered with empty signals returns None
- Test transform_fss_signal_discovered schema ref is fsssignaldiscovered/1
- Test transform_fss_signal_discovered preserves SignalName, IsStation, USSType, SpawningState, SpawningFaction, ThreatLevel, SignalType
- Test transform_fss_discovery_scan with BodyCount, NonBodyCount
- Test transform_fss_discovery_scan schema ref
- Test transform_fss_discovery_scan augments StarPos from session_state
- Test transform_navroute with Route entries containing StarPos, StarClass
- Test transform_navroute schema ref
- Test transform_navroute augments StarPos/StarSystem at message level
- Test transform_approach_settlement preserves Latitude, Longitude
- Test transform_approach_settlement renames StationName→Name
- Test transform_approach_settlement schema ref
- Test transform_codex_entry with all required fields
- Test transform_codex_entry schema ref
- Test transform_codex_entry preserves VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered
- Test Latitude/Longitude not stripped in approachsettlement context (keep_fields)
- Test Latitude/Longitude ARE stripped in journal/1 context
- Test Factions MyReputation is stripped
- Test StarPos augmentation works for Docked when session_state populated

### test_watcher.py (updates)
- Test FSSSignalDiscovered routes to batcher not immediate submit
- Test FSSDiscoveryScan triggers flush and uses fssdiscoveryscan/1
- Test NavRoute uses navroute/1 schema
- Test ApproachSettlement uses approachsettlement/1 schema
- Test CodexEntry uses codexentry/1 schema
- Test SAASignalsFound routes through journal/1
- Test ApproachBody/LeaveBody/SAAScanComplete are ignored (not reportable)
- Test FSDJump triggers signal batch flush before processing itself
- Test system change (FSDJump) flushes and clears signal batcher

### test_parser.py (updates)
- Remove ApproachBody, LeaveBody, SAAScanComplete from is_reportable tests
- Add SAASignalsFound, CodexEntry to is_reportable tests

---

## Acceptance Criteria
- All existing tests pass (backward compatible for journal/1 events: FSDJump, Scan, Location, Docked, CarrierJump)
- All new tests pass
- FSSSignalDiscovered batches correctly and submits to fsssignaldiscovered/1
- FSSDiscoveryScan submits to fssdiscoveryscan/1 with BodyCount, NonBodyCount
- NavRoute submits to navroute/1 with proper fields
- ApproachSettlement submits to approachsettlement/1 with Latitude/Longitude and StationName→Name rename
- CodexEntry submits to codexentry/1
- SAASignalsFound submits to journal/1
- ApproachBody, LeaveBody, SAAScanComplete are no longer reportable
- Latitude/Longitude are not stripped for approachsettlement/1 but ARE stripped for journal/1
- CodexEntry fields (VoucherAmount, Traits, IsNewEntry, NewTraitsDiscovered) are preserved in codexentry/1 but stripped in journal/1
- No MyReputation leakage in Factions[]
- README and AGENTS.md updated
