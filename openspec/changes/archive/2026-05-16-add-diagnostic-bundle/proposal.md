## Why

The plugin runs on a Steam Deck — a closed environment where diagnosing issues is difficult. When something goes wrong (EDDN submissions fail, journal path isn't found, events are silently dropped), there's no practical way for a user or developer to inspect what happened. Decky writes per-plugin logs to `DECKY_PLUGIN_LOG`, but users don't know where that file is, and a raw log alone doesn't capture runtime state needed for effective troubleshooting.

## What Changes

- Add a "Create Diagnostic Bundle" action that packages plugin log, settings, runtime state snapshot, and plugin metadata into a zip file placed in `DECKY_PLUGIN_SETTINGS_DIR`
- Add a "Detailed Logging" toggle that sets `decky.logger` level to DEBUG (default is INFO), so the log captures submission details, validation failures, and poll-cycle specifics needed for troubleshooting
- Add a Diagnostics section to the plugin UI panel with the toggle and bundle button, and display the zip path after creation
- Add a backend `diagnostics` module to handle runtime state snapshot and zip creation
- Add callable methods: `create_diagnostics()` and `set_detailed_logging(enabled)`

## Capabilities

### New Capabilities
- `diagnostic-bundle`: Packaging of log files, settings, and runtime state into a retrievable zip for offline troubleshooting
- `detailed-logging`: User-controllable toggle to increase log verbosity from INFO to DEBUG for richer diagnostic capture

### Modified Capabilities
- `plugin-ui`: Add Diagnostics section with detailed logging toggle and bundle creation button

## Impact

- New backend module: `src/modules/diagnostics.py`
- Modified frontend: `src/Content.tsx` (new Diagnostics panel section)
- Modified backend: `main.py` (new callables, pass logger reference to diagnostics module)
- Uses stdlib only: `zipfile`, `json`, `os`, `pathlib` — no new dependencies
- Zip file written to `DECKY_PLUGIN_SETTINGS_DIR` — accessible via desktop mode file manager
