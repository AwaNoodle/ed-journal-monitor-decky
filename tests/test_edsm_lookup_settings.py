"""Tests for the edsm_lookups_enabled setting and its callable."""
from __future__ import annotations

import pytest
from conftest import MockSettings

from main import Plugin


class TestEdsmLookupsEnabledSetting:
    @pytest.mark.asyncio
    async def test_set_edsm_lookups_enabled_persists_true(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_lookups_enabled(True)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_lookups_enabled") is True

    @pytest.mark.asyncio
    async def test_set_edsm_lookups_enabled_persists_false(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_lookups_enabled(False)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_lookups_enabled") is False

    @pytest.mark.asyncio
    async def test_get_status_reports_edsm_lookups_enabled_default_false(self):
        """Auto-lookups default to off (conservative — public API, opt-in)."""
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None

        status = await plugin.get_status()

        assert status["edsm_lookups_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_status_reports_edsm_lookups_enabled_when_set(self):
        plugin = Plugin()
        plugin.settings = MockSettings(initial_data={"edsm_lookups_enabled": True})
        plugin.watcher = None
        plugin.submitter = None

        status = await plugin.get_status()

        assert status["edsm_lookups_enabled"] is True

    @pytest.mark.asyncio
    async def test_setting_persists_across_load(self):
        """Value set via callable is readable via get()."""
        plugin = Plugin()
        plugin.settings = MockSettings()

        await plugin.set_edsm_lookups_enabled(True)
        assert plugin.settings.get("edsm_lookups_enabled") is True

        await plugin.set_edsm_lookups_enabled(False)
        assert plugin.settings.get("edsm_lookups_enabled") is False
