from __future__ import annotations

"""
Journal path finder.
Auto-discovers the ED journal directory by scanning Steam library configuration.
"""

import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    from src.modules.settings import PluginSettings

ED_APPID = "359320"
_ED_RUNNING_THRESHOLD_SECS = 300  # 5 minutes


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

    def is_ed_likely_running(self) -> bool:
        """Check if ED appears to be running.

        Uses two detection methods:
        1. Check /proc for ED process names (most reliable)
        2. Check for recently-modified journal files (fallback)

        This is used to detect ED that was already running when the plugin loaded
        (since RegisterForAppLifetimeNotifications only fires on state changes).
        """
        # Method 1: Process-based detection
        if self._check_ed_process():
            decky.logger.info("ED process detected via /proc scan")
            return True

        # Method 2: Journal file mtime heuristic
        journal_path = self.settings.get("journal_path")
        if not journal_path:
            return False

        try:
            journal_dir = Path(journal_path)
            if not journal_dir.is_dir():
                return False

            now = time.time()
            for f in journal_dir.glob("Journal*.log"):
                try:
                    if now - f.stat().st_mtime < _ED_RUNNING_THRESHOLD_SECS:
                        decky.logger.info(f"Journal file recently modified, ED likely running: {f.name}")
                        return True
                except OSError:
                    continue
        except (OSError, ValueError):
            return False

        return False

    def _check_ed_process(self) -> bool:
        """Check /proc for running Elite Dangerous processes.

        ED runs as 'EliteDangerous64.exe' under Proton, or potentially
        as 'EliteDangerous.exe'. We scan /proc/*/comm for these names.

        Note: /proc/PID/comm is kernel-truncated to 15 chars, so
        EliteDangerous64 may appear as EliteDangerous6.
        """
        ed_process_names = {
            "EliteDangerous6",
            "EliteDangerous64",
            "EliteDangerous64.exe",
            "WatchDog64",
            "WatchDog64.exe",
            "EDLaunch",
            "EDLaunch.exe",
        }
        try:
            proc = Path("/proc")
            for pid_dir in proc.iterdir():
                if not pid_dir.name.isdigit():
                    continue
                try:
                    comm = (pid_dir / "comm").read_text().strip()
                    if comm in ed_process_names:
                        return True
                except (OSError, PermissionError):
                    continue
        except OSError:
            return False
        return False

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
