## Context

`src/Content.tsx` renders seven `PanelSection`s in one flat scroll: Session, Status, Recent Activity, Configuration, EDSM, Recent Errors, Diagnostics. Each has accreted around a feature rather than around a reading frequency, and the file is now 799 lines with all layout inline.

The binding constraint is gamepad navigation. On a Steam Deck every `TextField`, `ButtonItem`, and `ToggleField` is a D-pad focus stop, and the panel currently has roughly fifteen of them. Eleven belong to Configuration and EDSM — sections the player configures once. Reaching the in-flight content means traversing setup UI on every visit.

Observed usage, from the plugin's author: mid-flight the scannable verdict and next-hop details are what get read; during a session, the counters; occasionally a check that data is still reaching EDDN and EDSM; configuration has been set once and not revisited since.

`@decky/ui` 4.11.3 exports no collapsible primitive — verified against `node_modules/@decky/ui/dist/components/` and `custom-components/`. Other Decky plugins (LSFG-VK) build their own.

## Goals / Non-Goals

**Goals:**

- Order the panel by reading frequency, not by subject.
- Cut the default focus-stop count from ~15 to 4, so mid-flight the D-pad never leaves the top of the panel.
- Answer "is data still flowing?" without expanding anything.
- Make the next-hop block permanent and informative in every state, including the currently-invisible "destination reached".
- Separate EDSM's write path (needs a key) from its read path (keyless).

**Non-Goals:**

- Persisting collapse state across panel opens.
- Any change to EDDN or EDSM submission behaviour, schemas, batching, or the activity log's data model.
- Restyling — colours, chips, and counter typography carry over as-is. This is structural.
- Relocating the nearest-scoopable action out of Navigation.

## Decisions

### Build the collapsible from `Field`, not a dependency

`Field` already exposes `focusable`, `onActivate`, `icon`, `bottomSeparator`, and `childrenLayout`. A local `CollapsibleSection` component — header `Field` plus conditionally-rendered children — is roughly twenty lines and inherits Steam's focus ring and footer-legend behaviour for free.

*Alternatives:* adding a third-party collapsible (new dependency, unlikely to match Steam's focus semantics); using `Dropdown` or `Tabs` (both exist in `@decky/ui`, but `Tabs` costs horizontal space the 
panel doesn't have, and neither degrades gracefully to "just a list of sections").

**Children must unmount, not be hidden with CSS.** This is the whole point: `display: none` keeps elements in the focus tree on Steam's navigation, so the focus-stop reduction would not materialise. Collapsed sections render `null` children.

### Header summaries are computed from state already in `Content.tsx`

The Data flow header's aggregate counts sum the existing per-target `targets` map; the Setup header's summary reads `journalPath`, `uploaderId`, `edsmApiKeySet`, and `edsmLookupsEnabled`. No new callables, no new backend state, no extra requests.

### Collapse state resets on open; one derived override

The Decky panel unmounts when closed, so plain `useState` in `Content` gives reset-on-open for free — the absence of persistence *is* the implementation.

Data flow's initial state is derived once on mount from whether the failure count is greater than zero, not held as a live effect. A failure arriving while the panel is open should not yank a section open under the player's hands; it will be expanded on the next open, and the header count changes immediately either way.

*Alternative rejected:* persisting collapse state to settings. Four new settings keys for pure UI state, and a stale expansion can persist for months. The header summaries remove most of the reason to expand at all.

### Health strip is a pure function of existing state, ordered by severity

`healthState(edRunning, watcherRunning, journalPath, enabled, commander)` returns one of five states, evaluated worst-first: no path → running-not-watching → paused → waiting → watching. Rendering it as a plain `div` rather than a `Field` keeps it out of the focus tree.

This is the change's biggest information loss: today ED Status and Journal Status are independently readable. The severity ordering is chosen so that every non-healthy combination surfaces its most actionable cause, and the states are enumerated in the spec so they can be walked through on-device.

### The next-hop `reason` discriminator belongs in the backend

`neutral_next_hop()` (`src/modules/edsm_next_hop_consumer.py:46`) collapses *no route / no hop / disabled / failed* into one `system: None` payload. That was sound while the UI rendered nothing for all four. A permanent block must say which case it is — and "final hop, destination reached" is genuinely useful information that currently renders as nothing at all.

`NextHopTracker.next_hop()` already distinguishes these cases internally in order to return `None`; it must now report which. The discriminator is derived from state the tracker holds, so it costs no additional request.

*Alternative rejected:* inferring the cause frontend-side. `edsmLookupsEnabled` is known locally, but no-route / final-hop / off-route are only knowable from the route array, which lives in the tracker. Inferring some causes and not others would produce a confusingly partial empty state.

`reason` is added as an optional field so a payload from a not-yet-updated backend still renders — the UI falls back to the generic no-route text when it is absent.

### Merge Recent Errors into the Data flow feed

Errors and activity are the same log filtered differently (`ActivityEntry`, already `target`-tagged, already carrying `outcome`). A separate section meant a failure's context — what succeeded around it — was three scrolls away. One time-ordered feed with the existing ❌ marker and target badge preserves distinguishability while restoring context. The header's failure count takes over the alerting role the separate section used to serve.

### Split EDSM by access path, nested one level inside Setup

Setup holds four independent concerns (journal path, EDDN, EDSM account, EDSM lookups). Flattening them into one expansion recreates today's problem inside a drawer, so each is its own nested collapsible carrying a state summary — expanding Setup alone answers "is everything configured?" without opening anything further.

Splitting EDSM into **account** (write, needs key) and **lookups** (read, keyless) removes the false implication, created by today's key-on-top ordering, that the API key gates lookups.

### Self-enabling nearest-scoopable action

With the lookups toggle now two drawers deep, today's advisory text ("Enable EDSM lookup to use this action") is a dead end. The disabled button instead becomes its own fix: it reads `Enable EDSM lookups to search`, and one activation persists the setting and runs the search.

The consent bar is low — EDSM reads are keyless and anonymous, unlike the write path — and the label states plainly what the press will do.

One rough edge, accepted: `lookup_nearest_scoopable` short-circuits to `"unavailable"` when the current system isn't known, which is exactly the state you are in if you enable lookups before the first arrival. The press then shows the unavailable state. That is the honest result and it self-corrects on the next jump; suppressing it would hide the fact that the press did anything.

## Risks / Trade-offs

- **Collapsed children might still take focus if implemented with CSS hiding** → render `null`, and verify on-device by D-pad traversal that a collapsed section is a single stop. This is the change's core claim; if it fails, the redesign delivers tidiness but not its main benefit.
- **The health strip loses independently-readable ED and journal status** → severity ordering is specified and enumerated as scenarios; the states are walked through on-device before merge. The author has flagged wanting to test this specifically.
- **`reason` is a payload change touching backend, types, and rehydration** → optional field with a frontend fallback, so a stale payload degrades to today's generic text rather than breaking.
- **`Content.tsx` is 799 lines and this touches most of it** → extract the collapsible, health strip, and section bodies as components in the same file first, then reorder. Keeps the diff reviewable and the reordering step mechanical.
- **Fixed-footprint next-hop block wastes vertical space when there is no route** → accepted deliberately; the author chose permanence over a block that appears and disappears, and layout stability is specified.
- **Auto-expanding Data flow on errors could surprise** → derived once on mount only, never mid-session.

## Migration Plan

No data migration. `reason` is additive and optional; an older frontend ignores it and a newer frontend tolerates its absence. Rollback is a straight revert — no persisted state is written by this change, which is a direct benefit of the reset-on-open decision.

## Open Questions

- Exact wording of the five health-strip states, to be settled during on-device testing.
- Whether the Setup header summary should report a problem state (e.g. missing uploader ID) or only completeness.
