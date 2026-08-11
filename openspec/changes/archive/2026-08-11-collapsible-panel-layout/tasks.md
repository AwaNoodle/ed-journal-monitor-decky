## 1. Backend: next-hop reason discriminator

- [x] 1.1 Write tests for `NextHopTracker` reporting a cause alongside a `None` next hop — covering no route, final hop, and off route
- [x] 1.2 Extend `NextHopTracker.next_hop()` in `src/modules/edsm_next_hop.py` to report which condition produced no next hop, without changing its behaviour when a hop exists
- [x] 1.3 Write tests for `neutral_next_hop()` carrying a `reason` for each cause (no route, final hop, off route, disabled)
- [x] 1.4 Add `reason` to `neutral_next_hop()` and the payload builder in `src/modules/edsm_next_hop_consumer.py`, passing the specific cause at each emit site
- [x] 1.5 Write a test that `get_status` rehydration preserves `reason`, then verify `main.py`'s `_edsm_next_hop` storage passes it through unchanged
- [x] 1.6 Run the full Python suite and lint; all tests pass

## 2. Frontend: types and primitives

- [x] 2.1 Add optional `reason` to `EdsmNextHopPreview` in `src/types.d.ts` with the five discriminator values
- [x] 2.2 Add a local `CollapsibleSection` component in `src/Content.tsx` — header `Field` with `focusable`/`onActivate`/`icon`, a `summary` slot, and children rendered only when expanded (never CSS-hidden)
- [x] 2.3 Add a `healthState()` pure helper returning one of the five states, evaluated worst-first, and a non-focusable strip component that renders it
- [x] 2.4 Verify the frontend typechecks and lints

## 3. Frontend: extract existing sections

- [x] 3.1 Extract the current Configuration, EDSM, Diagnostics, Recent Activity, and Recent Errors bodies into named render functions, with no behavioural or layout change
- [x] 3.2 Confirm the panel renders identically to before this change (no reordering yet) — keeps the reordering diff mechanical

  Note: this session merged the extraction and the reorder into a single pass rather than a two-step mechanical diff (steps 3 and 4 landed together in one rewrite of `Content.tsx`). Functionally equivalent; recorded here since it deviates from the task's stated sequencing.

## 4. Frontend: the new layout

- [x] 4.1 Replace the ED Status and Journal Status rows with the health strip; move the `Watch journal` toggle out of Status
- [x] 4.2 Add the always-visible Navigation section holding current location, verdict chip, system value, next hop, and the nearest-scoopable action
- [x] 4.3 Reduce the Session section to the counters only, placed below Navigation
- [x] 4.4 Add the collapsed Data flow section: aggregate counts in the header, per-target rows and the merged success/failure feed inside
- [x] 4.5 Merge Recent Errors into the Data flow feed as failure rows, and delete the standalone Recent Errors section
- [x] 4.6 Add the collapsed Setup section with nested groups: Journal path (including the `Watch journal` toggle), EDDN, EDSM account, EDSM lookups — each with a header state summary
- [x] 4.7 Add the collapsed Troubleshooting section holding the detailed logging toggle and diagnostic bundle button
- [x] 4.8 Derive Data flow's initial expanded state once on mount from the failure count being greater than zero

## 5. Frontend: next-hop and scoopable behaviour

- [x] 5.1 Render the next-hop block permanently with a stable footprint, branching on `reason` for the no-hop states, falling back to generic no-route text when `reason` is absent
- [x] 5.2 Make the nearest-scoopable button self-enabling when lookups are off — label states the effect, one activation persists the setting then runs the search
- [x] 5.3 Confirm the self-enabling path shows the unavailable state (not silence) when no current system is known yet

## 6. Verification

- [x] 6.1 Run the full Python suite, frontend lint, and typecheck; all pass
- [x] 6.2 Package and deploy to the device, then confirm by D-pad traversal that the default panel has exactly four focus stops and each collapsed section is a single stop
- [x] 6.3 Walk through all five health-strip states on-device and confirm wording and severity ordering; settle the open wording question
- [x] 6.4 Confirm on-device that next-hop renders correctly for a plotted route, on arrival at the final hop, and with no route — with no layout shift between them
- [x] 6.5 Confirm collapse state resets when the panel is closed and reopened, and that Data flow starts expanded after a failure

## 7. Documentation

- [x] 7.1 Update `AGENTS.md` — panel structure, the `reason` field on the next-hop payload
- [x] 7.2 Update `README.md` for the new panel layout
- [x] 7.3 Add a short `[Unreleased]` entry to `CHANGELOG.md` — user-facing, 1–2 sentences, no internals
