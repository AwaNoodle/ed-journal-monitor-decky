## Context

The plugin runs on a Steam Deck under Decky Loader. When issues occur (EDDN failures, path detection problems, silent event drops), there's no practical way to inspect what happened. Decky already provides per-plugin logging via `decky.logger` → `DECKY_PLUGIN_LOG`, but users don't know where that file lives and a raw log alone doesn't capture runtime state. The plugin uses stdlib-only Python (no pip packages) and communicates frontend↔backend via `callable()`/`decky.emit()`.

## Goals / Non-Goals

**Goals:**
- Allow users to package all relevant diagnostic data into a single zip retrievable via desktop mode
- Allow users to increase log verbosity to DEBUG for richer troubleshooting detail
- Default to INFO-level logging to keep log files lean
- Persist the detailed logging preference across plugin restarts

**Non-Goals:**
- Automatic upload of diagnostic data to any external service
- Automatic bundle creation on failure conditions
- Redaction/scrubbing of uploader ID or filesystem paths from the bundle
- Log rotation beyond what Decky already provides
- Custom log file or tee infrastructure (Decky's `decky.logger` is sufficient)

## Decisions

### 1. Use `decky.logger` directly — no custom logging infrastructure
Decky already writes `decky.logger` output to `DECKY_PLUGIN_LOG`. The detailed logging toggle simply adjusts the logger level between INFO and DEBUG. No wrapper, no tee, no new log file.

**Alternative considered**: Build a custom PluginLog wrapper that tees to a separate file. Rejected because Decky already provides the log file — adding a second one is redundant and requires touching every module.

### 2. New `src/modules/diagnostics.py` module
Single module responsible for snapshotting runtime state and creating the zip. Receives references to other components (watcher, submitter, settings) to gather state. Uses stdlib only (`zipfile`, `json`, `os`, `pathlib`).

**Alternative considered**: Scatter dump() methods across existing modules. Rejected because a single module keeps the responsibility centralized and avoids touching every existing module's interface.

### 3. Zip placed in `DECKY_PLUGIN_SETTINGS_DIR`
This directory is accessible via desktop mode file manager. The zip overwrites itself on each call — no accumulation.

**Alternative considered**: Write to `/tmp/` or a USB mount path. Rejected because SETTINGS_DIR is the standard Decky location for plugin data and doesn't require knowing the user's mount points.

### 4. Runtime state as JSON snapshot
Rather than including raw in-memory objects, serialize runtime state to a structured `runtime_state.json` with known fields. This is human-readable and versionable.

### 5. Log level applied on plugin startup
The `detailed_logging` setting is read during `_main()` and the logger level is set accordingly. This ensures the setting persists across Decky/plugin restarts.

## Risks / Trade-offs

- [Debug log growth] → DEBUG level produces more output. Mitigated by: user must explicitly opt in, and Decky's own log rotation handles the file.
- [Bundle contains filesystem paths] → `runtime_state.json` includes full journal file paths which reveal Steam library location. Accepted: not sensitive on a personal device, and useful for diagnosing path issues.
- [Zip contains uploader_id] → `settings.json` in the bundle includes the uploader ID. Accepted: it's an EDDN concept, not PII, and may be directly relevant to bug reports.
- [decky.logger is a stdlib Logger] → We rely on `setLevel()` working on it. Confirmed by the `.pyi` type definition (`logger: logging.Logger`).
