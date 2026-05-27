## Why

EDDN accepts `FSSAllBodiesFound` events (scanned-all-bodies-in-system), but this plugin does not yet support them. Adding this event improves coverage of journal-to-EDDN reporting, giving commanders credit for full system scans.

## What Changes

- Add `FSSAllBodiesFound` as a reportable journal event
- Map it to the dedicated EDDN schema `fssallbodiesfound/1`
- Augment the event with `StarPos` from session state (not present in the journal event)
- Include `horizons`/`odyssey` flags and `gameversion`/`gamebuild` headers (existing patterns)
- Validate required fields: `timestamp`, `event`, `SystemName`, `StarPos`, `SystemAddress`, `Count`
- Add tests for validation and transform logic

## Capabilities

### New Capabilities
- `fssallbodiesfound-support`: Parse, validate, transform, and submit `FSSAllBodiesFound` journal events to EDDN using the `fssallbodiesfound/1` schema

### Modified Capabilities
<!-- No existing spec requirements change; this is a pure addition -->

## Impact

- `src/modules/constants.py`: New schema ref, added to `REPORTABLE_EVENTS` and `DEDICATED_SCHEMA_EVENTS`
- `src/modules/validator.py`: New `REQUIRED_FIELDS` entry, new `transform_fss_all_bodies_found()` method
- `src/modules/watcher.py`: One-line dispatch entry in `transform_dispatch`
- `tests/`: New test file(s) for validation and transform
