"""Tests that main.Plugin wires the on-demand nearest-scoopable-star callable:
uses the current system tracked by the next-hop consumer, shares the same
EDSM read client as the other read features, is gated by the
edsm_lookups_enabled toggle (no request when disabled), and returns the
frontend-shaped result dict.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from main import Plugin
from src.modules.edsm_read_client import STATUS_OK as SPHERE_OK
from src.modules.edsm_read_client import SphereSystemsResult


@pytest.fixture(autouse=True)
def _isolate_decky_dirs(tmp_path, monkeypatch):
    for var in ("DECKY_PLUGIN_SETTINGS_DIR", "DECKY_PLUGIN_RUNTIME_DIR", "DECKY_PLUGIN_LOG_DIR"):
        monkeypatch.setenv(var, str(tmp_path))


async def _make_plugin() -> Plugin:
    plugin = Plugin()
    with patch("decky.emit", new_callable=AsyncMock):
        await plugin._main()
    return plugin


@pytest.mark.asyncio
async def test_disabled_toggle_returns_disabled_with_no_request():
    plugin = await _make_plugin()
    plugin.edsm_next_hop._current_system = "Sol"
    with patch.object(plugin.edsm_read_client, "get_sphere_systems") as mock_sphere:
        result = await plugin.get_nearest_scoopable_star()

    assert result["status"] == "disabled"
    mock_sphere.assert_not_called()


@pytest.mark.asyncio
async def test_uses_current_system_from_next_hop_consumer():
    plugin = await _make_plugin()
    await plugin.settings.set("edsm_lookups_enabled", True)
    plugin.edsm_next_hop._current_system = "Sol"
    with patch.object(plugin.edsm_read_client, "get_sphere_systems") as mock_sphere:
        mock_sphere.return_value = SphereSystemsResult(status=SPHERE_OK, system_name="Sol", systems=[
            {"name": "Sol", "distance": 0, "primaryStar": {"type": "G", "isScoopable": True}},
            {"name": "Barnard's Star", "distance": 5.95, "primaryStar": {"type": "M", "isScoopable": True}},
        ])
        result = await plugin.get_nearest_scoopable_star()

    mock_sphere.assert_called_once_with("Sol")
    assert result == {
        "status": "ok",
        "system": "Barnard's Star",
        "distance": 5.95,
        "star_class": "M",
    }


@pytest.mark.asyncio
async def test_no_current_system_yet_returns_unavailable_with_no_request():
    plugin = await _make_plugin()
    await plugin.settings.set("edsm_lookups_enabled", True)
    with patch.object(plugin.edsm_read_client, "get_sphere_systems") as mock_sphere:
        result = await plugin.get_nearest_scoopable_star()

    assert result["status"] == "unavailable"
    mock_sphere.assert_not_called()


@pytest.mark.asyncio
async def test_shares_read_client_with_other_edsm_consumers():
    plugin = await _make_plugin()
    assert plugin.edsm_read_client is plugin.edsm_lookup._client
    assert plugin.edsm_read_client is plugin.edsm_next_hop._client
