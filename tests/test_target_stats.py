"""
Tests for iteration-driven per-target upload stats aggregation in main.Plugin.

The status payload is a target-keyed map built by iterating the consumer
registry (EDDN wired in as one entry), with no hardcoded per-target branches,
so EDDN and EDSM counts stay isolated and a new target is purely additive.
"""

from unittest.mock import MagicMock, patch

import pytest

from main import Plugin


def _stats_consumer(name, success=0, fail=0, reports=True):
    c = MagicMock()
    c.name = name
    c.reports_upload_stats = reports
    c.get_stats.return_value = {"success_count": success, "fail_count": fail}
    return c


class TestBuildTargetStats:
    def test_map_includes_eddn_and_consumer_targets(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 3, "fail_count": 1}
        plugin.consumers = [_stats_consumer("edsm", success=5, fail=2)]

        payload = plugin._build_target_stats()

        assert payload["targets"]["eddn"] == {"success_count": 3, "fail_count": 1}
        assert payload["targets"]["edsm"] == {"success_count": 5, "fail_count": 2}

    def test_non_reporting_consumer_excluded(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        # The session accumulator does not report upload stats.
        plugin.consumers = [_stats_consumer("session", reports=False)]

        payload = plugin._build_target_stats()

        assert "session" not in payload["targets"]
        assert list(payload["targets"].keys()) == ["eddn"]

    def test_eddn_isolated_from_edsm(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 10, "fail_count": 0}
        # EDSM failing hard should not change EDDN's entry.
        plugin.consumers = [_stats_consumer("edsm", success=0, fail=7)]

        payload = plugin._build_target_stats()

        assert payload["targets"]["eddn"]["fail_count"] == 0
        assert payload["targets"]["edsm"]["fail_count"] == 7

    def test_additive_third_target(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        plugin.consumers = [
            _stats_consumer("edsm"),
            _stats_consumer("inara"),  # hypothetical 3rd target needs no reshape
        ]

        payload = plugin._build_target_stats()

        assert set(payload["targets"].keys()) == {"eddn", "edsm", "inara"}


class TestResetEmitsZeroedMap:
    @pytest.mark.asyncio
    async def test_set_ed_running_true_zeroes_all_targets(self):
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}
        edsm = _stats_consumer("edsm", success=0, fail=0)
        plugin.consumers = [edsm]
        emitted = []

        async def mock_emit(event, data):
            emitted.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            await plugin.set_ed_running(True)

        # Every consumer's on_session_start was called (reset), and the emitted
        # status_update carries the zeroed per-target map.
        edsm.on_session_start.assert_called_once()
        plugin.submitter.reset_stats.assert_called_once()
        status = next(d for e, d in emitted if e == "status_update")
        assert status["targets"]["eddn"] == {"success_count": 0, "fail_count": 0}
        assert status["targets"]["edsm"]["success_count"] == 0
        assert status["targets"]["edsm"]["fail_count"] == 0
