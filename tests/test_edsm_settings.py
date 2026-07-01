"""
Tests for EDSM credential settings and the backend callables that get/set them.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.forwarders.edsm import EdsmForwarder


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
