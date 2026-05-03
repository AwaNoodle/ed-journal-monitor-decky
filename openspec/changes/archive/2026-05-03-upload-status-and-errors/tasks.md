## 1. Backend: ActivityLog Module

- [x] 1.1 Create `src/modules/activity_log.py` with `ActivityLog` class using `collections.deque(maxlen=50)`, entry structure (timestamp, event_type, outcome, error_type, error_message, http_status)
- [x] 1.2 Add `record_success(event_type)` and `record_failure(event_type, error_type, error_message, http_status=None)` methods that append entries and emit `activity_update` via `decky.emit`
- [x] 1.3 Add `get_recent(limit=50, outcome=None)` method returning entries newest-first, with optional outcome filter
- [x] 1.4 Write tests for ActivityLog: entry creation, buffer overflow, filtering, newest-first ordering

## 2. Backend: Integrate Submitter with ActivityLog

- [x] 2.1 Modify `EDDNSubmitter` to accept an `ActivityLog` instance in `__init__`
- [x] 2.2 In `submit()` success path, call `activity_log.record_success(event_type)`
- [x] 2.3 In `submit()` failure path, call `activity_log.record_failure(event_type, error_type, error_message, http_status)` with appropriate error classification (http_error, network_error)
- [x] 2.4 Enhance `upload_success` event payload to include `event_name` field alongside existing fields
- [x] 2.5 Enhance `get_stats()` to include `last_upload_event` field
- [x] 2.6 Update existing submitter tests for new ActivityLog integration; add test verifying activity entries are recorded on success and failure

## 3. Backend: Wire ActivityLog into Plugin

- [x] 3.1 In `main.py`, instantiate `ActivityLog` and pass it to `EDDNSubmitter`
- [x] 3.2 Add `get_recent_activity` callable to `main.py` that delegates to `activity_log.get_recent()`
- [x] 3.3 Verify integration with manual test or existing test harness

## 4. Frontend: Activity & Error Display

- [x] 4.1 Add state variables for recent errors (last 5) and recent activity (last 10), and `lastUploadEvent` string
- [x] 4.2 Add `get_recent_activity` callable import and fetch on mount
- [x] 4.3 Listen for `activity_update` events to update error and activity lists in real-time
- [x] 4.4 Update `upload_success` listener to capture `event_name` for enhanced last-upload display
- [x] 4.5 Add "Recent Errors" PanelSection showing last 5 failures with event type, timestamp, error type, and error message; show "No errors" when empty
- [x] 4.6 Add "Recent Activity" PanelSection showing last 10 entries as compact lines (✅/❌ icon + event type + timestamp); show "No activity yet" when empty
- [x] 4.7 Update "Last Upload" Field to show event name alongside timestamp (e.g. "FSDJump — 14:32:05") or "No uploads yet"

## 5. Tests & Verification

- [x] 5.1 Run full test suite (`PYTHONPATH=. python -m pytest tests/ -v`) and ensure all pass
- [x] 5.2 Add integration test: verify `get_recent_activity` callable returns expected entries after simulated uploads
- [x] 5.3 Typecheck frontend (`npx tsc --noEmit`) and verify no errors
