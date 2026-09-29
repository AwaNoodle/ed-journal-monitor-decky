"""
Tests for the EDSM stream-consumer forwarder.

Covers buffering/filtering (discard list, API-key gate, Legacy gate, journal
order, transient-state hints), flush lifecycle (size/time/forced), per-target
stats with reset + failure isolation, and msgnum-driven retry behavior.
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest
from conftest import MockSettings

from src.modules.forwarders.edsm import EdsmForwarder
from src.modules.forwarders.edsm_client import EdsmResponse
from src.modules.parser import ParsedEvent, SessionState


def _event(event_type="FSDJump", **fields):
    raw = {"timestamp": "2026-01-12T12:00:00Z", "event": event_type}
    raw.update(fields)
    return ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])


def _session(game_version="4.1.0.404", **fields):
    state = SessionState()
    state.game_version = game_version
    state.game_build = fields.get("game_build", "r280105/r0")
    for k, v in fields.items():
        setattr(state, k, v)
    return state


def _ok():
    return EdsmResponse(msgnum=100, msg="OK", ok=True)


def _fatal(msgnum=203):
    return EdsmResponse(msgnum=msgnum, msg="Commander name/API Key not found.", fatal=True)


def _transient():
    return EdsmResponse(msgnum=500, msg="Exception", transient=True)


class FakeActivityLog:
    """Records calls so tests can assert per-event activity recording."""

    def __init__(self):
        self.entries = []

    async def record_success(self, event_type, target="eddn"):
        self.entries.append({"outcome": "success", "event_type": event_type, "target": target})

    async def record_failure(self, event_type, error_type, error_message, http_status=None, target="eddn"):
        self.entries.append({
            "outcome": "failure", "event_type": event_type, "target": target,
            "error_type": error_type, "error_message": error_message,
        })


def _make_forwarder(api_key="key-123", discard=None, client=None, flush_size=20,
                    flush_interval=30, max_buffer=500, activity_log=None):
    settings = MockSettings(initial_data={
        "edsm_commander_name": "CmdrTest",
        "edsm_api_key": api_key,
        "software_version": "0.4.0",
    })
    client = client or MagicMock()
    fwd = EdsmForwarder(settings, client=client, flush_size=flush_size,
                        flush_interval=flush_interval, max_buffer=max_buffer,
                        activity_log=activity_log)
    if discard is not None:
        fwd._discard = set(discard)
        fwd._active = bool(api_key)
    return fwd


async def _settle(predicate, timeout=2.0):
    """Wait for work dispatched to the default executor to land back on the loop."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            return False
        await asyncio.sleep(0.005)
    return True


class TestObserveFiltering:
    def test_queues_non_discarded_verbatim(self):
        fwd = _make_forwarder(discard={"Music"})
        fwd.observe(_event("FSDJump", StarSystem="Sol"), _session())
        assert len(fwd._buffer) == 1
        assert fwd._buffer[0]["event"] == "FSDJump"
        assert fwd._buffer[0]["StarSystem"] == "Sol"

    def test_drops_discarded_events(self):
        fwd = _make_forwarder(discard={"Music"})
        fwd.observe(_event("Music"), _session())
        assert fwd._buffer == []

    def test_nothing_queued_without_api_key(self):
        fwd = _make_forwarder(api_key="", discard={"Music"})
        fwd.observe(_event("FSDJump"), _session())
        assert fwd._buffer == []

    def test_nothing_queued_on_legacy(self):
        fwd = _make_forwarder(discard={"Music"})
        fwd.observe(_event("FSDJump"), _session(game_version="3.8.0.200"))
        assert fwd._buffer == []

    def test_nothing_queued_when_discard_unavailable(self):
        # Fail-safe: discard never fetched → don't forward.
        fwd = _make_forwarder(discard=None)
        fwd._active = True
        fwd.observe(_event("FSDJump"), _session())
        assert fwd._buffer == []

    def test_events_kept_in_journal_order(self):
        fwd = _make_forwarder(discard=set())
        fwd.observe(_event("FSDJump", StarSystem="A"), _session())
        fwd.observe(_event("Scan", BodyName="A 1"), _session())
        fwd.observe(_event("Docked", StationName="X"), _session())
        assert [e["event"] for e in fwd._buffer] == ["FSDJump", "Scan", "Docked"]

    def test_transient_state_hints_added(self):
        fwd = _make_forwarder(discard=set())
        state = _session(star_system="Sol", star_pos=[1.0, 2.0, 3.0], system_address=42)
        fwd.observe(_event("Scan", BodyName="Sol 1"), state)
        entry = fwd._buffer[0]
        assert entry["_systemName"] == "Sol"
        assert entry["_systemCoordinates"] == [1.0, 2.0, 3.0]
        assert entry["_systemAddress"] == 42

    def test_does_not_mutate_original_event(self):
        """EDDN path isolation: enriching the EDSM copy must not touch the raw event."""
        fwd = _make_forwarder(discard=set())
        event = _event("Scan", BodyName="Sol 1")
        fwd.observe(event, _session(star_system="Sol"))
        assert "_systemName" not in event.raw


class TestFlushLifecycle:
    @pytest.mark.asyncio
    async def test_flush_on_size_threshold(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=3)
        for i in range(3):
            fwd.observe(_event("FSDJump", StarSystem=f"S{i}"), _session())
        assert await _settle(lambda: client.post_journal.call_count == 1)
        assert fwd._buffer == []

    @pytest.mark.asyncio
    async def test_no_flush_below_threshold(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=5)
        fwd.observe(_event("FSDJump"), _session())
        await asyncio.sleep(0)
        client.post_journal.assert_not_called()
        assert len(fwd._buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_on_time_threshold(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, flush_interval=0.01)
        fwd.observe(_event("FSDJump"), _session())
        fwd._start_timer()
        assert await _settle(lambda: client.post_journal.call_count >= 1)
        fwd._cancel_tasks()

    @pytest.mark.asyncio
    async def test_manual_flush_posts_batch(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump", StarSystem="Sol"), _session())
        await fwd.flush()
        assert client.post_journal.call_count == 1
        _, kwargs = client.post_journal.call_args
        assert kwargs["commander_name"] == "CmdrTest"
        assert kwargs["api_key"] == "key-123"
        assert kwargs["messages"][0]["event"] == "FSDJump"

    def test_forced_flush_on_session_stop(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump"), _session())
        fwd.on_session_stop()
        assert client.post_journal.call_count == 1
        assert fwd._buffer == []

    def test_empty_flush_is_noop(self):
        client = MagicMock()
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.on_session_stop()
        client.post_journal.assert_not_called()


class TestStatsAndRetry:
    @pytest.mark.asyncio
    async def test_success_updates_stats(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        stats = fwd.get_stats()
        assert stats["success_count"] == 1
        assert stats["fail_count"] == 0
        assert stats["last_msgnum"] == 100

    def test_stats_reported_under_name(self):
        fwd = _make_forwarder(discard=set())
        assert fwd.name == "edsm"
        assert fwd.reports_upload_stats is True
        assert "success_count" in fwd.get_stats()

    @pytest.mark.asyncio
    async def test_fatal_msgnum_not_retried(self):
        client = MagicMock()
        client.post_journal.return_value = _fatal(203)
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        stats = fwd.get_stats()
        assert stats["fail_count"] == 1
        assert stats["last_msgnum"] == 203
        assert fwd._buffer == []  # dropped, not retried

    @pytest.mark.asyncio
    @pytest.mark.parametrize("code", [201, 202, 203, 205, 208])
    async def test_all_fatal_codes_drop(self, code):
        client = MagicMock()
        client.post_journal.return_value = _fatal(code)
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        assert fwd._buffer == []
        assert fwd.get_stats()["last_msgnum"] == code

    @pytest.mark.asyncio
    async def test_transient_retained_not_counted(self):
        """Transient events are retained for retry and NOT counted until terminal."""
        client = MagicMock()
        client.post_journal.return_value = _transient()
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump", StarSystem="Sol"), _session())
        await fwd.flush()
        assert len(fwd._buffer) == 1  # retained
        assert fwd.get_stats()["fail_count"] == 0  # not counted (will retry)
        assert fwd.get_stats()["success_count"] == 0

    @pytest.mark.asyncio
    async def test_reset_on_session_start(self):
        client = MagicMock()
        client.fetch_discard.return_value = {"Music"}
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        assert fwd.get_stats()["success_count"] == 1

        fwd.on_session_start()
        await asyncio.sleep(0)  # let discard fetch task run
        stats = fwd.get_stats()
        assert stats["success_count"] == 0
        assert stats["fail_count"] == 0
        assert stats["last_msgnum"] is None
        fwd._cancel_tasks()

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self):
        """EDSM failure is isolated — flush must not propagate exceptions."""
        client = MagicMock()
        client.post_journal.side_effect = RuntimeError("network melted")
        fwd = _make_forwarder(discard=set(), client=client)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()  # should swallow
        assert fwd.get_stats()["fail_count"] == 1


class TestPerEventCountingAndActivity:
    @pytest.mark.asyncio
    async def test_success_counts_per_event(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        for i in range(3):
            fwd.observe(_event("FSDJump", StarSystem=f"S{i}"), _session())
        await fwd.flush()
        assert fwd.get_stats()["success_count"] == 3  # per event, not per batch

    @pytest.mark.asyncio
    async def test_fatal_counts_per_event(self):
        client = MagicMock()
        client.post_journal.return_value = _fatal(203)
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        for i in range(3):
            fwd.observe(_event("Scan", BodyName=f"B{i}"), _session())
        await fwd.flush()
        assert fwd.get_stats()["fail_count"] == 3

    @pytest.mark.asyncio
    async def test_terminal_success_records_activity_per_event(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        activity = FakeActivityLog()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, activity_log=activity)
        fwd.observe(_event("FSDJump"), _session())
        fwd.observe(_event("Scan"), _session())
        await fwd.flush()
        await asyncio.sleep(0)  # drain scheduled activity-log tasks
        assert len(activity.entries) == 2
        assert all(e["target"] == "edsm" and e["outcome"] == "success" for e in activity.entries)
        assert {e["event_type"] for e in activity.entries} == {"FSDJump", "Scan"}

    @pytest.mark.asyncio
    async def test_fatal_records_failure_activity_with_msgnum(self):
        client = MagicMock()
        client.post_journal.return_value = _fatal(203)
        activity = FakeActivityLog()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, activity_log=activity)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        await asyncio.sleep(0)
        assert len(activity.entries) == 1
        entry = activity.entries[0]
        assert entry["outcome"] == "failure"
        assert entry["target"] == "edsm"
        assert entry["error_type"] == "edsm"
        assert "203" in entry["error_message"]

    @pytest.mark.asyncio
    async def test_transient_records_no_activity(self):
        client = MagicMock()
        client.post_journal.return_value = _transient()
        activity = FakeActivityLog()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, activity_log=activity)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        await asyncio.sleep(0)
        assert activity.entries == []


class TestDiscardFetch:
    @pytest.mark.asyncio
    async def test_discard_fetched_and_cached_on_start(self):
        client = MagicMock()
        client.fetch_discard.return_value = {"Music", "Market"}
        settings = MockSettings(initial_data={"edsm_api_key": "k", "edsm_commander_name": "C"})
        fwd = EdsmForwarder(settings, client=client)
        fwd.on_session_start()
        assert await _settle(lambda: fwd._discard is not None)
        assert fwd._discard == {"Music", "Market"}
        fwd._cancel_tasks()

    @pytest.mark.asyncio
    async def test_discard_failure_fails_safe(self):
        client = MagicMock()
        client.fetch_discard.return_value = None  # never succeeds
        settings = MockSettings(initial_data={"edsm_api_key": "k", "edsm_commander_name": "C"})
        fwd = EdsmForwarder(settings, client=client, discard_retry_interval=0.01)
        fwd.on_session_start()
        await asyncio.sleep(0.03)
        assert fwd._discard is None
        # observe must not queue while discard unavailable
        fwd.observe(_event("FSDJump"), _session())
        assert fwd._buffer == []
        fwd._cancel_tasks()


class TestBufferCap:
    def test_observe_caps_buffer_to_max(self):
        # flush_size high enough that no auto-flush fires while we observe.
        fwd = _make_forwarder(discard=set(), flush_size=100, max_buffer=5)
        for i in range(10):
            fwd.observe(_event("FSDJump", StarSystem=f"S{i}"), _session())
        assert len(fwd._buffer) <= 5
        # Newest events kept, oldest dropped.
        assert [e["StarSystem"] for e in fwd._buffer] == [f"S{i}" for i in range(5, 10)]

    @pytest.mark.asyncio
    async def test_transient_requeue_stays_capped(self):
        client = MagicMock()
        client.post_journal.return_value = _transient()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, max_buffer=5)
        for i in range(5):
            fwd.observe(_event("FSDJump", StarSystem=f"S{i}"), _session())
        # Add more while the (transient) batch is out, then flush re-queues.
        for i in range(5, 8):
            fwd.observe(_event("FSDJump", StarSystem=f"S{i}"), _session())
        await fwd.flush()
        assert len(fwd._buffer) <= 5


class TestRateLimitGate:
    @pytest.mark.asyncio
    async def test_backoff_gates_concurrent_flush(self):
        client = MagicMock()
        client.post_journal.return_value = EdsmResponse(
            msgnum=100, msg="OK", ok=True,
            rate_limit_remaining=0, rate_limit_reset=int(time.time() + 1000),
        )
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump", StarSystem="Sol"), _session())
        await fwd.flush()
        assert client.post_journal.call_count == 1  # posted once, backoff set

        # A concurrently-scheduled flush must not post during the window.
        fwd.observe(_event("FSDJump", StarSystem="Sol2"), _session())
        await fwd.flush()
        assert client.post_journal.call_count == 1  # still gated
        assert len(fwd._buffer) == 1  # new event stays buffered


class TestBlockingCallsOffTheLoop:
    """The plugin has one event loop; a stalling EDSM endpoint must not hold it
    for the client's full 20s timeout."""

    @staticmethod
    def _thread_recording_client(**returns):
        client = MagicMock()
        threads = []

        def record(value):
            def call(*_args, **_kwargs):
                threads.append(threading.get_ident())
                return value
            return call

        for attr, value in returns.items():
            getattr(client, attr).side_effect = record(value)
        return client, threads

    @pytest.mark.asyncio
    async def test_post_runs_off_the_loop_thread(self):
        client, threads = self._thread_recording_client(post_journal=_ok())
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        assert threads == [threads[0]] and threads[0] != threading.get_ident()
        assert fwd.get_stats()["success_count"] == 1  # response still applied

    @pytest.mark.asyncio
    async def test_discard_fetch_runs_off_the_loop_thread(self):
        client, threads = self._thread_recording_client(fetch_discard={"Music"})
        settings = MockSettings(initial_data={"edsm_api_key": "k", "edsm_commander_name": "C"})
        fwd = EdsmForwarder(settings, client=client)
        fwd.on_session_start()
        assert await _settle(lambda: fwd._discard is not None)
        fwd._cancel_tasks()
        assert threads[0] != threading.get_ident()

    @pytest.mark.asyncio
    async def test_forced_flush_on_stop_is_offloaded_and_still_posts(self):
        """on_session_stop is called from a coroutine on the loop: it cannot
        await, but it must neither block nor lose the final batch."""
        client, threads = self._thread_recording_client(post_journal=_ok())
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump"), _session())
        fwd.on_session_stop()
        assert await _settle(lambda: client.post_journal.call_count == 1)
        assert threads[0] != threading.get_ident()
        assert fwd._buffer == []


class TestServerMessageBounds:
    @pytest.mark.asyncio
    async def test_huge_server_msg_truncated_in_stats(self):
        """`last_msg` is server-supplied text pushed to the frontend."""
        from src.modules.constants import MAX_SERVER_MESSAGE_CHARS

        client = MagicMock()
        client.post_journal.return_value = EdsmResponse(msgnum=203, msg="M" * 100_000, fatal=True)
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        assert len(fwd.get_stats()["last_msg"]) == MAX_SERVER_MESSAGE_CHARS


class TestDiscardLoopResilience:
    @pytest.mark.asyncio
    async def test_bad_response_retries_instead_of_killing_the_loop(self):
        """If the discard task dies, `_discard` stays None and every event is
        dropped for the rest of the session, with no retry and no signal."""
        client = MagicMock()
        client.fetch_discard.side_effect = [
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
            {"Music"},
        ]
        client.post_journal.return_value = _ok()
        settings = MockSettings(initial_data={
            "edsm_api_key": "k", "edsm_commander_name": "C", "software_version": "0.4.0",
        })
        fwd = EdsmForwarder(settings, client=client, flush_size=100, discard_retry_interval=0.01)
        fwd.on_session_start()

        assert await _settle(lambda: fwd._discard == {"Music"})
        fwd._cancel_tasks()

        # Forwarding resumes once the discard list finally arrives.
        fwd.observe(_event("FSDJump"), _session())
        await fwd.flush()
        assert client.post_journal.call_count == 1
        assert fwd.get_stats()["success_count"] == 1


class TestUnloadDrain:
    """`on_session_stop()` can only schedule the final POST; plugin unload is
    about to take the loop away, so it has to await it."""

    @pytest.mark.asyncio
    async def test_drain_sends_the_batch_taken_by_session_stop(self):
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100)
        fwd.observe(_event("FSDJump", StarSystem="Sol"), _session())
        fwd.on_session_stop()
        client.post_journal.assert_not_called()  # scheduled only

        await fwd.drain()

        assert client.post_journal.call_count == 1
        assert client.post_journal.call_args.kwargs["messages"][0]["StarSystem"] == "Sol"
        assert fwd.get_stats()["success_count"] == 1

    @pytest.mark.asyncio
    async def test_drain_also_awaits_tasks_the_drain_itself_schedules(self):
        """The final flush schedules one activity record per event *while* it is
        being drained, and recording suspends (the real log awaits an emit), so
        draining the tasks that exist when drain() is entered is not enough."""
        class SuspendingActivityLog(FakeActivityLog):
            async def record_success(self, event_type, target="eddn"):
                await asyncio.sleep(0.01)
                await super().record_success(event_type, target=target)

        activity = SuspendingActivityLog()
        client = MagicMock()
        client.post_journal.return_value = _ok()
        fwd = _make_forwarder(discard=set(), client=client, flush_size=100, activity_log=activity)
        fwd.observe(_event("FSDJump"), _session())
        fwd.on_session_stop()

        await fwd.drain()

        assert [e["outcome"] for e in activity.entries] == ["success"]
        assert fwd._flush_tasks == set()

    @pytest.mark.asyncio
    async def test_unload_flushes_buffered_events(self, tmp_path, monkeypatch):
        """The B1 path: Decky tears the plugin down while ED is still running."""
        from unittest.mock import AsyncMock, patch

        from main import Plugin

        for var in ("DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR", "DECKY_PLUGIN_LOG_DIR"):
            monkeypatch.setenv(var, str(tmp_path))
        plugin = Plugin()
        with patch("decky.emit", new_callable=AsyncMock):
            await plugin._main()
        await plugin.settings.set("edsm_api_key", "key-123")
        client = MagicMock()
        client.post_journal.return_value = _ok()
        plugin.edsm._client = client
        plugin.edsm._discard = set()
        plugin.edsm._active = True
        plugin.edsm.observe(_event("FSDJump", StarSystem="Sol"), _session())
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = True
        plugin.watcher.stop = AsyncMock()

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin._unload()

        assert client.post_journal.call_count == 1
        assert client.post_journal.call_args.kwargs["messages"][0]["StarSystem"] == "Sol"


class TestFlushSerialisation:
    """The POST is offloaded to a worker thread, so two flushes could otherwise
    be in flight at once — reordering batches on the wire and slipping past a
    backoff window opened by the batch still in flight."""

    @staticmethod
    def _probe_client(response, post_seconds=0.05):
        """A client that logs a start/end pair around each (slow) POST."""
        client = MagicMock()
        log = []

        def post(**kwargs):
            systems = tuple(m["StarSystem"] for m in kwargs["messages"])
            log.append(("start", systems))
            time.sleep(post_seconds)
            log.append(("end", systems))
            return response

        client.post_journal.side_effect = post
        return client, log

    @pytest.mark.asyncio
    async def test_second_flush_waits_for_the_first_and_keeps_journal_order(self):
        client, log = self._probe_client(_ok())
        fwd = _make_forwarder(discard=set(), client=client, flush_size=2)

        fwd.observe(_event("FSDJump", StarSystem="A1"), _session())
        fwd.observe(_event("FSDJump", StarSystem="A2"), _session())
        assert await _settle(lambda: log and log[0][0] == "start")
        # Batch A is on the wire; batch B reaches the size threshold now.
        fwd.observe(_event("FSDJump", StarSystem="B1"), _session())
        fwd.observe(_event("FSDJump", StarSystem="B2"), _session())

        assert await _settle(lambda: len(log) == 4, timeout=5)
        await fwd.drain()
        assert log == [
            ("start", ("A1", "A2")), ("end", ("A1", "A2")),
            ("start", ("B1", "B2")), ("end", ("B1", "B2")),
        ]

    @pytest.mark.asyncio
    async def test_flush_in_flight_gates_the_next_flush_on_its_backoff(self):
        client, log = self._probe_client(EdsmResponse(
            msgnum=100, msg="OK", ok=True,
            rate_limit_remaining=0, rate_limit_reset=int(time.time() + 1000),
        ))
        fwd = _make_forwarder(discard=set(), client=client, flush_size=2)

        fwd.observe(_event("FSDJump", StarSystem="A1"), _session())
        fwd.observe(_event("FSDJump", StarSystem="A2"), _session())
        assert await _settle(lambda: log and log[0][0] == "start")
        fwd.observe(_event("FSDJump", StarSystem="B1"), _session())
        fwd.observe(_event("FSDJump", StarSystem="B2"), _session())

        await fwd.drain()

        assert client.post_journal.call_count == 1  # B never POSTed through the 429
        assert [e["StarSystem"] for e in fwd._buffer] == ["B1", "B2"]  # still buffered

    @pytest.mark.asyncio
    async def test_final_flush_does_not_overtake_a_flush_in_flight(self):
        client, log = self._probe_client(_ok())
        fwd = _make_forwarder(discard=set(), client=client, flush_size=2)

        fwd.observe(_event("FSDJump", StarSystem="A1"), _session())
        fwd.observe(_event("FSDJump", StarSystem="A2"), _session())
        assert await _settle(lambda: log and log[0][0] == "start")
        fwd.observe(_event("FSDJump", StarSystem="Z1"), _session())
        fwd.on_session_stop()

        await fwd.drain()

        assert log == [
            ("start", ("A1", "A2")), ("end", ("A1", "A2")),
            ("start", ("Z1",)), ("end", ("Z1",)),
        ]
