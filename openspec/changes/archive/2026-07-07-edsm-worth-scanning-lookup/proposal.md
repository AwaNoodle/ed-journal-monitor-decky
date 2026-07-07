## Why

On a Steam Deck, the Decky panel is the only "second screen" an Elite Dangerous player has while the game runs fullscreen under Proton. Today the plugin is a one-way relay (journal → EDDN/EDSM) with a passive session dashboard; it never tells the player anything they don't already know. The most valuable in-the-moment question an explorer asks on arrival in a system — *"is this worth my time to scan, or has someone already tagged everything?"* — currently requires alt-tabbing to a browser. EDSM's public system data can answer it in a glanceable chip, and this change also lays the shared read-side foundation that later EDSM lookups (system value, next-in-route, nearest scoopable star) will reuse.

## What Changes

- Add a **read-side EDSM client** (GET against the public `api-system-v1` endpoints) — the current EDSM code is write-only (POST to `api-journal`). Reuses the existing custom User-Agent (EDSM 403s the default urllib UA behind Cloudflare) and the shared `build_ssl_context()`.
- Add a **TTL system-lookup cache** keyed by system name, so re-jumping through a known system never re-hits EDSM.
- Add an **arrival trigger**: on `FSDJump`/`Location`, fire a single lookup for the entered system (once per system, non-blocking, never gating submission).
- Add a **"worth scanning" verdict** for the arrived system, computed from `api-system-v1/bodies`:
  - **GREEN** — system unknown to EDSM (high-confidence virgin) or no known bodies discovered/mapped
  - **YELLOW** — some but not all known bodies discovered or mapped
  - **RED** — all known bodies discovered *and* mapped (no first-discovery/first-mapped bonus left)
- Render the verdict as an **EDSM-sourced chip in the Session dashboard metric area** (glanceable, not a new panel section). The chip is explicitly labelled as EDSM-sourced because EDSM only knows uploaded bodies — before honking, the verdict reflects EDSM's records, not ground truth.
- Add an **enable/disable toggle for EDSM auto-lookups** in the existing EDSM configuration section. When off, no read calls are made. This is independent of the EDSM forwarding API key — read endpoints are public and need no key.
- All EDSM read calls are **fully isolated** from the EDDN and EDSM-write paths; a read failure or EDSM outage never affects submission.

## Capabilities

### New Capabilities
- `edsm-system-lookup`: Read-side EDSM integration — public `api-system-v1` GET client, TTL per-system cache, arrival-triggered lookup, the auto-lookup enable toggle, and the "worth scanning" (red/yellow/green) verdict logic with its EDSM-completeness caveat.

### Modified Capabilities
- `session-dashboard`: The metric area gains an EDSM-sourced "worth scanning" chip for the current system, with a neutral state when lookups are disabled, unavailable, or in flight.
- `plugin-ui`: The EDSM configuration section gains the auto-lookup enable/disable toggle control.

## Impact

- **New backend module(s)**: an EDSM read client (sibling to `forwarders/edsm_client.py`), a system-lookup service (cache + verdict), wired as/through the stream-consumer / session-state path in `main.py`.
- **Settings**: new persisted key for the auto-lookup toggle (e.g. `edsm_lookups_enabled`).
- **Frontend**: `src/api.ts`, `src/types.d.ts` (new emitted verdict payload / status field), `src/Content.tsx` (config toggle + dashboard chip).
- **External dependency**: EDSM `api-system-v1/bodies` — a free community service; mitigated by aggressive caching, one call per arrival, and the toggle. Reuses existing `ssl_context` and UA handling; no new pip packages.
- **Out of scope (future sibling specs)**: system value / priority bodies (`estimated-value`), next-in-route look-ahead (NavRoute next hop), nearest scoopable star (`sphere-systems`), nearest landable station (deferred — EDSM has no clean nearest-station endpoint), and honk `BodyCount` reconciliation of the verdict.
