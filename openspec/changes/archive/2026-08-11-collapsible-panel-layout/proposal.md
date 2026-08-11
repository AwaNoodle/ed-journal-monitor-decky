## Why

The panel has grown by accretion — each EDSM feature added a section — and is now a single flat scroll of seven sections with roughly fifteen gamepad focus stops. On a Steam Deck every text field, button, and toggle is a D-pad stop, so reaching the in-flight information means traversing setup UI that is configured once and never revisited. Sections are grouped by *subject* (Configuration, EDSM) rather than by *how often the player looks at them*, which puts the most-read content behind the least-used controls. The `EDSM` section compounds this by holding three unrelated things — write credentials, keyless read lookups, and notification preferences — under a vendor name, implying (wrongly) that the API key gates lookups.

## What Changes

- Reorganise the panel into four frequency-ordered tiers: an always-visible **health strip** and **Navigation** and **Session** sections, then collapsed **Data flow**, **Setup**, and **Troubleshooting** sections.
- Introduce a **collapsible section** control (`@decky/ui` 4.11.3 ships none; built locally from `Field`'s `focusable`/`onActivate`/`icon` props). Collapsed children unmount, so they are removed from the gamepad focus path entirely — reducing the default state from ~15 focus stops to 4.
- Collapsed section headers carry a **state summary** (e.g. `Data flow  ✅ 248  ❌ 0`), so the common "is data still flowing?" glance is answered without expanding anything.
- Collapse state **resets on every panel open**; the flight view is always the default. One override: **Data flow auto-expands when the error count is non-zero**.
- Merge `ED Status`, `Journal Status`, and the `Watch journal` toggle into a single-line **health strip** using worst-state-wins. The toggle moves into `Setup ▸ Journal path` (used for initial configuration only).
- Make the **Next hop** block permanent rather than conditional, with a fixed footprint so the panel does not jump as routes change.
- **BREAKING (internal payload)**: add a `reason` field to the `edsm_next_hop` event payload. The current `neutral_next_hop()` collapses *no route / final hop / off route / disabled / failed* into one indistinguishable `system: null`. That was invisible while the block was conditional; a permanent block must state which case it is — notably "final hop, destination reached", which is useful information currently rendered as nothing.
- Merge `Recent Activity` and `Recent Errors` into one time-ordered feed inside **Data flow**, alongside the per-target counters (currently buried under `Journal Status`). Failures remain distinguishable by their existing ❌ marker and target badge, and gain the context of what succeeded around them.
- Split the `EDSM` section into **`Setup ▸ EDSM account`** (write path, requires an API key) and **`Setup ▸ EDSM lookups`** (read path, keyless), removing the false implication that the key gates lookups.
- When EDSM lookups are off, the **Find Nearest Scoopable Star** button becomes self-enabling: it reads `Enable EDSM lookups to search`, and pressing it turns lookups on and runs the search in one action, rather than dead-ending on advisory text pointing at a toggle now two drawers deep.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `plugin-ui`: Restructures the panel into collapsible frequency-ordered sections; replaces the three status rows with a single health strip; relocates the enable/disable toggle into Setup; splits EDSM settings into account and lookups groups; changes the nearest-scoopable action's disabled behaviour to self-enabling.
- `edsm-system-lookup`: The next-hop preview payload gains a `reason` discriminator so a neutral preview states *why* there is no next hop.
- `session-dashboard`: The Next hop block becomes permanently rendered with a fixed footprint, including its empty states.
- `error-display`: Recent Errors ceases to be a standalone section; failures render in the merged Data flow feed, whose collapsed header surfaces the error count and which auto-expands when errors exist.

## Impact

- **Frontend**: `src/Content.tsx` (the bulk — restructure, new local collapsible component, health strip, permanent next-hop states, self-enabling button), `src/types.d.ts` (`EdsmNextHopPreview.reason`).
- **Backend**: `src/modules/edsm_next_hop_consumer.py` (`neutral_next_hop()` gains `reason`; emit sites pass the specific cause), `src/modules/edsm_next_hop.py` (`NextHopTracker` already distinguishes these cases internally to return `None` — it must now report which). `main.py` rehydration via `get_status` carries the field through.
- **Dependencies**: none added. The collapsible is built from existing `@decky/ui` primitives.
- **Testing**: backend `reason` discrimination is unit-testable against `NextHopTracker`; the layout itself needs on-device verification, particularly the health strip states and gamepad focus traversal.
- **Out of scope**: persisting collapse state across panel opens (explicitly rejected — reset-every-open plus the error auto-expand covers the need without new settings keys); relocating the nearest-scoopable action out of Navigation (revisit if more on-demand tools are added); any change to EDDN/EDSM submission behaviour.
