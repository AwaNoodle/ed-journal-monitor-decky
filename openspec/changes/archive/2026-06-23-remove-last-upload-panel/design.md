## Context

The plugin panel has a "Last Upload" field that shows the most recent successful upload's event name and timestamp. The "Recent Activity" pane directly below it already shows each upload event, its outcome (✅/❌), and timestamp. The two displays are redundant.

## Goals / Non-Goals

**Goals:**
- Remove the "Last Upload" UI field from `Content.tsx`
- Remove the supporting state (`lastUpload`, `lastUploadEvent`) and update handlers
- Remove `last_upload_time` / `last_upload_event` from the backend status payload and TypeScript types
- Stop tracking those fields in `submitter.py`

**Non-Goals:**
- Changing the Recent Activity pane or its data model
- Modifying the `upload_success` websocket event (still used by the activity log)
- Any visual redesign beyond the removal

## Decisions

**Remove tracking from the backend entirely, not just the UI**

The `_last_upload_time` and `_last_upload_event` fields in `submitter.py` exist solely to populate the removed UI field. Leaving dead state in the backend invites confusion. Removing them keeps the `get_status()` payload lean and avoids a future maintainer wondering why they're there.

Alternative considered: keep the fields on the backend in case a future feature needs them. Rejected — YAGNI; they're trivial to re-add if needed.

## Risks / Trade-offs

[Minor state churn] The `status_update` event handler in `Content.tsx` currently reads these fields — removing them means the handler needs a small update. Low risk since the fields are only consumed in one place. → No mitigation needed.

[Type changes] Removing fields from `PluginStatus` / `StatusUpdate` is a non-breaking internal change — no external consumers. → No mitigation needed.
