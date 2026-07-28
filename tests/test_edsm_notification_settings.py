"""Tests for the worth-scanning notification settings and their backend plumbing.

Covers:
- edsm_notifications_enabled / edsm_notify_all_verdicts round-trip and default to False
- set_edsm_notifications_enabled / set_edsm_notify_all_verdicts callables persist and
  are reflected in get_status
- notify is excluded from the stored/rehydrated worth-scanning verdict
"""
from __future__ import annotations

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.settings import PluginSettings


class TestSettingsDefaults:
    @pytest.mark.asyncio
    async def test_notifications_enabled_defaults_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path))
        settings = PluginSettings()
        await settings.load()

        assert settings.get("edsm_notifications_enabled", False) is False

    @pytest.mark.asyncio
    async def test_notify_all_verdicts_defaults_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path))
        settings = PluginSettings()
        await settings.load()

        assert settings.get("edsm_notify_all_verdicts", False) is False

    @pytest.mark.asyncio
    async def test_both_keys_round_trip_through_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path))
        settings = PluginSettings()
        await settings.load()
        await settings.set("edsm_notifications_enabled", True)
        await settings.set("edsm_notify_all_verdicts", True)

        reloaded = PluginSettings()
        await reloaded.load()

        assert reloaded.get("edsm_notifications_enabled", False) is True
        assert reloaded.get("edsm_notify_all_verdicts", False) is True


class TestNotificationCallables:
    @pytest.mark.asyncio
    async def test_set_edsm_notifications_enabled_persists_true(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_notifications_enabled(True)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_notifications_enabled") is True

    @pytest.mark.asyncio
    async def test_set_edsm_notifications_enabled_persists_false(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_notifications_enabled(False)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_notifications_enabled") is False

    @pytest.mark.asyncio
    async def test_set_edsm_notify_all_verdicts_persists_true(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_notify_all_verdicts(True)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_notify_all_verdicts") is True

    @pytest.mark.asyncio
    async def test_set_edsm_notify_all_verdicts_persists_false(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        result = await plugin.set_edsm_notify_all_verdicts(False)

        assert result == {"success": True}
        assert plugin.settings.get("edsm_notify_all_verdicts") is False


class TestGetStatusReflectsNotificationSettings:
    @pytest.mark.asyncio
    async def test_get_status_reports_defaults_false(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None

        status = await plugin.get_status()

        assert status["edsm_notifications_enabled"] is False
        assert status["edsm_notify_all_verdicts"] is False

    @pytest.mark.asyncio
    async def test_get_status_reports_set_values(self):
        plugin = Plugin()
        plugin.settings = MockSettings(initial_data={
            "edsm_notifications_enabled": True,
            "edsm_notify_all_verdicts": True,
        })
        plugin.watcher = None
        plugin.submitter = None

        status = await plugin.get_status()

        assert status["edsm_notifications_enabled"] is True
        assert status["edsm_notify_all_verdicts"] is True


class TestNotifyExcludedFromRehydration:
    def test_on_edsm_verdict_stores_payload_without_notify_key(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        plugin._on_edsm_verdict("Sol", "green", True)

        assert plugin._edsm_verdict == {"system": "Sol", "verdict": "green", "source": "edsm"}
        assert "notify" not in plugin._edsm_verdict

    def test_on_edsm_verdict_stores_payload_without_notify_key_when_false(self):
        plugin = Plugin()
        plugin.settings = MockSettings()

        plugin._on_edsm_verdict("Sol", "red", False)

        assert "notify" not in plugin._edsm_verdict

    def test_on_edsm_value_still_merges_onto_stored_dict(self):
        """_on_edsm_value must still merge totalValue/priorityBodies after the notify param was added upstream."""
        plugin = Plugin()
        plugin.settings = MockSettings()

        plugin._on_edsm_verdict("Sol", "green", True)
        plugin._on_edsm_value("Sol", {"totalValue": 1500, "priorityBodies": [{"name": "Earth", "value": 900}]})

        assert plugin._edsm_verdict == {
            "system": "Sol",
            "verdict": "green",
            "source": "edsm",
            "totalValue": 1500,
            "priorityBodies": [{"name": "Earth", "value": 900}],
        }
        assert "notify" not in plugin._edsm_verdict

    @pytest.mark.asyncio
    async def test_get_status_worth_scanning_field_has_no_notify_key(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None
        plugin._on_edsm_verdict("Sol", "green", True)

        status = await plugin.get_status()

        assert "notify" not in status["edsm_worth_scanning"]
