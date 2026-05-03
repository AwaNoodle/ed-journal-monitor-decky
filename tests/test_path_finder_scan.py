"""
Tests for compatdata scanning in JournalPathFinder.
Tests the _scan_libraries method with mock directory structures.
"""

import pytest

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


class TestScanLibraries:
    """Tests for _scan_libraries with mock compatdata structures."""

    def test_finds_journal_dir_with_steamuser(self, finder, tmp_path):
        """Standard case: journal under steamuser in internal storage."""
        journal_dir = (
            tmp_path / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "steamuser"
            / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        journal_dir.mkdir(parents=True)
        # Create a journal file so validation passes
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}'
        )

        result = finder._scan_libraries([str(tmp_path)])
        assert result is not None
        assert "Elite Dangerous" in result
        assert "359320" in result

    def test_finds_journal_on_sd_card(self, finder, tmp_path):
        """Journal on SD card library path."""
        sd_root = tmp_path / "sdcard"
        journal_dir = (
            sd_root / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "steamuser"
            / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        journal_dir.mkdir(parents=True)
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        result = finder._scan_libraries([str(sd_root)])
        assert result is not None

    def test_no_compatdata(self, finder, tmp_path):
        """ED not installed: no compatdata directory."""
        result = finder._scan_libraries([str(tmp_path)])
        assert result is None

    def test_compatdata_exists_but_no_journal_dir(self, finder, tmp_path):
        """ED installed but never launched: compatdata exists, no Saved Games."""
        compat_dir = (
            tmp_path / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "steamuser"
        )
        compat_dir.mkdir(parents=True)

        result = finder._scan_libraries([str(tmp_path)])
        assert result is None

    def test_journal_dir_exists_but_no_log_files(self, finder, tmp_path):
        """Journal directory exists but is empty (shouldn't normally happen)."""
        journal_dir = (
            tmp_path / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "steamuser"
            / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        journal_dir.mkdir(parents=True)
        # No journal files

        result = finder._scan_libraries([str(tmp_path)])
        assert result is None

    def test_multiple_libraries_finds_correct_one(self, finder, tmp_path):
        """ED installed on second library (SD card), not first."""
        empty_lib = tmp_path / "internal"
        empty_lib.mkdir()

        sd_root = tmp_path / "sdcard"
        journal_dir = (
            sd_root / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "steamuser"
            / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        journal_dir.mkdir(parents=True)
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        result = finder._scan_libraries([str(empty_lib), str(sd_root)])
        assert result is not None
        assert str(sd_root) in result

    def test_finds_alternative_username(self, finder, tmp_path):
        """Journal under a non-steamuser directory (older Proton versions)."""
        journal_dir = (
            tmp_path / "steamapps" / "compatdata" / "359320" / "pfx"
            / "drive_c" / "users" / "deck"
            / "Saved Games" / "Frontier Developments" / "Elite Dangerous"
        )
        journal_dir.mkdir(parents=True)
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        result = finder._scan_libraries([str(tmp_path)])
        assert result is not None
        assert "deck" in result
