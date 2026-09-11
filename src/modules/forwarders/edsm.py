from __future__ import annotations

"""
EDSM forwarder — a StreamConsumer that taps the raw parsed-event stream and
forwards journal lines verbatim to EDSM's api-journal-v1 under the commander's
own credentials.

It is independent of, and isolated from, the EDDN submission path:
  - it observes the same stream as EDDN, before the EDDN reportable filter;
  - it never mutates the shared event, blocks, or depends on EDDN routing;
  - its failures never touch EDDN stats and vice-versa.

Behavior: API-key presence is the consent gate (off by default); Legacy game
versions are not forwarded; events on EDSM's discard list are dropped; accepted
events are buffered in journal order and flushed on a size or time threshold and
forced-flushed on session stop. Flushes are serialised, so batches reach EDSM in
journal order even though each POST runs off the loop; a caller about to lose the
loop (plugin unload) awaits ``drain()``. Responses are classified by ``msgnum``
(1xx OK · 2xx fatal/no-retry · 5xx transient/retry).
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable

import decky
from src.modules import constants
from src.modules.forwarders.edsm_client import EdsmClient, EdsmResponse, rate_limit_wait_seconds
from src.modules.ssl_context import build_ssl_context

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from src.modules.activity_log import ActivityLog
    from src.modules.parser import ParsedEvent, SessionState
    from src.modules.settings import PluginSettings

DEFAULT_FLUSH_SIZE = 20
DEFAULT_FLUSH_INTERVAL = 30  # seconds
DEFAULT_MAX_BUFFER = 500
DEFAULT_DISCARD_RETRY = 10  # seconds
MAX_DISCARD_RETRY = 300  # seconds
# Live game versions are major >= 4; Legacy (major < 4) is not forwarded.
LIVE_MAJOR_VERSION = 4


class EdsmForwarder:
    """Forwards raw journal events to EDSM. Satisfies the StreamConsumer protocol."""

    name = "edsm"
    reports_upload_stats = True

    def __init__(
        self,
        settings: PluginSettings,
        client: EdsmClient | None = None,
        flush_size: int = DEFAULT_FLUSH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        max_buffer: int = DEFAULT_MAX_BUFFER,
        discard_retry_interval: float = DEFAULT_DISCARD_RETRY,
        on_stats_change: Callable[[], None] | None = None,
        activity_log: ActivityLog | None = None,
    ) -> None:
        self.settings = settings
        version = str(settings.get("software_version", constants.SOFTWARE_VERSION))
        self._client = client or EdsmClient(
            ssl_context=build_ssl_context(),
            user_agent=f"ed-journal-monitor-decky/{version}",
        )
        self._flush_size = flush_size
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._discard_retry_interval = discard_retry_interval
        self._on_stats_change = on_stats_change
        self._activity_log = activity_log

        self._buffer: list[dict] = []
        self._rate_limited_until: float = 0.0
        self._discard: set[str] | None = None
        self._active: bool = False
        self._game_version: str = ""
        self._game_build: str = ""

        self._success_count: int = 0
        self._fail_count: int = 0
        self._last_msgnum: int | None = None
        self._last_msg: str | None = None

        self._timer_task: asyncio.Task | None = None
        self._discard_task: asyncio.Task | None = None
        self._flush_tasks: set[asyncio.Task] = set()
        # Serialises the send path (see `flush`).
        self._flush_lock = asyncio.Lock()

    # --- StreamConsumer protocol ---

    def observe(self, event: ParsedEvent, session_state: SessionState | None = None) -> None:
        """Queue an accepted event for forwarding. Never raises."""
        try:
            if not self._api_key():
                return
            if not self._active or self._discard is None:
                # Inactive, or discard list not yet available → fail safe.
                return
            if session_state is not None:
                if not self._is_live(session_state.game_version):
                    return
                self._game_version = session_state.game_version
                self._game_build = session_state.game_build
            if event.event_type in self._discard:
                return

            self._buffer.append(self._enrich(event, session_state))
            # Bound the buffer so a sustained EDSM outage can't grow it without
            # limit; keep the newest events (EDSM dedupes server-side, so
            # dropping stale oldest events on overflow is safe).
            if len(self._buffer) > self._max_buffer:
                self._buffer = self._buffer[-self._max_buffer:]
            if len(self._buffer) >= self._flush_size:
                self._schedule_flush()
        except Exception as e:
            decky.logger.error(f"EDSM observe error on {event.event_type}: {e}")

    def on_session_start(self) -> None:
        """New launch: reset stats, clear buffer, (re)fetch discard list, start timer."""
        self._buffer = []
        self._rate_limited_until = 0.0
        self._success_count = 0
        self._fail_count = 0
        self._last_msgnum = None
        self._last_msg = None
        self._discard = None
        self._active = bool(self._api_key())
        self._cancel_tasks()
        if self._active:
            self._start_discard_fetch()
            self._start_timer()

    def disarm(self) -> None:
        """Withdraw consent mid-session: stop forwarding and drop what is buffered.

        Unlike `on_session_start()` (which re-reads the key and rebuilds the
        session) this leaves the panel's counters and the cached discard list
        alone — clearing an API key is not a new session, so the session's
        success/failure totals must survive it. Batches already on the wire are
        left to settle: cancelling them would abandon a POST that the worker
        thread is going to make anyway, uncounted and unlogged.
        """
        self._active = False
        self._buffer = []
        self._cancel_tasks()

    def on_session_stop(self) -> None:
        """Watcher stopped: stop timers and force a final flush.

        This hook is synchronous but is called from a coroutine on the plugin's
        only event loop, so it cannot await and must not block: the final POST
        is scheduled as a tracked task that offloads the blocking request to a
        worker thread. Callers about to lose the loop (plugin unload) must
        `await drain()` afterwards. Without a running loop (nothing to freeze,
        nothing to schedule on) the POST is made inline instead.
        """
        self._active = False
        self._cancel_tasks()
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        if not self._track(self._final_flush(batch)):
            self._post_batch(batch)

    async def drain(self) -> None:
        """Await every in-flight flush and activity-log task.

        Plugin unload is the one path that takes the event loop away, so a
        scheduled final flush would die unsent there. Re-checked in a loop
        because a drained flush schedules activity-log tasks of its own. Never
        holds `_flush_lock`, so it cannot deadlock against the flush it awaits.
        """
        while self._flush_tasks:
            await asyncio.gather(*self._flush_tasks, return_exceptions=True)

    def get_stats(self) -> dict:
        """Snapshot of this target's stats for per-target aggregation."""
        return {
            "success_count": self._success_count,
            "fail_count": self._fail_count,
            "last_msgnum": self._last_msgnum,
            "last_msg": self._last_msg,
            "active": self._active,
            "queued": len(self._buffer),
        }

    # --- flush ---

    async def flush(self) -> None:
        """Flush the buffer to EDSM. Re-queues events on transient failure.

        Serialised on `_flush_lock`, which is held across the buffer swap, the
        rate-limit gate and the send. The POST itself is offloaded to a worker
        thread, so without the lock a second flush (size threshold, timer or
        session stop) would swap the next buffer and POST concurrently: batches
        could reach EDSM out of journal order, and the gate below would be read
        before the in-flight batch had a chance to open a backoff window, so we
        would keep POSTing through a 429.
        """
        async with self._flush_lock:
            if not self._buffer:
                return
            # Gate flushes during a rate-limit backoff window: events stay
            # buffered and the timer loop retries once the window elapses.
            if time.monotonic() < self._rate_limited_until:
                return
            batch, self._buffer = self._buffer, []
            response = await self._post_batch_async(batch)
            if response is not None:
                wait = rate_limit_wait_seconds(response)
                if wait > 0:
                    decky.logger.info(f"EDSM rate limit reached, backing off {wait:.0f}s")
                    self._rate_limited_until = time.monotonic() + wait

    async def _final_flush(self, batch: list[dict]) -> None:
        """POST the batch `on_session_stop()` took, behind the same lock as
        `flush()` so the final batch cannot overtake a flush already on the wire."""
        async with self._flush_lock:
            await self._post_batch_async(batch)

    async def _post_batch_async(self, batch: list[dict]) -> EdsmResponse | None:
        """POST one batch off the event loop and apply the response on it.

        The client is blocking stdlib ``urllib`` with a 20s timeout; running it
        inline would freeze journal watching, EDDN submission and Decky RPC for
        the whole call. Only the request is offloaded — the response is applied
        on the loop, where the activity-log tasks it schedules belong.
        """
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, self._post_journal, batch)
        except Exception as e:
            self._record_post_error(e, batch)
            return None

        self._handle_response(response, batch)
        return response

    def _post_batch(self, batch: list[dict]) -> EdsmResponse | None:
        """POST one batch inline, blocking the caller. Never raises.

        Only used when there is no running loop to offload to.
        """
        try:
            response = self._post_journal(batch)
        except Exception as e:
            self._record_post_error(e, batch)
            return None

        self._handle_response(response, batch)
        return response

    def _post_journal(self, batch: list[dict]) -> EdsmResponse:
        """The blocking request itself — the only part run off the loop."""
        return self._client.post_journal(
            commander_name=str(self.settings.get("edsm_commander_name", "")),
            api_key=self._api_key(),
            software=constants.SOFTWARE_NAME,
            software_version=str(self.settings.get("software_version", constants.SOFTWARE_VERSION)),
            game_version=self._game_version,
            game_build=self._game_build,
            messages=batch,
        )

    def _record_post_error(self, error: Exception, batch: list[dict]) -> None:
        decky.logger.error(f"EDSM POST error: {error}")
        self._fail_count += len(batch)
        self._last_msg = str(error)[:constants.MAX_SERVER_MESSAGE_CHARS]
        self._notify_stats()

    def _handle_response(self, response: EdsmResponse, batch: list[dict]) -> None:
        self._last_msgnum = response.msgnum
        # Bound server-supplied text: `_last_msg` is surfaced to the frontend.
        self._last_msg = response.msg[:constants.MAX_SERVER_MESSAGE_CHARS] or self._last_msg
        if response.ok:
            # Terminal success: count and record one activity entry per event.
            self._success_count += len(batch)
            for event in batch:
                self._record_success(event.get("event", "unknown"))
        elif response.transient:
            # Keep events for resend (prepend to preserve journal order); not
            # counted or recorded until the batch settles with a terminal result.
            # Bound the re-queued buffer, keeping the newest events (EDSM dedupes
            # server-side, so dropping stale oldest events on overflow is safe).
            self._buffer = (batch + self._buffer)[-self._max_buffer:]
        else:
            # Fatal / unrecoverable (bad creds, blacklisted, Legacy) — drop.
            self._fail_count += len(batch)
            message = self._format_error(response)
            for event in batch:
                self._record_failure(event.get("event", "unknown"), message)
            decky.logger.warning(f"EDSM fatal response {response.msgnum}: {response.msg}")
        self._notify_stats()

    @staticmethod
    def _format_error(response: EdsmResponse) -> str:
        if response.msgnum is not None:
            return f"[{response.msgnum}] {response.msg}"
        return response.msg or "EDSM error"

    def _record_success(self, event_type: str) -> None:
        if self._activity_log is not None:
            self._track(self._activity_log.record_success(event_type, target=constants.TARGET_EDSM))

    def _record_failure(self, event_type: str, message: str) -> None:
        if self._activity_log is not None:
            self._track(
                self._activity_log.record_failure(
                    event_type, constants.TARGET_EDSM, message, target=constants.TARGET_EDSM,
                )
            )

    def _track(self, coro: Coroutine[Any, Any, Any]) -> bool:
        """Schedule a coroutine as a tracked task so `drain()` can await it.

        Used for the send path and for fire-and-forget activity-log records
        (recording must not block or gate a flush). Returns False, having
        discarded the coroutine, when there is no running loop to schedule on.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return False
        task = loop.create_task(coro)
        self._flush_tasks.add(task)
        task.add_done_callback(self._flush_tasks.discard)
        return True

    # --- background tasks ---

    def _start_timer(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._timer_task = loop.create_task(self._timer_loop())

    async def _timer_loop(self) -> None:
        try:
            while self._active:
                await asyncio.sleep(self._flush_interval)
                await self.flush()
        except asyncio.CancelledError:
            pass

    def _start_discard_fetch(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._discard_task = loop.create_task(self._discard_loop())

    async def _discard_loop(self) -> None:
        backoff = self._discard_retry_interval
        loop = asyncio.get_running_loop()
        try:
            while self._active and self._discard is None:
                try:
                    # Blocking stdlib GET — keep it off the loop.
                    result = await loop.run_in_executor(None, self._client.fetch_discard)
                    if result is not None:
                        self._discard = result
                        decky.logger.info(f"EDSM discard list cached ({len(result)} events)")
                        return
                    decky.logger.warning("EDSM discard list unavailable; EDSM idle until fetched")
                except Exception as e:
                    # A bad response must not kill this task: without it
                    # `_discard` stays None and every event is dropped for the
                    # rest of the session. CancelledError is a BaseException,
                    # so cancellation still unwinds to the guard below.
                    decky.logger.warning(f"EDSM discard fetch error; retrying: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_DISCARD_RETRY)
        except asyncio.CancelledError:
            pass

    def _schedule_flush(self) -> None:
        self._track(self.flush())

    def _cancel_tasks(self) -> None:
        for task in (self._timer_task, self._discard_task):
            if task is not None and not task.done():
                task.cancel()
        self._timer_task = None
        self._discard_task = None

    # --- helpers ---

    def _api_key(self) -> str:
        return str(self.settings.get("edsm_api_key", "") or "")

    def _notify_stats(self) -> None:
        if self._on_stats_change is not None:
            try:
                self._on_stats_change()
            except Exception as e:
                decky.logger.error(f"EDSM stats notify error: {e}")

    @staticmethod
    def _is_live(game_version: str) -> bool:
        """Treat unknown/parseable-major>=4 as Live. Legacy (major < 4) is skipped.

        EDSM also rejects Legacy server-side with msgnum 208, so this is a
        best-effort client gate, not the sole enforcement.
        """
        if not game_version:
            return True
        try:
            return int(game_version.split(".", maxsplit=1)[0]) >= LIVE_MAJOR_VERSION
        except ValueError:
            return True

    @staticmethod
    def _enrich(event: ParsedEvent, session_state: SessionState | None) -> dict:
        """Copy the raw event and add EDSM transient-state hints (never mutates
        the original event, keeping the EDDN path untouched)."""
        entry = dict(event.raw)
        if session_state is not None:
            if session_state.star_system:
                entry.setdefault("_systemName", session_state.star_system)
            if session_state.star_pos is not None:
                entry.setdefault("_systemCoordinates", session_state.star_pos)
            if session_state.system_address is not None:
                entry.setdefault("_systemAddress", session_state.system_address)
        return entry
