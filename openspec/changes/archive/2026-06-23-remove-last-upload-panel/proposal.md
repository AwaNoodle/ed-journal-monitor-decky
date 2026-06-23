## Why

The "Last Upload" field duplicates information already visible in the "Recent Activity" pane, which shows each upload's event type, outcome, and timestamp. Removing it reduces panel clutter on the narrow Steam Deck display without losing any information.

## What Changes

- Remove the "Last Upload" `PanelSectionRow` (both the populated and "No uploads yet" states) from the status panel in `Content.tsx`
- Remove the `lastUpload` and `lastUploadEvent` state variables and their update logic from `Content.tsx`
- Remove `last_upload_time` and `last_upload_event` from the backend status payload and the `PluginStatus` / `StatusUpdate` TypeScript types
- Stop tracking `_last_upload_time` and `_last_upload_event` in `submitter.py`

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `plugin-ui`: The "Last Upload" display requirements are removed; upload recency is now covered exclusively by Recent Activity

## Impact

- `src/Content.tsx`: remove state vars, update handlers, and JSX rows for Last Upload
- `src/types.d.ts`: remove `last_upload_time` and `last_upload_event` from `PluginStatus` and `StatusUpdate`
- `src/modules/submitter.py`: remove tracking fields and their inclusion in the status dict
