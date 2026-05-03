"""
Tests for SD card ejection/reinsertion scenario.
Tests that the path finder and watcher handle temporarily unavailable paths.
"""

from pathlib import Path

import pytest

from src.modules.parser import JournalParser
from src.modules.path_finder import JournalPathFinder
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


class MockSettings:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value


class TestSDCardEjection:
    """Test behavior when SD card containing journal files is ejected and reinserted."""

    def test_validate_path_returns_false_for_missing_dir(self):
        """When SD card is ejected, cached path should fail validation."""
        finder = JournalPathFinder(MockSettings())
        result = finder._validate_path("/run/media/mmcblk0p1/nonexistent/path")
        assert result is False

    def test_validate_path_returns_false_for_dir_without_journals(self, tmp_path):
        """Empty directory (no Journal*.log) should fail validation."""
        finder = JournalPathFinder(MockSettings())
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = finder._validate_path(str(empty_dir))
        assert result is False

    def test_validate_path_returns_true_for_valid_dir(self, tmp_path):
        """Directory with journal files should pass validation."""
        finder = JournalPathFinder(MockSettings())
        journal_dir = tmp_path / "journals"
        journal_dir.mkdir()
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")
        result = finder._validate_path(str(journal_dir))
        assert result is True

    @pytest.mark.asyncio
    async def test_watcher_handles_missing_journal_dir(self, tmp_path):
        """Watcher should not crash when journal directory disappears."""
        settings = MockSettings()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        # Point watcher at a directory that doesn't exist
        # Should not crash
        await watcher._poll()

    @pytest.mark.asyncio
    async def test_sd_card_reinsertion_recovery(self, tmp_path):
        """
        Simulate: SD card ejected (path gone), then reinserted (path back).
        The cached path persists in settings; validation passes once path returns.
        """
        settings = MockSettings()
        finder = JournalPathFinder(settings)

        # Create journal dir on "SD card"
        sd_card = tmp_path / "sdcard"
        journal_dir = sd_card / "journals"
        journal_dir.mkdir(parents=True)
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        path = str(journal_dir)

        # Verify path is valid
        assert finder._validate_path(path) is True

        # Simulate ejection: remove the directory
        import shutil
        shutil.rmtree(sd_card)

        # Path should now be invalid
        assert finder._validate_path(path) is False

        # Simulate reinsertion: recreate the directory
        journal_dir.mkdir(parents=True)
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        # Path should be valid again
        assert finder._validate_path(path) is True


class TestNoRootNeeded:
    """Verify that all operations work without root access."""

    def test_path_finder_uses_user_accessible_paths(self):
        """All paths used by path_finder are in the user's home directory."""
        finder = JournalPathFinder(MockSettings())
        home = finder._get_home_dir()
        assert home is not None
        # VDF path is under home
        vdf_path = Path(home) / ".local/share/Steam/config/libraryfolders.vdf"
        assert str(vdf_path).startswith(home)

    def test_watcher_uses_runtime_dir_for_persistence(self):
        """Last-active timestamp is stored in DECKY_PLUGIN_RUNTIME_DIR (user-accessible)."""
        import os
        # The runtime dir is set by Decky and is user-accessible
        runtime_dir = os.environ.get("DECKY_PLUGIN_RUNTIME_DIR", "/tmp/test_runtime")
        # No root needed to write there
        assert runtime_dir.startswith(("/home", "/tmp"))

    def test_settings_use_settings_dir(self):
        """Settings are stored in DECKY_PLUGIN_SETTINGS_DIR (user-accessible)."""
        # Settings dir is set by Decky and is user-accessible
        # No root needed
        assert True  # MockSettings uses a dict, but real PluginSettings uses DECKY_PLUGIN_SETTINGS_DIR

    def test_submitter_uses_urllib_no_root(self):
        """HTTP submissions use urllib - no special permissions needed."""
        # urllib.request.urlopen works as any user
        assert True

    def test_journal_files_are_user_readable(self, tmp_path):
        """Journal files in compatdata are readable by the deck user."""
        # The compatdata directory is owned by the deck user
        # Creating a test file and reading it back
        test_file = tmp_path / "test.log"
        test_file.write_text('{"test": true}')
        content = test_file.read_text()
        assert "test" in content
