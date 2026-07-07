## Why

Once the player knows a system is *worth scanning* (the red/yellow/green verdict from `edsm-worth-scanning-lookup`), the next question is *how much is here and what should I map first?* The journal never reports a system's total value — the player has to guess or alt-tab. EDSM's `estimated-value` endpoint answers it directly, and this feature reuses the read foundation already built, so it is a cheap, high-value follow-on.

## What Changes

- Extend the EDSM read client to fetch `api-system-v1/estimated-value` for the arrived system, alongside the existing bodies lookup, on the same arrival trigger and through the same cache.
- Produce a **system value summary**: the system's total estimated scan value plus a short ranked list of **priority bodies** (highest-value bodies to map), each with its body name/type and estimated value.
- Surface the value summary in the Session dashboard metric area next to the worth-scanning chip (glanceable; total value + top priority bodies).
- Make explicit that the figure is a **floor** — it reflects EDSM's known bodies and excludes the first-mapped bonus the player would personally earn.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `edsm-system-lookup`: The arrival lookup additionally fetches `estimated-value` and derives a system value summary (total estimated value + ranked priority bodies), cached per system alongside the bodies result.
- `session-dashboard`: The metric area gains an EDSM-sourced system value display (total value + priority bodies) for the current system, with a neutral state when unavailable.

## Impact

- **Depends on** `edsm-worth-scanning-lookup` (read client, cache, arrival trigger, toggle, verdict payload) — reuses all of it; adds one endpoint and one derivation.
- **Backend**: read client gains an `estimated-value` fetch; the lookup service derives and caches the value summary; the emitted payload/`get_status` gains value fields.
- **Frontend**: `src/types.d.ts` (value fields on the verdict payload), `src/Content.tsx` (value display in the Session section).
- **External**: EDSM `api-system-v1/estimated-value` — same caching/etiquette and toggle as the bodies lookup; no new pip packages.
- **Out of scope**: next-in-route look-ahead, nearest lookups, honk reconciliation.
