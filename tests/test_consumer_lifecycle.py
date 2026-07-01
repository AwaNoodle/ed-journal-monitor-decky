"""
Tests for the StreamConsumer lifecycle + stats fan-out.

Covers the protocol extension (name/get_stats/on_session_start/on_session_stop):
the watcher still fans observe() to every consumer, and main.Plugin drives the
lifecycle hooks across all registered consumers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.parser import JournalParser
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


def _make_consumer(name="fake", reports_upload_stats=True):
    consumer = MagicMock()
    consumer.name = name
    consumer.reports_upload_stats = reports_upload_stats
    consumer.get_stats.return_value = {"success_count": 0, "fail_count": 0}
    return consumer


class TestWatcherFanOut:
    @pytest.mark.asyncio
    async def test_observe_called_for_every_consumer(self, tmp_path):
        c1 = _make_consumer("c1")
        c2 = _make_consumer("c2")
        # MagicMock would satisfy suspend/resume; strip those so the watcher's
        # initial-scan coalescing doesn't try to call them.
        for c in (c1, c2):
            del c.suspend
            del c.resume

        settings = MockSettings(initial_data={"enabled": True, "poll_interval": 10})
        submitter = MagicMock()
        submitter.submit = AsyncMock(return_value=True)
        watcher = JournalWatcher(
            settings=settings,
            parser=JournalParser(),
            validator=EDDNValidator(),
            submitter=submitter,
            consumers=[c1, c2],
        )

        import json
        line = json.dumps({"timestamp": "2026-01-12T12:00:00Z", "event": "FSDJump",
                           "StarSystem": "Sol", "SystemAddress": 1, "StarPos": [0, 0, 0]})
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(line + "\n", encoding="utf-8")

        with patch("decky.emit", new_callable=AsyncMock):
            await watcher._process_file(str(journal_file))

        assert c1.observe.call_count == 1
        assert c2.observe.call_count == 1


class TestMainLifecycleFanOut:
    @pytest.mark.asyncio
    async def test_on_session_start_called_across_consumers(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        c1 = _make_consumer("c1")
        c2 = _make_consumer("c2")
        plugin.consumers = [c1, c2]

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(True)

        c1.on_session_start.assert_called_once()
        c2.on_session_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_session_stop_called_across_consumers_on_watcher_stop(self):
        plugin = Plugin()
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = True
        plugin.watcher.stop = AsyncMock()
        c1 = _make_consumer("c1")
        c2 = _make_consumer("c2")
        plugin.consumers = [c1, c2]

        await plugin.stop_watcher()

        c1.on_session_stop.assert_called_once()
        c2.on_session_stop.assert_called_once()
