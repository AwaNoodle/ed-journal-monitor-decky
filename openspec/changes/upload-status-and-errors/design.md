## Context

The plugin currently tracks aggregate upload stats (success/fail counts, last upload timestamp) and emits them via `status_update` events. The UI displays these as "✅ 5 ❌ 2" and a timestamp. There is no visibility into:
- What specific events were processed and when
- Why uploads failed (HTTP status, error message, which event)
- Any recent activity timeline

The submitter already emits `upload_success` and `upload_failed` events with event type and totals, but no error details. The diagnostics module can create a zip bundle, but that requires digging through logs offline.

## Goals / Non-Goals

**Goals:**
- Track last N upload attempts (success + failure) with full context: timestamp, event type, outcome, error details
- Expose this log to the frontend via callable and real-time event emission
- Show recent errors with details in the UI (event name, error type, HTTP status, message)
- Show a recent activity feed (last N events processed, with status indicators)
- Enhance the "last upload" display to include the event name

**Non-Goals:**
- Persistent activity log across plugin restarts (in-memory only, reset on restart)
- Searching/filtering the activity log
- Retrying failed uploads from the UI
- Log file analysis or log rotation

## Decisions

### 1. In-memory circular buffer for activity log
**Decision**: Store last 50 activity entries in a `collections.deque(maxlen=50)` in a new `ActivityLog` module.
**Rationale**: Simple, bounded memory, no disk I/O, sufficient for "recent activity" display. No persistence needed — the log is for live monitoring, not auditing. 50 entries covers ~50 upload attempts which is plenty for a play session.
**Alternative**: SQLite or file-based log — overkill for a Decky plugin, adds I/O overhead and cleanup complexity.

### 2. ActivityLog as a separate module (not part of Submitter)
**Decision**: Create `src/modules/activity_log.py` as an independent module. The Submitter records entries into it.
**Rationale**: Separation of concerns — Submitter handles HTTP, ActivityLog handles recording. ActivityLog can also record events from the watcher/parser in the future.
**Alternative**: Embed in Submitter — couples tracking to submission, harder to extend.

### 3. Activity entry structure
**Decision**: Each entry is a dict with: `timestamp` (ISO 8601), `event_type` (e.g. "FSDJump"), `outcome` ("success" | "failure"), `error_type` (e.g. "http_error", "validation_error", "network_error", null), `error_message` (string or null), `http_status` (int or null).
**Rationale**: Covers all current failure modes in the submitter (HTTP errors, validation errors, network errors) while staying flat and simple.

### 4. Frontend fetches activity on demand + receives real-time updates
**Decision**: Backend provides `get_recent_activity()` callable returning last N entries. Backend also emits `activity_update` event on each new entry so the UI can update live.
**Rationale**: Callable is needed for initial load. Real-time event avoids polling. Same pattern as existing `status_update`.

### 5. UI sections: "Recent Errors" and "Recent Activity"
**Decision**: Add two new PanelSections — "Recent Errors" showing the last 5 failed entries with details, and "Recent Activity" showing the last 10 entries (all types) as a compact feed.
**Rationale**: Errors deserve their own section with more detail. Activity feed gives a quick "what's happening" view. Both are collapsible Decky panel sections.
**Alternative**: Single combined list — harder to quickly spot errors among successes.

## Risks / Trade-offs

- [Lost history on restart] → Acceptable: this is live monitoring, not an audit trail. The diagnostic bundle captures what matters.
- [Memory usage from 50-entry deque] → Negligible: each entry is ~200 bytes, total ~10KB.
- [UI clutter with more sections] → Mitigate: keep sections collapsible, show compact single-line entries for activity, expandable detail for errors.
