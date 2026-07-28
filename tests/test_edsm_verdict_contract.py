"""Tests for the backend→frontend verdict contract.

Covers:
- Verdict payload included in get_status (rehydrate-on-open)
- Verdict cleared on session start
- on_edsm_verdict callback stores the verdict correctly
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin


class TestVerdictInGetStatus:
    @pytest.mark.asyncio
    async def test_get_status_includes_edsm_worth_scanning_null_by_default(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None

        status = await plugin.get_status()

        assert "edsm_worth_scanning" in status
        assert status["edsm_worth_scanning"] is None

    @pytest.mark.asyncio
    async def test_get_status_returns_current_verdict(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None
        plugin._edsm_verdict = {"system": "Sol", "verdict": "red", "source": "edsm"}

        status = await plugin.get_status()

        assert status["edsm_worth_scanning"] == {"system": "Sol", "verdict": "red", "source": "edsm"}


class TestVerdictCallback:
    def test_on_edsm_verdict_stores_payload(self):
        plugin = Plugin()

        plugin._on_edsm_verdict("Maia", "green", False)

        assert plugin._edsm_verdict == {"system": "Maia", "verdict": "green", "source": "edsm"}

    def test_on_edsm_verdict_stores_none_verdict(self):
        plugin = Plugin()

        plugin._on_edsm_verdict("Unknown System", None, False)

        assert plugin._edsm_verdict == {"system": "Unknown System", "verdict": None, "source": "edsm"}

    def test_on_edsm_verdict_overwrites_previous(self):
        plugin = Plugin()
        plugin._edsm_verdict = {"system": "Old System", "verdict": "green", "source": "edsm"}

        plugin._on_edsm_verdict("New System", "red", False)

        assert plugin._edsm_verdict["system"] == "New System"
        assert plugin._edsm_verdict["verdict"] == "red"


class TestValueCallback:
    def test_on_edsm_value_merges_into_current_verdict(self):
        """The value callback merges totalValue/priorityBodies onto the verdict
        already stored for the same system (verdict is emitted first)."""
        plugin = Plugin()
        plugin._on_edsm_verdict("Sol", "red", False)

        plugin._on_edsm_value("Sol", {"totalValue": 1500, "priorityBodies": [{"name": "Earth", "value": 900}]})

        assert plugin._edsm_verdict == {
            "system": "Sol",
            "verdict": "red",
            "source": "edsm",
            "totalValue": 1500,
            "priorityBodies": [{"name": "Earth", "value": 900}],
        }

    def test_on_edsm_value_none_reports_neutral_fields(self):
        plugin = Plugin()
        plugin._on_edsm_verdict("Sol", "red", False)

        plugin._on_edsm_value("Sol", None)

        assert plugin._edsm_verdict["totalValue"] is None
        assert plugin._edsm_verdict["priorityBodies"] == []

    def test_on_edsm_value_ignored_if_verdict_not_stored_for_system(self):
        """A stale value callback for a system that isn't the current verdict is a no-op."""
        plugin = Plugin()
        plugin._on_edsm_verdict("Sol", "red", False)

        plugin._on_edsm_value("Maia", {"totalValue": 500, "priorityBodies": []})

        assert plugin._edsm_verdict["system"] == "Sol"
        assert "totalValue" not in plugin._edsm_verdict

    def test_on_edsm_value_ignored_if_no_verdict_stored(self):
        plugin = Plugin()

        plugin._on_edsm_value("Sol", {"totalValue": 500, "priorityBodies": []})

        assert plugin._edsm_verdict is None


class TestValueInGetStatus:
    @pytest.mark.asyncio
    async def test_get_status_includes_merged_value_fields(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin.watcher = None
        plugin.submitter = None
        plugin._on_edsm_verdict("Sol", "green", False)
        plugin._on_edsm_value("Sol", {"totalValue": 2205, "priorityBodies": []})

        status = await plugin.get_status()

        assert status["edsm_worth_scanning"]["totalValue"] == 2205
        assert status["edsm_worth_scanning"]["priorityBodies"] == []


class TestVerdictClearedOnSessionStart:
    @pytest.mark.asyncio
    async def test_set_ed_running_true_clears_verdict(self):
        plugin = Plugin()
        plugin.settings = MockSettings()
        plugin._edsm_verdict = {"system": "Old System", "verdict": "green", "source": "edsm"}
        plugin.submitter = MagicMock()
        plugin.submitter.reset_stats = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        plugin.consumers = []

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(True)

        assert plugin._edsm_verdict is None
