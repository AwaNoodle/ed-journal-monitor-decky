from __future__ import annotations

"""
Diagnostic bundle creation.
Packages plugin log, settings, runtime state, and metadata into a zip file.
"""

import json
import os
import platform
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modules.settings import PluginSettings
    from src.modules.submitter import EDDNSubmitter
    from src.modules.watcher import JournalWatcher


def create_diagnostics(
    settings: PluginSettings,
    watcher: JournalWatcher | None,
    submitter: EDDNSubmitter | None,
) -> dict:
    """
    Create a diagnostic bundle zip file.

    Gathers runtime state, zips log/settings/metadata, and returns
    { success, path, size }.
    """
    settings_dir = os.environ.get("DECKY_PLUGIN_SETTINGS_DIR", "")
    if not settings_dir:
        return {"success": False, "error": "DECKY_PLUGIN_SETTINGS_DIR not set"}

    zip_path = Path(settings_dir) / "ed-jm-diagnostics.zip"

    # Gather runtime state snapshot
    runtime_state = _gather_runtime_state(settings, watcher, submitter)

    try:
        # Overwrite any existing bundle
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write runtime_state.json
            zf.writestr("runtime_state.json", json.dumps(runtime_state, indent=2))

            # Write settings.json if it exists
            settings_file = Path(settings_dir) / "settings.json"
            if settings_file.exists():
                zf.write(settings_file, "settings.json")

            # Write plugin.json if it exists
            plugin_dir = os.environ.get("DECKY_PLUGIN_DIR", "")
            if plugin_dir:
                plugin_json = Path(plugin_dir) / "plugin.json"
                if plugin_json.exists():
                    zf.write(plugin_json, "plugin.json")

            # Write plugin.log if it exists (omit if missing)
            log_path = os.environ.get("DECKY_PLUGIN_LOG", "")
            if log_path and Path(log_path).exists():
                zf.write(Path(log_path), "plugin.log")

        size = zip_path.stat().st_size
        return {"success": True, "path": str(zip_path), "size": size}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _gather_runtime_state(
    settings: PluginSettings,
    watcher: JournalWatcher | None,
    submitter: EDDNSubmitter | None,
) -> dict:
    """Serialize runtime state into a dict for runtime_state.json."""
    state: dict = {
        "python_version": platform.python_version(),
        "decky_plugin_version": os.environ.get("DECKY_PLUGIN_VERSION", "unknown"),
    }

    # Watcher state
    if watcher:
        state["watcher_running"] = watcher.is_running
        state["journal_path"] = watcher._journal_path
        state["poll_interval"] = watcher._poll_interval
        state["file_positions"] = dict(watcher._file_positions)
        state["known_files"] = sorted(watcher._known_files)
    else:
        state["watcher_running"] = False

    # Settings
    state["journal_path_source"] = settings.get("journal_path_source")
    state["enabled"] = settings.get("enabled", True)
    state["uploader_id"] = settings.get("uploader_id", "")
    state["detailed_logging"] = settings.get("detailed_logging", False)

    # Submitter stats
    if submitter:
        stats = submitter.get_stats()
        state["submitter_stats"] = stats
    else:
        state["submitter_stats"] = {}

    return state
