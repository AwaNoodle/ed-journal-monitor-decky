## Why

Users have no visibility into what the plugin is actually doing. The UI shows aggregate counts (✅ 5 ❌ 2) and a last-upload timestamp, but provides no detail on what went wrong when uploads fail, what events have been processed, or any recent activity timeline. When something goes wrong, there's no way to diagnose it from the UI — the user must download a diagnostic bundle and dig through logs.

## What Changes

- Add a recent activity log to the backend that records each upload attempt (success or failure) with timestamp, event type, and error details
- Expose the activity log to the frontend via a callable and real-time events
- Add an error details panel to the UI showing the most recent errors with context (event type, error message, HTTP status, retry count)
- Add a "last successful upload" field with event name, not just a timestamp
- Show a recent activity feed in the UI (last N events processed) with status indicators

## Capabilities

### New Capabilities
- `activity-log`: Backend tracking of recent upload attempts and events processed, with timestamp, event type, outcome, and error details; exposed via callable and emitted to frontend
- `error-display`: Frontend panel showing recent errors with details (event type, error message, HTTP status if applicable), and a recent activity feed showing last N processed events with status

### Modified Capabilities
- `plugin-ui`: UI needs new sections for error display and activity feed; existing upload stats section enhanced with event-level detail on last upload

## Impact

- `src/modules/submitter.py` — must report per-attempt details to activity log
- `src/modules/activity_log.py` — new module for tracking recent activity
- `main.py` — wire up activity log, add callable for fetching recent activity
- `src/index.tsx` — listen for new backend events (activity updates)
- `src/Content.tsx` — new UI sections for error display and activity feed
- `openspec/specs/plugin-ui/` — requirements for new UI sections
