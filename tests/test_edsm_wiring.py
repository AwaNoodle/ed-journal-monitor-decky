"""
Tests that main.Plugin registers the EDSM forwarder in the watcher's consumer
list and drives its lifecycle hooks alongside the session accumulator.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import Plugin
from src.modules.forwarders.edsm import EdsmForwarder
from src.modules.session_stats import SessionStatsAccumulator


@pytest.fixture(autouse=True)
def _isolate_decky_dirs(tmp_path, monkeypatch):
    for var in ("DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR", "DECKY_PLUGIN_LOG_DIR"):
        monkeypatch.setenv(var, str(tmp_path))


@pytest.mark.asyncio
async def test_main_registers_edsm_consumer():
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    # EDSM forwarder and session accumulator both registered.
    assert any(isinstance(c, EdsmForwarder) for c in plugin.consumers)
    assert any(isinstance(c, SessionStatsAccumulator) for c in plugin.consumers)
    # The watcher fans out to the same consumer list.
    assert plugin.watcher._consumers is plugin.consumers
    assert plugin.edsm in plugin.watcher._consumers
    # EDSM records activity into the shared activity log.
    assert plugin.edsm._activity_log is plugin.activity_log


@pytest.mark.asyncio
async def test_lifecycle_reaches_edsm_on_start():
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    plugin.edsm.on_session_start = MagicMock()
    plugin.submitter = MagicMock()
    plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

    with patch("decky.emit", new_callable=AsyncMock):
        await plugin.set_ed_running(True)

    plugin.edsm.on_session_start.assert_called_once()


@pytest.mark.asyncio
async def test_lifecycle_reaches_edsm_on_stop():
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    plugin.edsm.on_session_stop = MagicMock()
    plugin.watcher = MagicMock()
    plugin.watcher.is_running = True
    plugin.watcher.stop = AsyncMock()

    await plugin.stop_watcher()

    plugin.edsm.on_session_stop.assert_called_once()
