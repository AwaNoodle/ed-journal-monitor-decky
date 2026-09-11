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

# Setting keys whose values must never leave the device in a diagnostics bundle.
# A redaction key set (rather than an allow-list) keeps unrelated future settings
# in the bundle, where they are useful to support, while still blanking secrets.
SECRET_SETTING_KEYS = frozenset({"edsm_api_key"})
REDACTED = "<redacted>"


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

            # Write a redacted copy of settings.json — never the raw file, which
            # holds the plaintext EDSM API key.
            settings_file = Path(settings_dir) / "settings.json"
            if settings_file.exists():
                zf.writestr("settings.json", _redacted_settings_json(settings_file))

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
        state["journal_path"] = _mask_home(watcher._journal_path)
        state["poll_interval"] = watcher._poll_interval
        state["file_positions"] = {
            _mask_home(path): position for path, position in watcher._file_positions.items()
        }
        state["known_files"] = sorted(_mask_home(path) for path in watcher._known_files)
    else:
        state["watcher_running"] = False

    # Settings
    state["journal_path_source"] = settings.get("journal_path_source")
    state["enabled"] = settings.get("enabled", True)
    # uploader_id is deliberately not redacted: it is the EDDN uploaderID header,
    # published publicly with every message we submit by design. Blanking it in a
    # local bundle protects nothing and costs support a field they need to trace
    # a message through the EDDN monitor.
    state["uploader_id"] = settings.get("uploader_id", "")
    state["detailed_logging"] = settings.get("detailed_logging", False)

    # Submitter stats
    if submitter:
        stats = submitter.get_stats()
        state["submitter_stats"] = stats
    else:
        state["submitter_stats"] = {}

    return state


def _redacted_settings_json(settings_file: Path) -> str:
    """Serialize settings.json with secret values replaced.

    Falls back to a JSON note (never the raw bytes) if the file cannot be read
    or parsed, so an unparseable file can't smuggle a key into the bundle.
    """
    try:
        with settings_file.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        return json.dumps({"error": f"settings.json could not be read: {type(e).__name__}"}, indent=2)

    if not isinstance(data, dict):
        return json.dumps({"error": "settings.json is not a JSON object"}, indent=2)

    redacted = {
        key: (REDACTED if key in SECRET_SETTING_KEYS and value else value)
        for key, value in data.items()
    }
    return json.dumps(redacted, indent=2)


def _mask_home(value: str) -> str:
    """Replace a leading home-directory prefix with '~'.

    Off-Deck the journal path embeds the OS username; the path structure is the
    diagnostic value, the username is not.
    """
    if not value:
        return value
    home = str(Path.home())
    if value == home:
        return "~"
    if value.startswith(home + os.sep):
        return "~" + value[len(home):]
    return value
