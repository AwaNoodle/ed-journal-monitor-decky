"""
Tests for the JournalWatcher module.
Tests position tracking and incremental reading.
"""

import pytest

from src.modules.parser import JournalParser
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


@pytest.fixture
def watcher():
    settings = MockSettings()
    parser = JournalParser()
    validator = EDDNValidator()
    submitter = EDDNSubmitter(settings)
    return JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)


class TestFilePositions:
    """Tests for file position tracking."""

    def test_initial_position_is_zero(self, watcher):
        assert watcher._file_positions == {}

    def test_position_updates_after_processing(self, watcher, tmp_path):
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n',
        )

        import asyncio
        asyncio.run(watcher._process_file(str(journal_file)))

        assert watcher._file_positions[str(journal_file)] == 2

    def test_incremental_reading(self, watcher, tmp_path):
        """File is written to after initial read - only new lines should be processed."""
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n',
        )

        import asyncio
        asyncio.run(watcher._process_file(str(journal_file)))
        assert watcher._file_positions[str(journal_file)] == 2

        # Append new content
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6}\n',
        )

        asyncio.run(watcher._process_file(str(journal_file)))
        assert watcher._file_positions[str(journal_file)] == 3


class TestIsFromToday:
    """Tests for _is_from_today."""

    def test_today_filename(self, watcher):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"Journal.{today}T120000.01.log"
        assert watcher._is_from_today(filename) is True

    def test_old_filename(self, watcher):
        assert watcher._is_from_today("Journal.2020-01-01T120000.01.log") is False

    def test_invalid_filename(self, watcher):
        assert watcher._is_from_today("notajournal.log") is False
