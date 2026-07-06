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

        plugin._on_edsm_verdict("Maia", "green")

        assert plugin._edsm_verdict == {"system": "Maia", "verdict": "green", "source": "edsm"}

    def test_on_edsm_verdict_stores_none_verdict(self):
        plugin = Plugin()

        plugin._on_edsm_verdict("Unknown System", None)

        assert plugin._edsm_verdict == {"system": "Unknown System", "verdict": None, "source": "edsm"}

    def test_on_edsm_verdict_overwrites_previous(self):
        plugin = Plugin()
        plugin._edsm_verdict = {"system": "Old System", "verdict": "green", "source": "edsm"}

        plugin._on_edsm_verdict("New System", "red")

        assert plugin._edsm_verdict["system"] == "New System"
        assert plugin._edsm_verdict["verdict"] == "red"


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
