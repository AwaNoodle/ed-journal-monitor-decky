"""
Tests for the is_ed_likely_running method and check_ed_running callable.
These cover detection of ED that was already running when the plugin loaded.
"""

import os
import time

import pytest

from main import Plugin
from src.modules.path_finder import JournalPathFinder


class MockSettings:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value


@pytest.fixture
def finder():
    return JournalPathFinder(MockSettings())


class TestIsEdLikelyRunning:
    """Tests for JournalPathFinder.is_ed_likely_running()."""

    def test_returns_false_when_no_journal_path_configured(self, finder):
        """No journal_path in settings -> not running."""
        assert finder.is_ed_likely_running() is False

    def test_returns_false_when_journal_dir_missing(self, finder):
        """Configured path doesn't exist -> not running."""
        finder.settings._data["journal_path"] = "/nonexistent/path"
        assert finder.is_ed_likely_running() is False

    def test_returns_false_when_no_journal_files(self, finder, tmp_path):
        """Journal dir exists but has no Journal*.log files -> not running."""
        finder.settings._data["journal_path"] = str(tmp_path)
        assert finder.is_ed_likely_running() is False

    def test_returns_false_when_journal_file_stale(self, finder, tmp_path):
        """Journal file exists but was modified >5 min ago -> not running."""
        finder.settings._data["journal_path"] = str(tmp_path)
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text('{"event":"Fileheader"}')
        # Set mtime to 10 minutes ago
        old_time = time.time() - 600
        os.utime(journal_file, (old_time, old_time))

        assert finder.is_ed_likely_running() is False

    def test_returns_true_when_journal_file_recently_modified(self, finder, tmp_path):
        """Journal file modified within 5 minutes -> ED likely running."""
        finder.settings._data["journal_path"] = str(tmp_path)
        journal_file = tmp_path / "Journal.2026-05-06T120000.01.log"
        journal_file.write_text('{"event":"Fileheader"}')
        # File was just created, mtime is now -> should be detected as recent

        assert finder.is_ed_likely_running() is True

    def test_returns_true_with_recent_file_among_stale_ones(self, finder, tmp_path):
        """One recent file among stale ones -> ED likely running."""
        finder.settings._data["journal_path"] = str(tmp_path)

        # Stale file
        stale = tmp_path / "Journal.2026-01-01T120000.01.log"
        stale.write_text('{"event":"Fileheader"}')
        old_time = time.time() - 600
        os.utime(stale, (old_time, old_time))

        # Recent file
        recent = tmp_path / "Journal.2026-05-06T120000.01.log"
        recent.write_text('{"event":"Fileheader"}')

        assert finder.is_ed_likely_running() is True

    def test_returns_false_when_only_stale_files(self, finder, tmp_path):
        """Multiple stale files but none recent -> not running."""
        finder.settings._data["journal_path"] = str(tmp_path)
        for i in range(3):
            f = tmp_path / f"Journal.2026-01-0{i+1}T120000.01.log"
            f.write_text('{"event":"Fileheader"}')
            old_time = time.time() - 600 - i * 100
            os.utime(f, (old_time, old_time))

        assert finder.is_ed_likely_running() is False

    def test_boundary_at_five_minutes(self, finder, tmp_path):
        """File modified exactly at 5 min boundary (300s) -> not running (uses <)."""
        finder.settings._data["journal_path"] = str(tmp_path)
        journal_file = tmp_path / "Journal.2026-05-06T115500.01.log"
        journal_file.write_text('{"event":"Fileheader"}')
        boundary_time = time.time() - 300
        os.utime(journal_file, (boundary_time, boundary_time))

        # At exactly 300s, the check is < 300, so this should be False
        assert finder.is_ed_likely_running() is False

    def test_just_under_five_minutes(self, finder, tmp_path):
        """File modified just under 5 min ago -> running."""
        finder.settings._data["journal_path"] = str(tmp_path)
        journal_file = tmp_path / "Journal.2026-05-06T120000.01.log"
        journal_file.write_text('{"event":"Fileheader"}')
        just_under = time.time() - 299
        os.utime(journal_file, (just_under, just_under))

        assert finder.is_ed_likely_running() is True


class TestCheckEdRunningCallable:
    """Tests for Plugin.check_ed_running callable."""

    @pytest.mark.asyncio
    async def test_returns_false_when_path_finder_not_initialized(self):
        """path_finder not set up -> not running."""
        plugin = Plugin()
        result = await plugin.check_ed_running()
        assert result["running"] is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_journal_path(self, tmp_path):
        """No journal path found -> not running."""
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.path_finder = JournalPathFinder(plugin.settings)

        result = await plugin.check_ed_running()
        assert result["running"] is False

    @pytest.mark.asyncio
    async def test_returns_true_when_recent_journal_file(self, tmp_path):
        """Journal path with recently modified file -> running."""
        # Set up a journal directory with a recent file
        journal_dir = tmp_path / "Elite Dangerous"
        journal_dir.mkdir()
        journal_file = journal_dir / "Journal.2026-05-06T120000.01.log"
        journal_file.write_text('{"event":"Fileheader"}')

        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.settings._data["journal_path"] = str(journal_dir)
        plugin.path_finder = JournalPathFinder(plugin.settings)

        result = await plugin.check_ed_running()
        assert result["running"] is True

    @pytest.mark.asyncio
    async def test_attempts_path_discovery_if_no_cached_path(self, tmp_path):
        """When no cached path, check_ed_running calls find_journal_path first."""
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.path_finder = JournalPathFinder(plugin.settings)

        # Spy on find_journal_path
        original_find = plugin.path_finder.find_journal_path
        find_called = False

        async def spy_find():
            nonlocal find_called
            find_called = True
            return await original_find()

        plugin.path_finder.find_journal_path = spy_find

        result = await plugin.check_ed_running()
        assert find_called is True
        assert result["running"] is False  # No path to find in this test
