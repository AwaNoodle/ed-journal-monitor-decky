"""
Tests for EDSM credential settings and the backend callables that get/set them.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.forwarders.edsm import EdsmForwarder
from src.modules.parser import ParsedEvent


class DeletableSettings(MockSettings):
    """MockSettings plus the delete() the clear-credentials path needs."""

    async def delete(self, key):
        self._data.pop(key, None)
        return True


class TestEdsmCredentialCallables:
    @pytest.mark.asyncio
    async def test_set_edsm_credentials_persists(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_credentials("CmdrTest", "api-key-123")

        assert result == {"success": True}
        assert plugin.settings.get("edsm_commander_name") == "CmdrTest"
        assert plugin.settings.get("edsm_api_key") == "api-key-123"

    @pytest.mark.asyncio
    async def test_blank_api_key_keeps_existing(self):
        """Saving with a blank API key preserves the previously saved key."""
        plugin = Plugin()
        plugin.settings = MockSettings(initial_data={"edsm_api_key": "existing-key"})

        await plugin.set_edsm_credentials("NewName", "")

        assert plugin.settings.get("edsm_commander_name") == "NewName"
        assert plugin.settings.get("edsm_api_key") == "existing-key"

    @pytest.mark.asyncio
    async def test_set_edsm_credentials_activates_when_ed_running(self):
        """Saving credentials mid-session activates EDSM without a relaunch."""
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.ed_running = True
        plugin.edsm = MagicMock()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_edsm_credentials("CmdrTest", "api-key-123")

        plugin.edsm.on_session_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_edsm_credentials_no_activation_when_ed_not_running(self):
        """When ED is not running, EDSM activates on the next session start."""
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.ed_running = False
        plugin.edsm = MagicMock()

        await plugin.set_edsm_credentials("CmdrTest", "api-key-123")

        plugin.edsm.on_session_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_edsm_credentials_removes_key(self, tmp_path, monkeypatch):
        """Clearing withdraws consent: the key is gone from settings and from disk."""
        from src.modules.settings import PluginSettings

        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path / "settings"))
        plugin = Plugin()
        plugin.settings = PluginSettings()
        await plugin.set_edsm_credentials("CmdrTest", "api-key-123")

        result = await plugin.clear_edsm_credentials()

        assert result == {"success": True}
        assert await plugin.get_edsm_credentials() == {"commander_name": "", "api_key_set": False}

        reloaded = PluginSettings()
        await reloaded.load()
        assert reloaded.get("edsm_api_key") is None
        assert reloaded.get("edsm_commander_name") is None

    @pytest.mark.asyncio
    async def test_clear_edsm_credentials_disarms_forwarder_mid_session(self):
        """Clearing mid-session re-runs the forwarder's session hook so it observes
        the now-absent key and goes inactive without a relaunch."""
        settings = DeletableSettings(initial_data={"edsm_api_key": "k", "edsm_commander_name": "C"})
        plugin = Plugin()
        plugin.settings = settings
        plugin.ed_running = True
        plugin.edsm = EdsmForwarder(settings, client=MagicMock())
        plugin.edsm.on_session_start()
        assert plugin.edsm._active is True
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.clear_edsm_credentials()

        assert plugin.edsm._active is False

    @pytest.mark.asyncio
    async def test_clear_edsm_credentials_keeps_the_panel_counters(self):
        """Clearing a key is not a new session: the session's EDSM upload
        counters must survive it, unlike the on_session_start() reset."""
        settings = DeletableSettings(initial_data={"edsm_api_key": "k", "edsm_commander_name": "C"})
        plugin = Plugin()
        plugin.settings = settings
        plugin.ed_running = True
        plugin.edsm = EdsmForwarder(settings, client=MagicMock())
        plugin.edsm.on_session_start()
        plugin.edsm._discard = set()
        plugin.edsm._success_count = 3
        plugin.edsm._fail_count = 2
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.clear_edsm_credentials()

        stats = plugin.edsm.get_stats()
        assert (stats["success_count"], stats["fail_count"]) == (3, 2)
        assert stats["active"] is False
        # ...and forwarding really has stopped.
        raw = {"timestamp": "2026-01-12T12:00:00Z", "event": "FSDJump"}
        plugin.edsm.observe(ParsedEvent(raw=raw, event_type="FSDJump", timestamp=raw["timestamp"]))
        assert plugin.edsm._buffer == []

    @pytest.mark.asyncio
    async def test_clear_edsm_credentials_reports_a_failed_write(self, tmp_path, monkeypatch):
        """A key that is still on disk re-arms the forwarder on the next load,
        so the frontend must not be told consent was withdrawn."""
        import json as json_module

        from src.modules.settings import PluginSettings

        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path / "settings"))
        plugin = Plugin()
        plugin.settings = PluginSettings()
        await plugin.set_edsm_credentials("CmdrTest", "api-key-123")

        def _disk_full(*_args, **_kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(json_module, "dump", _disk_full)
        result = await plugin.clear_edsm_credentials()

        assert result == {"success": False, "error": "could not persist settings"}
        assert (await plugin.get_edsm_credentials())["api_key_set"] is True
        reloaded = PluginSettings()
        await reloaded.load()
        assert reloaded.get("edsm_api_key") == "api-key-123"

    @pytest.mark.asyncio
    async def test_get_edsm_credentials_hides_key(self):
        plugin = Plugin()
        plugin.settings = MockSettings(initial_data={
            "edsm_commander_name": "CmdrTest",
            "edsm_api_key": "secret",
        })

        result = await plugin.get_edsm_credentials()

        assert result["commander_name"] == "CmdrTest"
        assert result["api_key_set"] is True
        assert "secret" not in str(result)  # raw key never returned

    @pytest.mark.asyncio
    async def test_get_edsm_credentials_unset(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.get_edsm_credentials()

        assert result["commander_name"] == ""
        assert result["api_key_set"] is False

    @pytest.mark.asyncio
    async def test_get_status_reports_edsm_fields(self):
        plugin = Plugin()
        plugin.settings = MockSettings(initial_data={
            "edsm_commander_name": "CmdrTest",
            "edsm_api_key": "secret",
            "enabled": True,
        })
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = False
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

        status = await plugin.get_status()

        assert status["edsm_commander_name"] == "CmdrTest"
        assert status["edsm_api_key_set"] is True


class TestEdsmInactiveWithoutKey:
    def test_inactive_without_api_key(self):
        settings = MockSettings(initial_data={"edsm_commander_name": "CmdrTest"})
        client = MagicMock()
        fwd = EdsmForwarder(settings, client=client)

        fwd.on_session_start()

        assert fwd._active is False
        # No discard fetch attempted when inactive.
        client.fetch_discard.assert_not_called()
