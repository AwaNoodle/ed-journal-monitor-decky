"""
Tests for the set_ed_running callable and ed_running state tracking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import Plugin


class TestEdRunningState:
    """Test ed_running boolean instance variable."""

    def test_ed_running_defaults_to_false(self):
        """Plugin initializes with ed_running = False."""
        plugin = Plugin()
        assert plugin.ed_running is False


class TestSetEdRunning:
    """Test set_ed_running callable."""

    @pytest.mark.asyncio
    async def test_set_ed_running_true(self):
        """set_ed_running(true) updates state, resets stats, and emits events."""
        plugin = Plugin()
        plugin.submitter = MagicMock()
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            result = await plugin.set_ed_running(True)

        assert result == {"success": True}
        assert plugin.ed_running is True
        plugin.submitter.reset_stats.assert_called_once()
        assert len(emitted_events) == 2
        assert emitted_events[0] == ("status_update", plugin.submitter.get_stats.return_value)
        assert emitted_events[1] == ("ed_state_change", {"ed_running": True})

    @pytest.mark.asyncio
    async def test_set_ed_running_false(self):
        """set_ed_running(false) updates state and emits event."""
        plugin = Plugin()
        plugin.ed_running = True
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            result = await plugin.set_ed_running(False)

        assert result == {"success": True}
        assert plugin.ed_running is False
        assert len(emitted_events) == 1
        assert emitted_events[0] == ("ed_state_change", {"ed_running": False})

    @pytest.mark.asyncio
    async def test_set_ed_running_noop_on_same_state(self):
        """set_ed_running should NOT emit event if state hasn't changed."""
        plugin = Plugin()
        # ed_running is False by default
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            result = await plugin.set_ed_running(False)

        assert result == {"success": True}
        assert plugin.ed_running is False
        assert len(emitted_events) == 0  # No event emitted

    @pytest.mark.asyncio
    async def test_set_ed_running_noop_on_same_state_true(self):
        """set_ed_running(true) when already true should NOT emit event."""
        plugin = Plugin()
        plugin.ed_running = True
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            result = await plugin.set_ed_running(True)

        assert result == {"success": True}
        assert plugin.ed_running is True
        assert len(emitted_events) == 0

    @pytest.mark.asyncio
    async def test_set_ed_running_state_transition_true_false(self):
        """State transition true -> false emits event."""
        plugin = Plugin()
        plugin.ed_running = True
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            await plugin.set_ed_running(False)

        assert len(emitted_events) == 1
        assert emitted_events[0] == ("ed_state_change", {"ed_running": False})

    @pytest.mark.asyncio
    async def test_set_ed_running_true_resets_submitter_stats(self):
        """set_ed_running(true) calls reset_stats on the submitter."""
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {"success_count": 0, "fail_count": 0}

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(True)

        plugin.submitter.reset_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_ed_running_true_emits_status_update(self):
        """set_ed_running(true) emits status_update with zeroed stats."""
        plugin = Plugin()
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {
            "success_count": 0,
            "fail_count": 0,
            "last_upload_time": None,
            "last_upload_event": None,
        }
        emitted_events = []

        async def mock_emit(event, data):
            emitted_events.append((event, data))

        with patch("decky.emit", side_effect=mock_emit):
            await plugin.set_ed_running(True)

        status_update = next(e for e in emitted_events if e[0] == "status_update")
        assert status_update[1]["success_count"] == 0
        assert status_update[1]["fail_count"] == 0
        assert status_update[1]["last_upload_time"] is None
        assert status_update[1]["last_upload_event"] is None

    @pytest.mark.asyncio
    async def test_set_ed_running_false_does_not_reset_stats(self):
        """set_ed_running(false) does NOT call reset_stats."""
        plugin = Plugin()
        plugin.ed_running = True
        plugin.submitter = MagicMock()

        with patch("decky.emit", new_callable=AsyncMock):
            await plugin.set_ed_running(False)

        plugin.submitter.reset_stats.assert_not_called()


class TestGetStatusEdRunning:
    """Test get_status returns ed_running field."""

    @pytest.mark.asyncio
    async def test_get_status_returns_ed_running_false(self):
        """get_status() includes ed_running: false when ED not running."""
        plugin = Plugin()
        # Need minimal setup for get_status
        plugin.settings = MagicMock()
        plugin.settings.get.side_effect = lambda key, default=None: {
            "journal_path": None,
            "journal_path_source": None,
            "uploader_id": None,
            "enabled": True,
            "detailed_logging": False,
        }.get(key, default)
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = False
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {}

        status = await plugin.get_status()
        assert status["ed_running"] is False

    @pytest.mark.asyncio
    async def test_get_status_returns_ed_running_true(self):
        """get_status() includes ed_running: true when ED is running."""
        plugin = Plugin()
        plugin.ed_running = True
        plugin.settings = MagicMock()
        plugin.settings.get.side_effect = lambda key, default=None: {
            "journal_path": None,
            "journal_path_source": None,
            "uploader_id": None,
            "enabled": True,
            "detailed_logging": False,
        }.get(key, default)
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = False
        plugin.submitter = MagicMock()
        plugin.submitter.get_stats.return_value = {}

        status = await plugin.get_status()
        assert status["ed_running"] is True
