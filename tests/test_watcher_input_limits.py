"""
Tests for the watcher's ingestion limits.

The watched directory is a user-settable path (the Steam library scan reaches
removable media), so its contents are untrusted: discovery must reject anything
that is not a plausible regular journal file, and reads must be bounded and
must never block the plugin's single event loop.
"""

import asyncio
import os
import time
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


class TestIncrementalByteReads:
    """Positions are byte offsets; only complete lines are dispatched."""

    @pytest.mark.asyncio
    async def test_only_appended_lines_are_processed(self, watcher, tmp_path):
        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher._poll()
        assert consumer.systems == ["Sol"]

        with journal.open("a", encoding="utf-8") as f:
            f.write(jump_line("Wolf 359", "2026-01-12T12:07:00Z"))

        await watcher._poll()

        assert consumer.systems == ["Sol", "Wolf 359"]
        assert watcher._file_positions[str(journal)] == journal.stat().st_size

    @pytest.mark.asyncio
    async def test_torn_final_line_is_deferred_then_processed_once_complete(self, watcher, tmp_path):
        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        complete = FILEHEADER + LOADGAME
        torn = jump_line("Wolf 359", "2026-01-12T12:07:00Z")
        half = torn[: len(torn) // 2]
        journal.write_text(complete + half, encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher._poll()

        # The half-written line is neither parsed nor skipped: the offset stops
        # at the last complete line so the event survives to the next poll.
        assert consumer.systems == []
        assert watcher._file_positions[str(journal)] == len(complete.encode())

        with journal.open("a", encoding="utf-8") as f:
            f.write(torn[len(torn) // 2 :])

        await watcher._poll()

        assert consumer.systems == ["Wolf 359"]
        assert watcher._file_positions[str(journal)] == journal.stat().st_size

    @pytest.mark.asyncio
    async def test_newline_free_chunk_at_the_cap_advances_the_offset(self, watcher, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(watcher_mod, "JOURNAL_READ_CHUNK_BYTES", 16)

        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_bytes(b"x" * 40)

        with caplog.at_level("WARNING", logger="decky"):
            await watcher._poll()
            assert watcher._file_positions[str(journal)] == 16
            await watcher._poll()
            assert watcher._file_positions[str(journal)] == 32

        # Never re-reads the same bytes: progress is guaranteed.
        assert any("without a line break" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_read_is_capped_per_poll_and_resumes_next_poll(self, watcher, tmp_path, monkeypatch):
        first = FILEHEADER + LOADGAME
        monkeypatch.setattr(watcher_mod, "JOURNAL_READ_CHUNK_BYTES", len(first.encode()) + 10)

        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(first + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher._poll()
        assert [event for event, _ in consumer.observed] == ["Fileheader", "LoadGame"]
        assert watcher._file_positions[str(journal)] == len(first.encode())

        await watcher._poll()
        assert consumer.systems == ["Sol"]
        assert watcher._file_positions[str(journal)] == journal.stat().st_size

    @pytest.mark.asyncio
    async def test_truncated_file_is_re_read_from_the_start(self, watcher, tmp_path):
        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher._poll()
        assert consumer.systems == ["Sol"]

        # Rotated in place: same name, shorter content.
        journal.write_text(FILEHEADER + jump_line("Wolf 359", "2026-01-12T12:07:00Z"), encoding="utf-8")

        await watcher._poll()

        assert consumer.systems == ["Sol", "Wolf 359"]
        assert watcher._file_positions[str(journal)] == journal.stat().st_size

    def test_track_file_position_reads_nothing(self, watcher, tmp_path, monkeypatch):
        journal = tmp_path / "Journal.2026-01-11T120000.01.log"
        journal.write_text(FILEHEADER + LOADGAME, encoding="utf-8")

        def explode(*args, **kwargs):
            raise AssertionError("tracking a file must not open it")

        monkeypatch.setattr("builtins.open", explode)
        monkeypatch.setattr("pathlib.Path.open", explode)

        watcher._track_file_position(str(journal))

        assert watcher._file_positions[str(journal)] == journal.stat().st_size
        assert str(journal) in watcher._known_files


@pytest.mark.asyncio
async def test_slow_file_read_does_not_stall_the_event_loop(watcher, tmp_path):
    """A slow read must not freeze everything else the plugin is doing."""
    journal = tmp_path / "Journal.2026-01-12T120000.01.log"
    journal.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

    original = watcher._read_new_lines

    def slow_read(filepath):
        time.sleep(0.3)
        return original(filepath)

    watcher._read_new_lines = slow_read

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    heartbeat = asyncio.create_task(ticker())
    consumer = RecordingConsumer()
    watcher._consumers = [consumer]
    try:
        await watcher._process_file(str(journal))
    finally:
        heartbeat.cancel()

    # Other coroutines kept running throughout the blocking read.
    assert ticks >= 5
    assert consumer.systems == ["Sol"]
