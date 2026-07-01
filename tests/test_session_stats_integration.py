"""
Integration tests for session stats lifecycle wiring in main.Plugin.

Covers the launch-epoch reset (set_ed_running) running before the watcher's
initial-scan replay, and the get_session_stats callable.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.parser import JournalParser
from src.modules.session_stats import SessionStatsAccumulator
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


def make_event_line(event_type: str, **fields) -> str:
    import json
    payload = {"timestamp": "2026-01-12T12:00:00Z", "event": event_type}
    payload.update(fields)
    return json.dumps(payload)


class TestSetEdRunningResetsSessionStats:
    @pytest.mark.asyncio
    async def test_set_ed_running_true_resets_session_stats(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        plugin.session_stats = SessionStatsAccumulator()
        plugin.consumers = [plugin.session_stats]
        # Pre-populate as if a previous launch had stats.
        plugin.session_stats.stats.jumps = 7
        plugin.session_stats.stats.star_system = "Old System"

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(True)

        assert plugin.session_stats.stats.jumps == 0
        assert plugin.session_stats.stats.star_system == ""

    @pytest.mark.asyncio
    async def test_set_ed_running_false_does_not_reset_session_stats(self):
        plugin = Plugin()
        plugin.ed_running = True
        plugin.submitter = MagicMock()
        plugin.session_stats = SessionStatsAccumulator()
        plugin.session_stats.stats.jumps = 7

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(False)

        assert plugin.session_stats.stats.jumps == 7


class TestResetBeforeReplay:
    @pytest.mark.asyncio
    async def test_reset_runs_before_initial_scan_preserves_retroactive_totals(self, tmp_path):
        """The launch reset zeros stats, then the replay repopulates them with
        this launch's events — retroactive totals are preserved, not doubled."""
        settings = MockSettings(initial_data={"enabled": True, "poll_interval": 10})
        parser = JournalParser()
        accumulator = SessionStatsAccumulator()
        submitter = EDDNSubmitter(settings)
        submitter.submit = AsyncMock(return_value=True)
        watcher = JournalWatcher(
            settings=settings,
            parser=parser,
            validator=EDDNValidator(),
            submitter=submitter,
            consumers=[accumulator],
        )

        plugin = Plugin()
        plugin.submitter = submitter
        plugin.session_stats = accumulator
        plugin.consumers = [accumulator]
        plugin.watcher = watcher

        lines = [
            make_event_line("Fileheader"),
            make_event_line("LoadGame", Commander="TestCmdr", Horizons=True, Odyssey=True),
            make_event_line("FSDJump", StarSystem="Sol", SystemAddress=1, StarPos=[0, 0, 0], JumpDist=15),
            make_event_line("FSDJump", StarSystem="Wolf 359", SystemAddress=2, StarPos=[1, 2, 3], JumpDist=7.8),
        ]
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Stale state from a prior launch.
        accumulator.stats.jumps = 99

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(True)  # launch epoch reset
        assert accumulator.stats.jumps == 0  # reset happened first

        await watcher.start(str(tmp_path))  # triggers _initial_scan replay

        # Repopulated from this launch's two jumps — not 99, not 101.
        assert accumulator.stats.jumps == 2
        assert accumulator.stats.star_system == "Wolf 359"
        assert accumulator.stats.commander == "TestCmdr"


class TestGetSessionStats:
    @pytest.mark.asyncio
    async def test_get_session_stats_returns_current(self):
        plugin = Plugin()
        plugin.session_stats = SessionStatsAccumulator()
        plugin.session_stats.stats.jumps = 3
        plugin.session_stats.stats.star_system = "Sol"

        result = await plugin.get_session_stats()
        assert result["jumps"] == 3
        assert result["star_system"] == "Sol"

    @pytest.mark.asyncio
    async def test_get_session_stats_returns_zeroed_when_uninitialized(self):
        plugin = Plugin()
        result = await plugin.get_session_stats()
        assert result == {
            "commander": "",
            "star_system": "",
            "jumps": 0,
            "distance_ly": 0.0,
            "bodies_scanned": 0,
            "first_discoveries": 0,
        }


class TestSessionUpdateEmit:
    @pytest.mark.asyncio
    async def test_stats_change_emits_session_update(self):
        plugin = Plugin()
        emitted = []

        async def mock_emit(event, data):
            emitted.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            plugin.session_stats = SessionStatsAccumulator(
                on_change=plugin._on_session_stats_change,
            )
            plugin.session_stats.observe(
                type("E", (), {"event_type": "FSDJump", "raw": {"StarSystem": "Sol", "JumpDist": 10.0}})(),
            )
            # Let the scheduled emit task run.
            import asyncio
            await asyncio.sleep(0)

        session_updates = [e for e in emitted if e[0] == "session_update"]
        assert len(session_updates) == 1
        assert session_updates[0][1]["jumps"] == 1
