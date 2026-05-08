# ED Journal Monitor Decky Plugin — Plan

## Status: Implementation Complete

## Recent Change: fix-plugin-import-path-and-game-detection
Fixed plugin failing to start on-device (ModuleNotFoundError) and improved ED game detection.

### What Changed
- `main.py` — Added `sys.path` manipulation so `from src.modules...` resolves when Decky deploys to `bin/src/modules/`; fixed broken `create_diagnostics` method; added `Optional` type compat
- `package.json` — Fixed package script: `cp -r src/modules out/.../bin/` → `cp -r src/modules out/.../bin/src/` to match import paths
- `src/index.tsx` — Removed custom `declare const SteamClient` that shadowed `@decky/ui` global; added diagnostic logging for all `AppLifetimeNotification` events; added registration success/failure logging
- `src/modules/path_finder.py` — Added `_check_ed_process()` scanning `/proc/*/comm` for ED processes; `is_ed_likely_running()` now checks process list first, falls back to journal mtime; fixed process name detection (kernel truncates `/proc/PID/comm` to 15 chars, so `EliteDangerous64` → `EliteDangerous6`)
- `tests/test_path_finder_process.py` — 8 new tests for process-based detection

### Root Cause (Primary)
Plugin never started on-device. The `package` script deployed modules to `bin/modules/` but `main.py` imported `from src.modules...`. Every startup failed with `ModuleNotFoundError: No module named 'src'`.

### Root Cause (Secondary)
`/proc/PID/comm` truncates to 15 chars. The detection code looked for `EliteDangerous64` (16 chars) which never matched the actual comm value `EliteDangerous6`.

### Test Results
125 tests, all passing (was 117).

### On-Device Verification
Plugin now starts successfully, detects ED via /proc scan, finds journal path via VDF scan. SSL cert issue discovered (separate problem).

## Previous Change: already-running-game-detection
Fixed bug where ED was not detected if already running when the plugin loaded.

### What Changed
- `src/modules/path_finder.py` — Added `is_ed_likely_running()` method that checks for journal files modified within the last 5 minutes
- `main.py` — Added `check_ed_running` callable that probes backend for already-running ED
- `src/index.tsx` — Added startup probe: after registering lifecycle listeners, calls `check_ed_running()` and triggers watcher start if ED is already running
- `tests/test_ed_already_running.py` — 13 new tests covering `is_ed_likely_running()` and `check_ed_running`

### Root Cause
`RegisterForAppLifetimeNotifications` only fires on state changes. If ED was already running when the plugin loaded (Decky restart, plugin update, Steam Deck reboot), no notification was fired and ED went undetected.

### Test Results
117 tests, all passing (was 104).

## Previous Change: upload-status-and-errors
Added activity log, real-time error display, and enhanced upload status to the plugin.

### What Changed
- New `src/modules/activity_log.py` — in-memory circular buffer (deque maxlen=50) tracking upload attempts
- `src/modules/submitter.py` — now accepts optional `ActivityLog`, records success/failure entries, includes `event_name` in `upload_success` event and `last_upload_event` in `get_stats()`
- `main.py` — wires `ActivityLog`, adds `get_recent_activity` callable
- `src/Content.tsx` — new "Recent Errors" and "Recent Activity" panel sections, enhanced "Last Upload" with event name
- `src/types.d.ts` — added `ActivityEntry`, `UploadSuccessEvent.event_name`, `StatusUpdateEvent.last_upload_event`

### Test Results
96 tests, all passing (was 67).

## What Was Built
A Decky plugin that monitors Elite Dangerous journal files and submits events to EDDN. All 50 tasks from the OpenSpec change are complete.

## Components Implemented
1. **Project scaffold** — Decky plugin template customized, builds clean
2. **Journal path detection** — VDF parser + compatdata scanner + settings cache + manual fallback
3. **Journal parser** — JSON line parsing, reportable event filtering, LoadGame/Fileheader handling
4. **Journal watcher** — Polling loop, position tracking, incremental reads, catch-up logic
5. **EDDN submission** — Message construction, field stripping, horizons/odyssey augmentation, HTTP POST with retry
6. **Frontend game lifecycle** — SteamClient AppLifetimeNotifications for ED 359320, suspend/resume handling
7. **Frontend UI panel** — Status, upload stats, enable/disable toggle, manual path input, uploader ID config
8. **Integration tests** — End-to-end pipeline, catch-up, SD card, no-root verification

## Test Results
67 tests, all passing.

## OpenSpec Change
- Change: `ed-journal-monitor-decky` at `openspec/changes/ed-journal-monitor-decky/`
- All artifacts complete (proposal, design, specs, tasks)

## Next Steps
- Test on actual Steam Deck hardware
- Publish to Decky plugin store
- Add commodity/3 and outfitting/2 EDDN schemas as future feature

---

## Fix Plan: Verification WARNINGs & SUGGESTIONs

### WARNING Fixes

#### W1: Status text matches spec wording
- **File**: `src/Content.tsx:124`
- **Change**: `"🟢 Watching"` → `"🟢 Watching — uploading journal events"`
- **Test**: No test needed (UI text only)

#### W2: Test for enabled/disabled auto-start suppression
- **Note**: This test depends on fixing CRITICAL issue #1 (frontend `handleAppStart` must check `enabled`). Tracking here as a test to add once that fix lands.
- **File**: New test or extend `tests/test_integration.py`
- **Change**: Add test that verifies when `enabled=False`, the watcher does not start even when ED launch is triggered
- **Approach**: Since the enabled check is in the TypeScript frontend, this is best verified manually on-device. However, we can add a backend test verifying `set_enabled(False)` prevents `start_watcher` from succeeding (it already calls `stop_watcher` if running, but we should also gate `start_watcher` on `enabled`).
- **Test**: Add test in `tests/test_integration.py`:
  ```python
  async def test_start_watcher_blocked_when_disabled(self):
      # set enabled=False
      # call start_watcher
      # assert watcher is not running
  ```

### SUGGESTION Fixes

#### S1: Deduplicate shared constants
- **Files**: `src/modules/parser.py`, `src/modules/path_finder.py`
- **Change**: Create `src/modules/constants.py` with `REPORTABLE_EVENTS` and `EDDN_DISALLOWED_FIELDS`, then import from there in both `parser.py` and `path_finder.py`
- **Also update**: `src/modules/validator.py` already imports from `parser.py` — update that import too
- **Test**: Run existing 67 tests to confirm no breakage

#### S2: Replace inline `__import__("os")` with top-level import
- **File**: `src/modules/path_finder.py:86-88`
- **Change**: Add `import os` at top of file (after existing imports), replace `_get_home_dir` body with:
  ```python
  def _get_home_dir(self) -> str | None:
      home = os.environ.get("DECKY_USER_HOME")
      if not home:
          home = os.path.expanduser("~")
      return home
  ```
- **Test**: Run existing 67 tests to confirm no breakage

#### S3: Add CI configuration for lint/typecheck
- **Files**: New `.github/workflows/ci.yml`
- **Change**: Add GitHub Action that runs:
  1. `npm run lint:ts` (tsc + eslint)
  2. `npm run lint:py` (ruff + pytest)
- **Note**: Low priority — this is infrastructure, not a code bug

### Execution Order
1. ~~S1 (constants dedup) — clean refactor, makes S2 easier~~ ✅
2. ~~S2 (os import) — trivial fix~~ ✅
3. ~~W1 (status text) — trivial fix~~ ✅
4. ~~W2 (enabled gate test) — requires backend `start_watcher` to check `enabled` setting~~ ✅
5. S3 (CI) — optional, separate concern

### Additional Fixes (from second verification)

#### CRITICAL Fix: SD card cache preservation
- **File**: `src/modules/path_finder.py:48-50`
- **Change**: When `_validate_path` fails for a cached path, return `None` but do NOT clear `journal_path` from settings. This preserves the path for SD card reinsertion recovery.
- **Old**: `await self.settings.set("journal_path", None)` on validation failure
- **New**: `return None` with log message "Cached journal path temporarily unavailable"
- **Test**: Added `test_cached_path_preserved_when_unavailable` in `tests/test_sdcard_and_root.py`

#### WARNING Fix: Frontend enabled check on ED launch
- **File**: `src/index.tsx:28-32`
- **Change**: `handleAppStart` now calls `getStatus()` first and checks `status.enabled` before proceeding to `findJournalPath()` + `startWatcher()`
- Also added: `startWatcher()` return value checked and logged on failure
- **Impact**: When monitor is disabled, no unnecessary backend calls made on ED launch events
