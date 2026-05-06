## 1. Backend — ED Running State

- [x] 1.1 Add `ed_running` boolean instance variable to Plugin class in `main.py`, defaulting to `false`
- [x] 1.2 Implement `set_ed_running(enabled: bool)` callable that updates `ed_running`, emits `ed_state_change` event only if state actually changed, and returns `{"success": True}`
- [x] 1.3 Add `ed_running` field to `get_status()` response
- [x] 1.4 Add tests for `set_ed_running` callable (state update, event emission, no-op on same state)
- [x] 1.5 Add tests for `get_status` returning `ed_running` field

## 2. Frontend — Game Lifecycle Integration

- [x] 2.1 Add `setEdRunning` callable import to `src/index.tsx`
- [x] 2.2 Call `setEdRunning(true)` in `handleAppStart` when ED starts (`bRunning: true`)
- [x] 2.3 Call `setEdRunning(false)` in `handleAppStart` when ED stops (`bRunning: false`)
- [x] 2.4 Log failures from `setEdRunning` calls (don't block watcher start/stop on failure)

## 3. Frontend — UI Split Status Display

- [x] 3.1 Add `edRunning` state to `Content.tsx`, initialized from `get_status().ed_running`
- [x] 3.2 Add `ed_state_change` event listener that updates `edRunning` state
- [x] 3.3 Remove the single `getStatusText()` function
- [x] 3.4 Add `getEdStatusText()` returning "⚪ Not Running" or "🟢 Running"
- [x] 3.5 Add `getJournalStatusText()` returning "🔍 Not Found" / "📂 Found" / "⚠️ Found, Not Watching" / "🟢 Watching & Uploading" with contextual logic based on `edRunning`
- [x] 3.6 Replace the single Status Field with two Field components: "ED Status" and "Journal Status"
- [x] 3.7 Clean up event listener registration in the useEffect return

## 4. TypeScript Types

- [x] 4.1 Add `ed_running: boolean` to `GetStatusResult` type definition
- [x] 4.2 Add `EdStateChangeEvent` type for the `ed_state_change` event payload

## 5. Verification

- [x] 5.1 Run all Python tests (`PYTHONPATH=. python -m pytest tests/ -v`)
- [x] 5.2 Run TypeScript type check
- [x] 5.3 Build frontend and verify no errors
