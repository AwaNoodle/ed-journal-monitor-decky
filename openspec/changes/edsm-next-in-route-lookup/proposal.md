## Why

When following a plotted route, the most useful look-ahead is *the next system I'm about to jump to* — is its star scoopable (so I don't strand myself), and is it already discovered or worth a detour? The plugin already parses `NavRoute.json` for EDDN, so the plotted route is in hand; combined with the EDSM read foundation, it can preview the next hop before the player jumps.

## What Changes

- Read the plotted route from `NavRoute.json` (already parsed) and identify the **next system** relative to the player's current system.
- On route change and after each jump, run an EDSM lookup for that next system and produce a **next-hop preview**: primary-star scoopability (fuel safety), and the worth-scanning verdict / value if available.
- Surface the preview as an EDSM-sourced "next hop" chip in the Session dashboard metric area (glanceable before the jump), with neutral states when there is no route or the lookup is unavailable.
- Reuse the existing read client, cache, toggle, and verdict/value derivations — pointed one system ahead instead of at the current system.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `edsm-system-lookup`: Adds a next-in-route trigger (derive the next system from `NavRoute.json` on route change / after a jump) and a next-hop lookup that reuses the existing per-system read/cache to produce a next-hop preview (scoopability + verdict/value).
- `session-dashboard`: The metric area gains an EDSM-sourced "next hop" preview for the next system in the plotted route, with neutral states when there is no route or no data.

## Impact

- **Depends on** `edsm-worth-scanning-lookup` (read client, cache, toggle, verdict). Reuses `edsm-system-value-lookup`'s value summary if present (graceful when absent).
- **Backend**: parse/track the next system from `NavRoute.json`; a next-hop lookup reusing the per-system read + cache; emit the next-hop preview payload.
- **Frontend**: `src/types.d.ts` (next-hop preview fields), `src/Content.tsx` (next-hop chip in the Session section).
- **External**: EDSM per-system reads for the next hop — same caching/etiquette/toggle; no new endpoint types beyond those in changes 1/2; no new pip packages.
- **Out of scope**: full multi-hop route preview (only the immediate next system); nearest lookups; honk reconciliation.
