"""
Tests for the watcher's ingestion limits.

The watched directory is a user-settable path (the Steam library scan reaches
removable media), so its contents are untrusted: discovery must reject anything
that is not a plausible regular journal file, reads must be bounded and must
never block the plugin's single event loop, and a failing initial scan must not
leave the watcher reporting "monitoring" with nothing running.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock

import pytest
from conftest import MockSettings

import src.modules.watcher as watcher_mod
from src.modules.constants import MAX_AUXILIARY_RETRIES_PER_POLL
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


class TestStartupRobustness:
    """A failing initial scan must not abort start()."""

    @pytest.fixture
    def runtime_dir(self, tmp_path, monkeypatch):
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        (runtime / "last_active").write_text("2026-01-01T00:00:00+00:00")
        monkeypatch.setenv("DECKY_PLUGIN_RUNTIME_DIR", str(runtime))
        return runtime

    @pytest.mark.asyncio
    async def test_absurd_mtime_does_not_abort_start(self, watcher, tmp_path, runtime_dir):
        journals = tmp_path / "journals"
        journals.mkdir()

        poisoned = journals / "Journal.2026-01-12T120000.01.log"
        poisoned.write_text(FILEHEADER, encoding="utf-8")
        os.utime(str(poisoned), (10**12, 10**12))

        good = journals / "Journal.2026-01-13T120000.01.log"
        good.write_text(FILEHEADER + LOADGAME + jump_line("Sol"), encoding="utf-8")

        consumer = RecordingConsumer()
        watcher._consumers = [consumer]

        await watcher.start(str(journals))
        try:
            assert watcher.is_running is True
            assert watcher._poll_task is not None
            assert not watcher._poll_task.done()
            # Only the poisoned file is skipped; its neighbour still replays.
            assert consumer.systems == ["Sol"]
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_scan_failure_still_establishes_the_poll_task(self, watcher, tmp_path, runtime_dir):
        async def boom(last_active):
            raise RuntimeError("scan exploded")

        watcher._initial_scan = boom

        await watcher.start(str(tmp_path))
        try:
            assert watcher.is_running is True
            assert watcher._poll_task is not None
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_is_running_is_false_until_the_poll_task_exists(self, watcher, tmp_path, runtime_dir):
        seen = {}

        async def observe(last_active):
            seen["during_scan"] = watcher.is_running
            seen["task_during_scan"] = watcher._poll_task

        watcher._initial_scan = observe

        await watcher.start(str(tmp_path))
        try:
            # Nothing was polling yet, so nothing reported "monitoring".
            assert seen["during_scan"] is False
            assert seen["task_during_scan"] is None
            assert watcher.is_running is True
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_concurrent_start_does_not_scan_twice(self, watcher, tmp_path, runtime_dir):
        scans = []

        async def slow_scan(last_active):
            scans.append(last_active)
            await asyncio.sleep(0)

        watcher._initial_scan = slow_scan

        await asyncio.gather(watcher.start(str(tmp_path)), watcher.start(str(tmp_path)))
        try:
            assert len(scans) == 1
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_stop_during_the_scan_leaves_nothing_running(self, watcher, tmp_path, runtime_dir):
        async def scan_then_stopped(last_active):
            await watcher.stop()

        watcher._initial_scan = scan_then_stopped

        await watcher.start(str(tmp_path))

        assert watcher.is_running is False
        assert watcher._poll_task is None


class TestStopDuringCatchUpReplay:
    """A stop() during the catch-up replay must stop the uploading too.

    The replay awaits real EDDN submissions (and sidecar retries), so it can
    outlive the stop_watcher/set_enabled(false) call that already told the user
    uploading had ceased -- and the EDSM forwarder's final flush has been taken
    by then, so anything replayed afterwards reaches EDDN but never EDSM.
    """

    SYSTEMS = (
        ("Sol", "Alpha Centauri", "Barnard's Star"),
        ("Wolf 359", "Lalande 21185", "Sirius"),
        ("Achenar", "Lave", "Diso"),
    )

    @pytest.fixture
    def catch_up_dir(self, tmp_path, monkeypatch):
        """Three journals to replay, all newer than the last-active stamp."""
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        (runtime / "last_active").write_text("2026-01-01T00:00:00+00:00")
        monkeypatch.setenv("DECKY_PLUGIN_RUNTIME_DIR", str(runtime))

        journals = tmp_path / "journals"
        journals.mkdir()
        for index, systems in enumerate(self.SYSTEMS, start=10):
            (journals / f"Journal.2026-01-{index}T120000.01.log").write_text(
                FILEHEADER + LOADGAME + "".join(jump_line(system) for system in systems),
                encoding="utf-8",
            )
        return journals

    @staticmethod
    def _recording_submit(submitted: list[str], on_call=None):
        async def submit(message, **kwargs):
            submitted.append(message["message"]["StarSystem"])
            if on_call is not None:
                await on_call(len(submitted))
            return True

        return submit

    @pytest.mark.asyncio
    async def test_stop_partway_through_the_replay_stops_submitting(self, watcher, catch_up_dir):
        submitted: list[str] = []

        async def stop_after_first(count):
            if count == 1:
                # The user switches monitoring off while the replay is awaiting
                # this very submission.
                await watcher.stop()

        watcher.submitter.submit = self._recording_submit(submitted, stop_after_first)

        await watcher.start(str(catch_up_dir))

        # Neither the rest of the file being replayed nor the two files behind
        # it reach EDDN after stop() returned.
        assert submitted == ["Sol"]
        assert watcher.is_running is False
        assert watcher._poll_task is None

    @pytest.mark.asyncio
    async def test_replay_without_a_stop_still_covers_every_file(self, watcher, catch_up_dir):
        submitted: list[str] = []
        watcher.submitter.submit = self._recording_submit(submitted)

        await watcher.start(str(catch_up_dir))
        try:
            assert submitted == [system for systems in self.SYSTEMS for system in systems]
            assert watcher.is_running is True
            assert watcher._poll_task is not None
        finally:
            await watcher.stop()


class TestAuxiliaryRetryBudget:
    """Retry sleeps are budgeted per poll cycle, not per event."""

    @pytest.fixture
    def counted_sleep(self, monkeypatch):
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(watcher_mod.asyncio, "sleep", fake_sleep)
        return sleeps

    @pytest.mark.asyncio
    async def test_many_missing_sidecars_share_one_budget(self, watcher, tmp_path, counted_sleep):
        # Six auxiliary events whose sidecar never appears. Per-event retries
        # would stall the poll for 24 sleeps; the shared budget caps it.
        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(
            FILEHEADER
            + LOADGAME
            + "".join(
                f'{{"timestamp":"2026-01-12T13:0{i}:00Z","event":"Outfitting","MarketID":12866676{i}}}\n'
                for i in range(6)
            ),
            encoding="utf-8",
        )

        await watcher._poll()

        assert len(counted_sleep) == MAX_AUXILIARY_RETRIES_PER_POLL
        watcher.submitter.submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_budget_resets_each_poll(self, watcher, tmp_path, counted_sleep):
        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(
            FILEHEADER + LOADGAME + '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._poll()
        first_poll = len(counted_sleep)
        assert first_poll > 0

        with journal.open("a", encoding="utf-8") as f:
            f.write('{"timestamp":"2026-01-12T13:06:00Z","event":"Outfitting","MarketID":128666763}\n')

        await watcher._poll()

        assert len(counted_sleep) - first_poll == first_poll

    @pytest.mark.asyncio
    async def test_sidecar_arriving_on_retry_still_submits(self, watcher, tmp_path, copy_fixture, counted_sleep):
        # The happy path is unchanged: one retry, then the file is there.
        original_parse = watcher.parser.parse_auxiliary_file
        calls = []

        def flaky_parse(filepath):
            calls.append(filepath)
            if len(calls) == 1:
                return None
            return original_parse(filepath)

        copy_fixture("Outfitting.json")
        watcher.parser.parse_auxiliary_file = flaky_parse

        journal = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal.write_text(
            FILEHEADER + LOADGAME + '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._poll()

        assert len(counted_sleep) == 1
        watcher.submitter.submit.assert_awaited_once()


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
