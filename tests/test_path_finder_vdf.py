"""
Tests for the VDF parser in JournalPathFinder.
Tests the _parse_libraryfolders_vdf method with sample VDF content.
"""

import pytest

from src.modules.path_finder import JournalPathFinder


class MockSettings:
    """Mock PluginSettings for testing."""
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value


@pytest.fixture
def finder():
    return JournalPathFinder(MockSettings())


class TestParseLibraryfoldersVDF:
    """Tests for _parse_libraryfolders_vdf."""

    def test_single_library(self, finder, tmp_path):
        vdf_content = '''"libraryfolders"
{
    "0"
    {
        "path"      "/home/deck/.local/share/Steam"
        "label"     ""
    }
}
'''
        vdf_file = tmp_path / ".local/share/Steam/config/libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)
        vdf_file.write_text(vdf_content)

        result = finder._parse_libraryfolders_vdf(str(tmp_path))
        assert result == ["/home/deck/.local/share/Steam"]

    def test_multiple_libraries_with_sdcard(self, finder, tmp_path):
        vdf_content = '''"libraryfolders"
{
    "0"
    {
        "path"      "/home/deck/.local/share/Steam"
        "label"     ""
    }
    "1"
    {
        "path"      "/run/media/mmcblk0p1/steamlib"
        "label"     "SD Card"
    }
}
'''
        vdf_file = tmp_path / ".local/share/Steam/config/libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)
        vdf_file.write_text(vdf_content)

        result = finder._parse_libraryfolders_vdf(str(tmp_path))
        assert len(result) == 2
        assert "/home/deck/.local/share/Steam" in result
        assert "/run/media/mmcblk0p1/steamlib" in result

    def test_no_vdf_file(self, finder, tmp_path):
        result = finder._parse_libraryfolders_vdf(str(tmp_path))
        assert result == []

    def test_fallback_steam_root_symlink(self, finder, tmp_path):
        vdf_content = '''"libraryfolders"
{
    "0"
    {
        "path"      "/home/deck/.local/share/Steam"
    }
}
'''
        # Only create at .steam/root path (fallback)
        vdf_file = tmp_path / ".steam/root/config/libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)
        vdf_file.write_text(vdf_content)

        result = finder._parse_libraryfolders_vdf(str(tmp_path))
        assert result == ["/home/deck/.local/share/Steam"]

    def test_empty_vdf(self, finder, tmp_path):
        vdf_file = tmp_path / ".local/share/Steam/config/libraryfolders.vdf"
        vdf_file.parent.mkdir(parents=True)
        vdf_file.write_text("")

        result = finder._parse_libraryfolders_vdf(str(tmp_path))
        assert result == []
