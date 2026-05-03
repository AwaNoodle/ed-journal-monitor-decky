# ED Journal Monitor Decky Plugin — Plan

## Status: Implementation Complete

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
