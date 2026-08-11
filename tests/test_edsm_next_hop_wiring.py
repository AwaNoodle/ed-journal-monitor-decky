"""
Tests that main.Plugin wires the next-hop consumer into the stream, shares the
EDSM read client + cache with the lookup consumer, exposes the next-hop preview
in get_status(), and clears it on toggle-off / ED stop.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from main import Plugin
from src.modules.edsm_lookup_consumer import EdsmLookupConsumer
from src.modules.edsm_next_hop_consumer import EdsmNextHopConsumer


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
async def test_registers_next_hop_consumer_sharing_client_and_cache():
    plugin = await _make_plugin()

    assert any(isinstance(c, EdsmNextHopConsumer) for c in plugin.consumers)
    assert plugin.edsm_next_hop in plugin.watcher._consumers
    # Shares the same read client + cache instance as the lookup consumer.
    lookup = next(c for c in plugin.consumers if isinstance(c, EdsmLookupConsumer))
    assert plugin.edsm_next_hop._client is lookup._client
    assert plugin.edsm_next_hop._cache is lookup._cache


@pytest.mark.asyncio
async def test_get_status_exposes_next_hop():
    plugin = await _make_plugin()

    status = await plugin.get_status()
    assert "edsm_next_hop" in status
    assert status["edsm_next_hop"] is None  # neutral until a preview arrives

    payload = {"system": "Alpha Centauri", "scoopable": True, "starClass": "B",
               "verdict": "green", "source": "edsm", "totalValue": None, "priorityBodies": []}
    plugin._on_edsm_next_hop(payload)
    status = await plugin.get_status()
    assert status["edsm_next_hop"] == payload


@pytest.mark.asyncio
async def test_callback_stores_payload_unchanged():
    """`_on_edsm_next_hop` stores whatever it's given, including a neutral
    payload — so its `reason` discriminator survives get_status rehydration."""
    plugin = await _make_plugin()
    plugin._on_edsm_next_hop({"system": "Sol", "scoopable": True})
    assert plugin._edsm_next_hop == {"system": "Sol", "scoopable": True}

    from src.modules.edsm_next_hop_consumer import neutral_next_hop
    neutral = neutral_next_hop("final_hop")
    plugin._on_edsm_next_hop(neutral)
    assert plugin._edsm_next_hop == neutral
    assert plugin._edsm_next_hop["reason"] == "final_hop"


@pytest.mark.asyncio
async def test_get_status_rehydration_preserves_reason():
    plugin = await _make_plugin()
    from src.modules.edsm_next_hop_consumer import neutral_next_hop
    plugin._on_edsm_next_hop(neutral_next_hop("off_route"))

    status = await plugin.get_status()
    assert status["edsm_next_hop"]["reason"] == "off_route"
    assert status["edsm_next_hop"]["system"] is None


@pytest.mark.asyncio
async def test_toggle_off_clears_and_emits_neutral_next_hop():
    plugin = await _make_plugin()
    plugin._edsm_next_hop = {"system": "Sol"}

    with patch("decky.emit", new_callable=AsyncMock) as mock_emit:
        await plugin.set_edsm_lookups_enabled(False)

    assert plugin._edsm_next_hop["system"] is None
    assert plugin._edsm_next_hop["reason"] == "disabled"
    events = [c.args[0] for c in mock_emit.call_args_list]
    assert "edsm_next_hop" in events


@pytest.mark.asyncio
async def test_ed_stop_clears_and_emits_neutral_next_hop():
    plugin = await _make_plugin()
    plugin.ed_running = True
    plugin._edsm_next_hop = {"system": "Sol"}

    with patch("decky.emit", new_callable=AsyncMock) as mock_emit:
        await plugin.set_ed_running(False)

    assert plugin._edsm_next_hop["system"] is None
    assert plugin._edsm_next_hop["reason"] == "disabled"
    events = [c.args[0] for c in mock_emit.call_args_list]
    assert "edsm_next_hop" in events


@pytest.mark.asyncio
async def test_toggle_on_reevaluates_next_hop():
    plugin = await _make_plugin()
    with patch.object(plugin.edsm_next_hop, "reevaluate") as mock_reeval:
        await plugin.set_edsm_lookups_enabled(True)
    mock_reeval.assert_called_once()
