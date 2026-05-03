from __future__ import annotations

"""
Journal path finder.
Auto-discovers the ED journal directory by scanning Steam library configuration.
"""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    from src.modules.settings import PluginSettings

ED_APPID = "359320"


class JournalPathFinder:
    """Finds the Elite Dangerous journal directory on the filesystem."""

    def __init__(self, settings: PluginSettings) -> None:
        self.settings = settings

    async def find_journal_path(self) -> str | None:
        """
        Find the ED journal directory using the cascade:
        1. Cached path from settings (validate it still exists)
        2. VDF scan of Steam libraries
        Returns the path string or None.
        """
        # Step 1: Check cached path
        cached_path = self.settings.get("journal_path")
        if cached_path:
            validated = self._validate_path(cached_path)
            if validated:
                decky.logger.info(f"Using cached journal path: {cached_path}")
                return cached_path
            # Path may be temporarily unavailable (e.g. SD card ejected).
            # Do NOT clear cache — spec requires preserving it for reinsertion recovery.
            decky.logger.info("Cached journal path temporarily unavailable")
            return None

        # Step 2: VDF scan
        home = self._get_home_dir()
        if not home:
            return None

        libraries = self._parse_libraryfolders_vdf(home)
        if libraries:
            found_path = self._scan_libraries(libraries)
            if found_path:
                await self.settings.set("journal_path", found_path)
                await self.settings.set("journal_path_source", "auto")
                decky.logger.info(f"Found journal path via VDF scan: {found_path}")
                return found_path

        return None

    async def set_manual_path(self, path: str) -> dict:
        """Set a manually configured journal path after validating it."""
        validated = self._validate_path(path)
        if validated:
            await self.settings.set("journal_path", path)
            await self.settings.set("journal_path_source", "manual")
            decky.logger.info(f"Manual journal path set: {path}")
            return {"success": True, "path": path}
        return {"success": False, "error": f"Invalid journal path: {path}"}

    def _validate_path(self, path: str) -> bool:
        """Validate that a path contains ED journal files."""
        try:
            journal_dir = Path(path)
            if not journal_dir.is_dir():
                return False
            # Check for Journal*.log files
            log_files = list(journal_dir.glob("Journal*.log"))
            return len(log_files) > 0
        except (OSError, ValueError):
            return False

    def _get_home_dir(self) -> str | None:
        """Get the user's home directory from Decky environment."""
        home = os.environ.get("DECKY_USER_HOME")
        if not home:
            home = str(Path.home())
        return home

    def _parse_libraryfolders_vdf(self, home: str) -> list[str]:
        """
        Parse Steam's libraryfolders.vdf to extract library paths.
        Returns a list of directory paths.
        """
        vdf_paths = [
            Path(home) / ".local/share/Steam/config/libraryfolders.vdf",
            Path(home) / ".steam/root/config/libraryfolders.vdf",
        ]

        vdf_path = None
        for p in vdf_paths:
            if p.is_file():
                vdf_path = p
                break

        if not vdf_path:
            decky.logger.warning("libraryfolders.vdf not found")
            return []

        try:
            content = vdf_path.read_text(encoding="utf-8", errors="replace")
            libraries = []
            # Match "path" lines: "path"\t\t"/some/path"
            for match in re.finditer(r'"path"\s+"(.+?)"', content):
                libraries.append(match.group(1))
            decky.logger.debug(f"Found {len(libraries)} Steam libraries")
            return libraries
        except OSError as e:
            decky.logger.error(f"Failed to read libraryfolders.vdf: {e}")
            return []

    def _scan_libraries(self, libraries: list[str]) -> str | None:
        """
        Scan each Steam library for the ED compatdata journal directory.
        """
        for lib_path in libraries:
            compat_dir = Path(lib_path) / "steamapps" / "compatdata" / ED_APPID / "pfx"
            if not compat_dir.is_dir():
                continue

            # Glob for journal dir under any user folder
            candidates = compat_dir.glob(
                "drive_c/users/*/Saved Games/Frontier Developments/Elite Dangerous",
            )

            for candidate in candidates:
                if candidate.is_dir() and list(candidate.glob("Journal*.log")):
                    return str(candidate)

        return None
