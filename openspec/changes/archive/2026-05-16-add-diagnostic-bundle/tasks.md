## 1. Backend: Diagnostics Module

- [x] 1.1 Create `src/modules/diagnostics.py` with `create_diagnostics()` method that gathers runtime state, zips log/settings/metadata, and returns `{ success, path, size }`
- [x] 1.2 Implement runtime state snapshot: serialize watcher status, journal path/source, submitter stats, file positions, known files, poll interval, Python version, Decky version to `runtime_state.json`
- [x] 1.3 Implement zip packaging: write `plugin.log` (from `DECKY_PLUGIN_LOG`), `settings.json`, `runtime_state.json`, `plugin.json` into `DECKY_PLUGIN_SETTINGS_DIR/ed-jm-diagnostics.zip`, overwriting any existing bundle

## 2. Backend: Detailed Logging

- [x] 2.1 Add `set_detailed_logging(enabled)` method to `main.py` Plugin class: set `decky.logger` level to DEBUG or INFO, persist to settings
- [x] 2.2 In `_main()`, read `detailed_logging` setting and apply logger level on startup

## 3. Backend: Wire Callables

- [x] 3.1 Add `create_diagnostics` and `set_detailed_logging` callable methods to `Plugin` class in `main.py`
- [x] 3.2 Pass component references (watcher, submitter, settings) to diagnostics module

## 4. Frontend: Diagnostics UI

- [x] 4.1 Add Diagnostics `PanelSection` to `Content.tsx` with "Detailed Logging" toggle and "Create Diagnostic Bundle" button
- [x] 4.2 Wire toggle to `set_detailed_logging` callable, persist state locally
- [x] 4.3 Wire button to `create_diagnostics` callable, display returned zip path in the panel
- [x] 4.4 Load `detailed_logging` state from `get_status` on mount

## 5. Tests

- [x] 5.1 Test `create_diagnostics()` produces zip with expected contents (plugin.log/settings.json/runtime_state.json/plugin.json)
- [x] 5.2 Test `create_diagnostics()` handles missing log file gracefully
- [x] 5.3 Test `create_diagnostics()` overwrites previous bundle
- [x] 5.4 Test `set_detailed_logging(true)` sets logger to DEBUG and persists
- [x] 5.5 Test `set_detailed_logging(false)` sets logger to INFO and persists
- [x] 5.6 Test default logging level is INFO on first run

## 6. Cleanup

- [x] 6.1 Run ruff lint and mypy typecheck, fix any issues
- [x] 6.2 Run full test suite (`PYTHONPATH=. python -m pytest tests/ -v`), ensure all tests pass
- [x] 6.3 Update AGENTS.md and README.md with diagnostics feature
