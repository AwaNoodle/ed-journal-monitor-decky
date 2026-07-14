## Context

Builds on `edsm-worth-scanning-lookup` (read client, per-system cache, toggle, verdict) and optionally `edsm-system-value-lookup` (value summary). The plugin already parses `NavRoute.json` for EDDN's navroute schema, so the plotted route is available in-process — this change reads the *next* system from it and points the existing per-system lookup one hop ahead.

## Goals / Non-Goals

**Goals:**
- Track the next system in the plotted route from `NavRoute.json`, updating on route change and after each jump.
- Produce a next-hop preview (scoopability + verdict/value when available) via the existing per-system read/cache.
- Surface it as an EDSM-sourced "next hop" chip in the Session metric area.

**Non-Goals:**
- Multi-hop / full-route preview — only the immediate next system.
- New endpoints — reuses per-system reads from changes 1/2.
- Route *planning* (that is Spansh territory) — this only previews an already-plotted route.

## Decisions

**Derive next hop from `NavRoute.json`, matched against the current system.**
The route is an ordered list of systems; the "next hop" is the entry after the player's current system (from the arrival/session state). Re-evaluate on NavRoute change and on each FSDJump. Alternative — reading the in-game target from Status.json — is less reliable for full-route context; NavRoute gives the whole plotted path.

**Reuse the per-system cache for the next hop.**
The next hop is just another system name; run it through the same read + TTL cache. Frequently the next hop becomes the current system on the following jump, so a cache hit is likely — cheap and etiquette-friendly.

**Graceful composition with value feature.**
If `edsm-system-value-lookup` is present, include value in the preview; if not, the preview carries scoopability + verdict only. The preview payload treats value as optional so the two changes compose in either order.

**Emit as part of the existing per-system payload family.**
Add a `nextHop` preview object to the emitted status/session payload; the frontend renders it as a distinct chip. One event path, rehydrate-on-open supported.

## Risks / Trade-offs

- **[Current-system matching in the route]** Determining "which entry is next" depends on correctly matching the current system within the route list. → Match on system name/address from session state; unit-test with fixtures (mid-route, final hop, off-route, no route).
- **[Route staleness]** `NavRoute.json` reflects the last plot; if the player re-plots, re-read on its change. → Trigger on NavRoute updates, not just jumps.
- **[Extra per-jump lookup]** One additional per-system read per jump for the next hop. → Cache-backed and toggle-gated; usually a cache hit on the subsequent jump.

## Open Questions

- Match the current system by name or SystemAddress (address is more robust against name edge cases) — confirm what session state carries.
- Whether to preview only scoopability by default and fold in verdict/value only when those features are enabled, to keep the chip compact on a small screen.
