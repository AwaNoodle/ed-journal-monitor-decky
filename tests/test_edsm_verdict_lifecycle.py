"""Tests for verdict clearing on ED stop / lookups-disabled transitions."""

from unittest.mock import AsyncMock, patch

import pytest

from main import Plugin


@pytest.fixture(autouse=True)
def _isolate_decky_dirs(tmp_path, monkeypatch):
    for var in ("DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR", "DECKY_PLUGIN_LOG_DIR"):
        monkeypatch.setenv(var, str(tmp_path))


@pytest.mark.asyncio
async def test_edsm_verdict_cleared_on_ed_stop():
    """_edsm_verdict must be None after set_ed_running(False)."""
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    # Inject a live verdict as if a lookup had just completed
    plugin._edsm_verdict = {"system": "Sol", "verdict": "green", "source": "edsm"}
    plugin.ed_running = True

    with patch("decky.emit", new_callable=AsyncMock) as mock_emit:
        await plugin.set_ed_running(False)

    assert plugin._edsm_verdict is None
    # Also verify an edsm_worth_scanning clear was emitted
    emitted_events = [call.args[0] for call in mock_emit.call_args_list]
    assert "edsm_worth_scanning" in emitted_events


@pytest.mark.asyncio
async def test_edsm_verdict_cleared_on_lookups_disabled():
    """_edsm_verdict must be None after set_edsm_lookups_enabled(False)."""
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    plugin._edsm_verdict = {"system": "Sol", "verdict": "green", "source": "edsm"}

    with patch("decky.emit", new_callable=AsyncMock) as mock_emit:
        await plugin.set_edsm_lookups_enabled(False)

    assert plugin._edsm_verdict is None
    emitted_events = [call.args[0] for call in mock_emit.call_args_list]
    assert "edsm_worth_scanning" in emitted_events


@pytest.mark.asyncio
async def test_edsm_verdict_not_cleared_when_lookups_enabled():
    """Enabling lookups must NOT clear the existing verdict."""
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    plugin._edsm_verdict = {"system": "Sol", "verdict": "green", "source": "edsm"}

    with patch("decky.emit", new_callable=AsyncMock):
        await plugin.set_edsm_lookups_enabled(True)

    assert plugin._edsm_verdict is not None


@pytest.mark.asyncio
async def test_re_enabling_lookups_fires_lookup_for_current_system():
    """Re-enabling lookups must trigger a lookup for the system the player is in."""
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()

    from src.modules.edsm_lookup_consumer import EdsmLookupConsumer
    lookup_consumer = next(c for c in plugin.consumers if isinstance(c, EdsmLookupConsumer))
    lookup_consumer._last_system = "Sol"  # player is in Sol

    with patch("decky.emit", new_callable=AsyncMock), \
         patch.object(lookup_consumer, "_fire_lookup") as mock_fire:
        await plugin.set_edsm_lookups_enabled(True)

    mock_fire.assert_called_once_with("Sol")
    assert lookup_consumer._last_system == "Sol"
