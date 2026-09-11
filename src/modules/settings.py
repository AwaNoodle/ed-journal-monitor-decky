from __future__ import annotations

"""
Plugin settings management.
Persists configuration to DECKY_PLUGIN_SETTINGS_DIR.
"""

import contextlib
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

    async def save(self) -> bool:
        """Persist settings to disk with owner-only permissions. Returns success.

        The settings file holds the EDSM API key, so it is written through a
        sibling temp file created 0600 (never widened by the inherited umask)
        and `os.replace`d into place: a reader either sees the previous file or
        the complete new one, where truncate-then-write could leave an empty
        settings.json if the write were interrupted. Never raises — callers use
        the return value, because a swallowed failure on the credential path
        would report a cleared API key that is still on disk.
        """
        tmp_path = self._settings_file.with_suffix(".json.tmp")
        try:
            self._settings_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._tighten_dir()
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                os.fchmod(fd, 0o600)
                json.dump(self._data, f, indent=2)
                f.flush()
                os.fsync(fd)
            tmp_path.replace(self._settings_file)
            decky.logger.debug("Settings saved")
            return True
        except (OSError, TypeError, ValueError) as e:
            decky.logger.error(f"Failed to save settings: {e}")
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
            return False

    def _tighten_dir(self) -> None:
        """Keep the settings directory owner-only.

        `mkdir(mode=0o700)` only applies to a directory this call creates, so an
        existing settings dir keeps whatever mode it had. Best-effort: a
        directory we may not chmod (not ours) can still be writable, and losing
        every settings write over its mode would be worse than the loose mode.
        """
        try:
            self._settings_dir.chmod(0o700)
        except OSError as e:
            decky.logger.warning(f"Could not tighten settings dir permissions: {e}")

    def get(self, key: str, default: object = None) -> object:
        """Get a setting value."""
        return self._data.get(key, default)

    async def set(self, key: str, value: object) -> None:
        """Set a setting value and persist."""
        self._data[key] = value
        await self.save()

    async def delete(self, key: str) -> bool:
        """Remove a setting and persist. No-op when the key is absent.

        Returns whether the removal reached disk; on a failed write the value is
        restored in memory so in-memory state keeps matching the file — a
        cleared API key that is still on disk must keep reporting as set, or the
        frontend shows consent withdrawn while the next load re-arms EDSM.
        """
        if key not in self._data:
            return True
        value = self._data.pop(key)
        if await self.save():
            return True
        self._data[key] = value
        return False
