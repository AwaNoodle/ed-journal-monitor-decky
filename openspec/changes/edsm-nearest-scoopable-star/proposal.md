## Why

Running low on fuel far from a station is a real failure mode in exploration, and the game gives no help finding the nearest scoopable (KGBFOAM) star. On a Steam Deck with no second screen, the player can't easily consult a map. EDSM's `sphere-systems` endpoint, with primary-star data, answers "where's my nearest fuel?" on demand — reusing the read foundation already in place.

## What Changes

- Extend the EDSM read client to query `api-v1/sphere-systems` around the current system, requesting primary-star information.
- Add a **nearest scoopable star** lookup: from the sphere result, find the closest system whose primary star is scoopable, returning its name, distance, and star class.
- Trigger this **on demand** (a button/action in the panel) rather than automatically on every arrival — it is a "help me now" action, and keeps sphere traffic minimal. Gated by the same EDSM auto-lookup toggle.
- Display the result (nearest scoopable system + distance + class) in the panel, with clear in-flight/unavailable states.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `edsm-system-lookup`: Adds a `sphere-systems` read and an on-demand nearest-scoopable-star computation from the current system, using the existing read client, toggle, and etiquette (distinct from the per-arrival cache since it is a radius query).
- `plugin-ui`: Adds an on-demand "nearest scoopable star" action and its result display.

## Impact

- **Depends on** `edsm-worth-scanning-lookup` (read client, SSL/UA, toggle). Adds one endpoint and an on-demand path.
- **Backend**: read client gains a `sphere-systems` fetch; a nearest-scoopable computation; a new callable to invoke it on demand and return the result.
- **Frontend**: `src/api.ts` + `src/types.d.ts` (new callable + result type), `src/Content.tsx` (button + result display).
- **External**: EDSM `api-v1/sphere-systems` — radius query, so potentially heavier than a single-system call; mitigated by being on-demand only, a bounded radius, and the toggle. No new pip packages.
- **Out of scope**: nearest *landable station* (EDSM has no clean nearest-station-with-service endpoint — deferred to a possible future Spansh-backed feature); automatic low-fuel triggering (possible future enhancement).
