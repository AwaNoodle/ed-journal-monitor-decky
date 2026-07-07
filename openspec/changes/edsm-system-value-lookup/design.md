## Context

This builds directly on `edsm-worth-scanning-lookup`, which introduces the EDSM read client, the per-system TTL cache, the arrival trigger (an `EdsmLookupConsumer` observing FSDJump/Location), the `edsm_lookups_enabled` toggle, and the verdict payload emitted to the frontend. This change adds a second endpoint (`estimated-value`) to that same machinery and a value summary derivation — no new architecture.

## Goals / Non-Goals

**Goals:**
- Fetch `api-system-v1/estimated-value` on the existing arrival trigger, through the existing cache and toggle.
- Derive a value summary: total estimated value + ranked priority bodies.
- Surface it as an EDSM-sourced display in the Session metric area, beside the worth-scanning chip.

**Non-Goals:**
- Any new client, cache, trigger, or toggle — all reused from the foundation.
- First-mapped bonus math or per-player value personalization.
- Next-in-route or nearest lookups.

## Decisions

**Fetch value alongside bodies in the same arrival lookup.**
Both queries are keyed by the same system and share a trigger; issuing them together (concurrently) keeps to one logical lookup per arrival and one cache entry per system. Alternative — a separate trigger/consumer — was rejected as duplicative.

**Extend the existing verdict payload rather than a second event.**
The frontend already consumes a per-system payload; add `value` fields (`{ totalValue, priorityBodies: [{name, value}] }`) to it. One event, one rehydrate path, one chip cluster. Keeps the frontend simple.

**Treat value as a floor, label it as such.**
EDSM's estimated value omits the first-mapped bonus and unknown bodies. The display communicates "estimate" so players don't treat it as exact.

## Risks / Trade-offs

- **[Two requests per arrival instead of one]** → Issue concurrently, share the cache entry and TTL; still bounded to one arrival's worth of traffic and still gated by the toggle.
- **[estimated-value field/shape assumptions]** → Pin the response shape (total + valued bodies) against a captured sample; unit-test the summary derivation over fixtures.
- **[Small-screen clutter with the worth-scanning chip]** → Compact display (total + top N priority bodies); neutral when absent.

## Open Questions

- How many priority bodies to show on the Deck's small screen (top 3?).
- Whether to show per-body value or just names + system total.
