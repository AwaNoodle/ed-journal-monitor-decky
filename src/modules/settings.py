from __future__ import annotations

"""
Plugin settings management.
Persists configuration to DECKY_PLUGIN_SETTINGS_DIR.
"""

import json
import os
from pathlib import Path

import decky


class PluginSettings:
    """Manages plugin settings stored in DECKY_PLUGIN_SETTINGS_DIR."""

    def __init__(self) -> None:
        self._data: dict = {}
        self._settings_dir: Path = Path(os.environ.get("DECKY_PLUGIN_SETTINGS_DIR", ""))
        self._settings_file: Path = self._settings_dir / "settings.json"

    async def load(self) -> None:
        """Load settings from disk."""
        if self._settings_file.exists():
            try:
                with self._settings_file.open() as f:
                    self._data = json.load(f)
                decky.logger.info("Settings loaded")
            except (json.JSONDecodeError, OSError) as e:
                decky.logger.error(f"Failed to load settings: {e}")
                self._data = {}
        else:
            self._data = {}

    async def save(self) -> None:
        """Persist settings to disk."""
        try:
            self._settings_dir.mkdir(parents=True, exist_ok=True)
            with self._settings_file.open("w") as f:
                json.dump(self._data, f, indent=2)
            decky.logger.debug("Settings saved")
        except OSError as e:
            decky.logger.error(f"Failed to save settings: {e}")

    def get(self, key: str, default: object = None) -> object:
        """Get a setting value."""
        return self._data.get(key, default)

    async def set(self, key: str, value: object) -> None:
        """Set a setting value and persist."""
        self._data[key] = value
        await self.save()
