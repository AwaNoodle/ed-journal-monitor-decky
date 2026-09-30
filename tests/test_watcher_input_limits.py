"""
Tests for the watcher's ingestion limits.

The watched directory is a user-settable path (the Steam library scan reaches
removable media), so its contents are untrusted: discovery must reject anything
that is not a plausible regular journal file.
"""

import asyncio
import os
from unittest.mock import AsyncMock

import pytest
from conftest import MockSettings

import src.modules.watcher as watcher_mod
from src.modules.parser import JournalParser
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher

FILEHEADER = '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.3.0.1","build":"r322188/r0"}\n'
LOADGAME = (
    '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame",'
    '"Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
)


def jump_line(system: str, timestamp: str = "2026-01-12T12:05:30Z") -> str:
    return (
        f'{{"timestamp":"{timestamp}","event":"FSDJump","StarSystem":"{system}",'
        '"SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15}\n'
    )


class RecordingConsumer:
    """A fake StreamConsumer that records every event it observes."""

    def __init__(self):
        self.observed = []

    def observe(self, event, session_state):
        self.observed.append((event.event_type, event.raw.get("StarSystem")))

    @property
    def systems(self):
        return [system for _, system in self.observed if system]


@pytest.fixture
def watcher(tmp_path):
    from src.modules.signal_batcher import SignalBatcher

    instance = JournalWatcher(
        settings=MockSettings(),
        parser=JournalParser(),
        validator=EDDNValidator(),
        submitter=EDDNSubmitter(MockSettings()),
        signal_batcher=SignalBatcher(),
    )
    instance._journal_path = str(tmp_path)
    instance.submitter.submit = AsyncMock(return_value=True)
    return instance


class TestDiscoveryGuard:
    """Only regular files of plausible size are ever opened."""

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFOs only")
    @pytest.mark.asyncio
    async def test_fifo_matching_the_glob_is_skipped_without_blocking(self, watcher, tmp_path):
        # A FIFO nobody writes to blocks open() forever; the poll runs on the
        # plugin's only event loop, so this must never be opened at all.
        fifo = tmp_path / "Journal.fifo.log"
        os.mkfifo(str(fifo))

        real = tmp_path / "Journal.2026-01-12T120000.01.log"
        real.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await asyncio.wait_for(watcher._poll(), timeout=10)

        assert str(fifo) not in watcher._file_positions
        # The real journal beside it is processed as usual.
        assert consumer.systems == ["Sol"]

    @pytest.mark.asyncio
    async def test_oversized_file_is_skipped(self, watcher, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(watcher_mod, "MAX_JOURNAL_FILE_BYTES", 32)

        huge = tmp_path / "Journal.2026-01-12T120000.01.log"
        huge.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        with caplog.at_level("WARNING", logger="decky"):
            await watcher._poll()
            await watcher._poll()

        assert consumer.observed == []
        assert str(huge) not in watcher._file_positions
        # Warned once per path per reason, not once per poll.
        assert sum("exceeds" in record.message for record in caplog.records) == 1

    @pytest.mark.asyncio
    async def test_directory_matching_the_glob_is_skipped(self, watcher, tmp_path):
        (tmp_path / "Journal.decoy.log").mkdir()

        real = tmp_path / "Journal.2026-01-12T120000.01.log"
        real.write_text(FILEHEADER + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher._poll()

        assert str(tmp_path / "Journal.decoy.log") not in watcher._file_positions
        assert consumer.systems == ["Sol"]
