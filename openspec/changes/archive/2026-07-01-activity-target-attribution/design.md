## Context

The activity log (`src/modules/activity_log.py`) is a 50-entry in-memory circular buffer written **only** by the EDDN submitter, one entry per event at submit time, and mirrored to the frontend via the `activity_update` emit and the `get_recent_activity` callable. Entries are flat dicts (`timestamp`, `event_type`, `outcome`, `error_type`, `error_message`, `http_status`) with no notion of a destination.

The `edsm-target` change (implemented, not yet archived) added a second destination: `EdsmForwarder`, a `StreamConsumer` that buffers events and POSTs them to EDSM in batches, classifying each batch response by `msgnum` (1xx OK, 2xx fatal/no-retry, 5xx transient/retry). It currently writes nothing to the activity log and counts success/fail **per batch**, so its "Uploads" number is not comparable to EDDN's per-event count. EDDN and EDSM also apply different filters (EDDN a ~21-event allow-list; EDSM a broad deny-list), so the two carry different, only-partially-overlapping streams.

## Goals / Non-Goals

**Goals:**
- Show, per event, which target it was sent to, in both Recent Activity and Recent Errors.
- Record EDSM events in the same activity log as EDDN, per event, without disturbing the EDDN path.
- Make the EDDN and EDSM upload counts mean the same unit (events).
- Type the target so a third target (Inara) is a one-line addition, not a reshape.

**Non-Goals:**
- Merging both targets for one event into a single combined row (rejected: needs cross-path correlation of the immediate EDDN path with the delayed EDSM batch).
- A target filter / per-target sub-lists in the UI (deferred follow-up).
- Persisting activity across restarts, or changing the 50-entry buffer size or the last-10 / last-5 display caps.

## Decisions

### Decision: Per-event rows tagged by target (not one merged row per event)
Each target records its own per-event entry; an event sent to both targets appears as two rows (EDDN immediately, EDSM when its batch flushes). *Why over a merged row:* a combined row requires correlating the same journal event across two paths that fire seconds apart, plus in-place row updates and a correlation key — significant complexity for a cosmetic gain, especially since the two streams only partially overlap so most rows are single-target anyway. Tagged rows are the current mechanism plus a field.

### Decision: `target` as a typed value (`UploadTarget`)
Add `TARGET_EDDN = "eddn"`, `TARGET_EDSM = "edsm"`, and `UploadTarget = Literal["eddn", "edsm"]` in `constants.py` (mirrors the existing `AuxiliarySchemaType = Literal[...]`); the frontend mirrors it as `type UploadTarget = "eddn" | "edsm"`. The string values match the per-target stats keys already used by `_build_target_stats`/`EdsmForwarder.name`. *Why:* centralizes the target vocabulary and makes Inara additive (one constant + one union member). `record_success`/`record_failure` take `target` defaulting to `TARGET_EDDN` so existing EDDN callers are untouched.

### Decision: EDSM records per event, only on terminal responses
`EdsmForwarder` holds an `activity_log` reference (as the EDDN submitter does). In `_handle_response`, on a **terminal** response it loops the batch: `ok` → `record_success(event_type, target=edsm)` per event; `fatal` → `record_failure(event_type, "edsm", "[<msgnum>] <msg>", target=edsm)` per event. On a **transient** response the events are retained for retry and nothing is recorded. Counting moves to per event in the same place (`success_count += len(batch)` / `fail_count += len(batch)`), only on terminal outcomes. *Why:* recording/counting only terminal outcomes keeps activity, success, and fail counts consistent and prevents double-counting a retried event; it also naturally makes EDSM's counter per-event like EDDN's.

### Decision: Fold EDSM `msgnum` into `error_message` (sub-decision A)
EDSM failures reuse the existing entry fields — `error_type = "edsm"`, `error_message = "[<msgnum>] <msg>"`, `http_status = null` — rather than adding an EDSM-specific field. *Why:* keeps the entry shape uniform across targets so the frontend renders one row type; the `msgnum` is still visible, embedded in the message.

## Risks / Trade-offs

- **EDSM batch floods the last-10 view** → A flush of N events adds N rows at once, briefly dominating the feed. Accepted as accurate; a target filter is the deferred mitigation. The 50-entry buffer and last-10 cap bound it.
- **Entry shape change ripples to tests** → Existing `test_activity_log.py` (and any test asserting exact entry dicts) must add `target`. Mitigation: `target` defaults to `eddn`, so EDDN production callers and most assertions need only the new field added.
- **Spec dependency on unarchived `edsm-target`** → The EDSM per-event counting refines behavior whose spec (`edsm-submission`) is not yet in the baseline. Mitigation: capture the counting change here in design + tasks; it will reconcile cleanly when `edsm-target` is archived. No baseline delta is created for a non-baselined capability.
- **EDSM error volume in Recent Errors** → A wrong API key makes every batch fatal (203), which now writes a failure row per event. Mitigation: this is desired visibility; the existing EDSM status block still shows the single last message, and the 5-error cap limits the panel.

## Migration Plan

Additive and in-memory only — no persistence or data migration. Ships in the plugin package; on load the activity log starts empty as today. Rollback is reverting the change (no stored state to unwind).

## Open Questions

None.
