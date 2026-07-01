## Why

The Recent Activity and Recent Errors lists are fed only by EDDN, so events forwarded to EDSM never appear and there is no way to see which target an event was sent to. Because EDDN (a narrow ~21-event allow-list) and EDSM (a broad deny-list of everything not on its ~141-entry discard list) carry different, only-partially-overlapping streams, "what was sent where" genuinely differs per event — and today the panel can't show it. A related confusion: EDSM's upload counter increments per *batch* while EDDN's increments per *event*, so the two "Uploads" numbers aren't comparable.

## What Changes

- Add a `target` value (`eddn` / `edsm`) to every activity log entry, typed as a small enum/`Literal` (`UploadTarget`) so a future target (e.g. Inara) is a one-line addition.
- The EDSM forwarder records **per-event** activity entries when a batch reaches a **terminal** response (success or fatal); transient/retried batches record nothing until they settle. EDSM fatal errors (e.g. a bad-key `203`) now also surface in Recent Errors.
- Align EDSM upload counting with EDDN: count **per event** (not per batch), incremented only on terminal outcomes so retried events are never double-counted, making the EDDN and EDSM "Uploads" numbers mean the same unit. (Refines the per-target stats introduced by the pending `edsm-target` change.)
- The frontend renders a compact **target badge** on each Recent Activity and Recent Errors row (e.g. `✅ FSDJump · EDSM · 19:31`).
- Chosen shape: **per-event rows tagged by target** (not one merged row per event). An event sent to both targets shows as two rows — one EDDN (immediate), one EDSM (when its batch flushes). Accepted characteristic: an EDSM batch of N events adds N rows at once; a target filter is a deferred follow-up, not part of this change.

## Capabilities

### New Capabilities
<!-- none — the activity log capability already exists -->

### Modified Capabilities
- `activity-log`: activity entries gain a typed `target` field; the log records entries for **any** submission target (EDDN per-event immediately, EDSM per-event on terminal batch flush), not EDDN only.
- `error-display`: Recent Activity and Recent Errors rows show the target for each entry, and EDSM failures appear in Recent Errors.

## Impact

- **Backend:** `src/modules/constants.py` (`TARGET_EDDN`/`TARGET_EDSM`/`UploadTarget = Literal[...]`); `src/modules/activity_log.py` (`record_success`/`record_failure` gain a `target` param, default `eddn`; entry carries `target`); `src/modules/forwarders/edsm.py` (holds an `activity_log` reference, records per-event on terminal responses, counts per event); `main.py` (passes `activity_log` into `EdsmForwarder`). EDDN submitter unchanged (defaults to `eddn`).
- **Frontend:** `src/types.d.ts` (`type UploadTarget`; `ActivityEntry.target`); `src/Content.tsx` (target badge on activity + error rows, `target` in the React key).
- **Depends on** the (implemented, not-yet-archived) `edsm-target` change: the `EdsmForwarder`, per-target stats, and `StreamConsumer` registry it introduced.
- **Docs:** `AGENTS.md` (activity entries are target-tagged; EDSM records per-event), `CHANGELOG.md` `[Unreleased]`.
