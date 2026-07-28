## Context

Builds on `edsm-worth-scanning-lookup` (read client, UA/SSL, toggle). Unlike the worth-scanning and value features, this is a **radius query** (`sphere-systems`) triggered **on demand**, not a single-system lookup on arrival — so it does not share the per-arrival cache and does not run automatically.

## Goals / Non-Goals

**Goals:**
- A `sphere-systems` read (bounded radius, primary-star info) on the existing client.
- An on-demand "nearest scoopable star" computation returning system + distance + class.
- A panel action + result display with clear states, gated by the auto-lookup toggle.

**Non-Goals:**
- Nearest landable station (no clean EDSM endpoint — deferred, likely Spansh).
- Automatic low-fuel triggering (possible future enhancement).
- Reusing the per-arrival cache (radius queries are point-in-time and user-initiated).

## Decisions

**On-demand, not on-arrival.** A sphere query is heavier than a single-system call and is only needed when the player actually wants it (low fuel / route planning). A button avoids per-jump radius traffic against a free community service. Alternative — auto-fire when Status.json fuel drops below a threshold — is deferred as a future enhancement to avoid scope creep and extra triggers here.

**New callable returning a result, not an emitted stream.** Because it is user-initiated and one-shot, a request/response callable fits better than the arrival event stream. The frontend shows in-flight → result.

**Bounded radius constant.** Pick a sensible default radius (e.g. tens of ly) to keep the response small and fast; scoopable stars are common enough that a modest radius suffices.

## Risks / Trade-offs

- **[Radius query heavier than single-system]** → On-demand only, bounded radius, toggle-gated; not cached (acceptable — infrequent, user-initiated).
- **[Sparse coverage far from populated space]** → sphere-systems reflects EDSM's uploaded systems; out in the black results may be thin. Handle "none found within radius" explicitly.
- **[primary-star scoopability field shape]** → Confirm the `sphere-systems` primary-star fields (type / isScoopable) against a captured sample; unit-test the nearest computation over fixtures.

## Open Questions

- Default radius value (balance coverage vs. response size).
- Whether to later add automatic low-fuel triggering from Status.json (separate change).
