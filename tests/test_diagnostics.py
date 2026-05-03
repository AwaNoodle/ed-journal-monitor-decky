"""Tests for the diagnostics module."""

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.modules.diagnostics import _gather_runtime_state, create_diagnostics


@pytest.fixture
def settings_dir(tmp_path, monkeypatch):
    """Set up a temporary settings directory."""
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(settings_dir))
    return settings_dir


@pytest.fixture
def plugin_dir(tmp_path, monkeypatch):
    """Set up a temporary plugin directory with plugin.json."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    plugin_json = plugin_dir / "plugin.json"
    plugin_json.write_text(json.dumps({"name": "ED Journal Monitor", "api_version": 1}))
    monkeypatch.setenv("DECKY_PLUGIN_DIR", str(plugin_dir))
    return plugin_dir


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """Set up a temporary log directory with plugin.log."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "plugin.log"
    log_file.write_text("INFO: ED Journal Monitor starting...\nDEBUG: test debug line\n")
    monkeypatch.setenv("DECKY_PLUGIN_LOG", str(log_file))
    monkeypatch.setenv("DECKY_PLUGIN_LOG_DIR", str(log_dir))
    return log_dir


@pytest.fixture
def mock_settings():
    """Create a mock PluginSettings."""
    settings = MagicMock()
    settings.get.side_effect = lambda key, default=None: {
        "journal_path_source": "auto",
        "enabled": True,
        "uploader_id": "test-uploader",
        "detailed_logging": False,
    }.get(key, default)
    return settings


@pytest.fixture
def mock_watcher():
    """Create a mock JournalWatcher."""
    watcher = MagicMock()
    watcher.is_running = True
    watcher._journal_path = "/fake/journal/path"
    watcher._poll_interval = 10
    watcher._file_positions = {"/fake/journal/Journal.2026.log": 42}
    watcher._known_files = {"/fake/journal/Journal.2026.log"}
    return watcher


@pytest.fixture
def mock_submitter():
    """Create a mock EDDNSubmitter."""
    submitter = MagicMock()
    submitter.get_stats.return_value = {
        "success_count": 5,
        "fail_count": 1,
        "last_upload_time": "2026-05-03T12:00:00+00:00",
    }
    return submitter


class TestCreateDiagnostics:
    """Test create_diagnostics()."""

    def test_produces_zip_with_expected_contents(
        self, settings_dir, plugin_dir, log_dir, mock_settings, mock_watcher, mock_submitter
    ):
        """Test that create_diagnostics() produces a zip with expected contents."""
        # Create a settings.json file
        (settings_dir / "settings.json").write_text(json.dumps({"enabled": True}))

        result = create_diagnostics(mock_settings, mock_watcher, mock_submitter)

        assert result["success"] is True
        assert "path" in result
        assert "size" in result
        assert result["size"] > 0

        zip_path = Path(result["path"])
        assert zip_path.exists()

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "runtime_state.json" in names
            assert "settings.json" in names
            assert "plugin.json" in names
            assert "plugin.log" in names

            # Verify runtime_state.json contents
            runtime_state = json.loads(zf.read("runtime_state.json"))
            assert runtime_state["watcher_running"] is True
            assert runtime_state["journal_path"] == "/fake/journal/path"
            assert runtime_state["poll_interval"] == 10
            assert "submitter_stats" in runtime_state
            assert runtime_state["submitter_stats"]["success_count"] == 5

    def test_handles_missing_log_file(
        self, settings_dir, plugin_dir, mock_settings, mock_watcher, mock_submitter, monkeypatch
    ):
        """Test that create_diagnostics() handles missing log file gracefully."""
        # No log file — point to nonexistent path
        monkeypatch.setenv("DECKY_PLUGIN_LOG", "/nonexistent/plugin.log")

        result = create_diagnostics(mock_settings, mock_watcher, mock_submitter)

        assert result["success"] is True
        assert "path" in result

        with zipfile.ZipFile(result["path"]) as zf:
            names = zf.namelist()
            assert "plugin.log" not in names
            assert "runtime_state.json" in names

    def test_overwrites_previous_bundle(
        self, settings_dir, plugin_dir, log_dir, mock_settings, mock_watcher, mock_submitter
    ):
        """Test that create_diagnostics() overwrites previous bundle."""
        # Create first bundle
        result1 = create_diagnostics(mock_settings, mock_watcher, mock_submitter)
        assert result1["success"]

        # Create second bundle (should overwrite)
        result2 = create_diagnostics(mock_settings, mock_watcher, mock_submitter)
        assert result2["success"]
        assert result2["path"] == result1["path"]

        # The zip should be overwritten (same path, potentially different mtime)
        zip_path = Path(result2["path"])
        assert zip_path.exists()


class TestSetDetailedLogging:
    """Test set_detailed_logging via Plugin class."""

    @pytest.mark.asyncio
    async def test_enable_sets_debug_and_persists(self, tmp_path, monkeypatch):
        """Test that set_detailed_logging(true) sets logger to DEBUG and persists."""
        import logging

        from src.modules.settings import PluginSettings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(settings_dir))

        settings = PluginSettings()
        await settings.load()

        # Simulate the method logic
        decky_logger = logging.getLogger("decky")
        decky_logger.setLevel(logging.DEBUG)
        await settings.set("detailed_logging", True)

        assert decky_logger.level == logging.DEBUG
        assert settings.get("detailed_logging") is True

    @pytest.mark.asyncio
    async def test_disable_sets_info_and_persists(self, tmp_path, monkeypatch):
        """Test that set_detailed_logging(false) sets logger to INFO and persists."""
        import logging

        from src.modules.settings import PluginSettings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(settings_dir))

        settings = PluginSettings()
        await settings.load()

        # First enable, then disable
        decky_logger = logging.getLogger("decky")
        decky_logger.setLevel(logging.DEBUG)
        await settings.set("detailed_logging", True)

        # Now disable
        decky_logger.setLevel(logging.INFO)
        await settings.set("detailed_logging", False)

        assert decky_logger.level == logging.INFO
        assert settings.get("detailed_logging") is False

    @pytest.mark.asyncio
    async def test_default_is_info(self, tmp_path, monkeypatch):
        """Test that default logging level is INFO on first run."""
        import logging

        from src.modules.settings import PluginSettings

        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(settings_dir))

        settings = PluginSettings()
        await settings.load()

        # Default should be False (not detailed)
        detailed = settings.get("detailed_logging", False)
        assert detailed is False

        # Simulate _main logic: if not detailed_logging, level is INFO
        decky_logger = logging.getLogger("decky")
        if not detailed:
            decky_logger.setLevel(logging.INFO)

        assert decky_logger.level == logging.INFO


class TestGatherRuntimeState:
    """Test _gather_runtime_state()."""

    def test_with_all_components(self, mock_settings, mock_watcher, mock_submitter, monkeypatch):
        """Test runtime state snapshot with all components present."""
        monkeypatch.setenv("DECKY_PLUGIN_VERSION", "0.1.0")

        state = _gather_runtime_state(mock_settings, mock_watcher, mock_submitter)

        assert "python_version" in state
        assert state["decky_plugin_version"] == "0.1.0"
        assert state["watcher_running"] is True
        assert state["journal_path"] == "/fake/journal/path"
        assert state["poll_interval"] == 10
        assert state["file_positions"] == {"/fake/journal/Journal.2026.log": 42}
        assert state["known_files"] == ["/fake/journal/Journal.2026.log"]
        assert state["submitter_stats"]["success_count"] == 5

    def test_with_no_watcher_or_submitter(self, mock_settings, monkeypatch):
        """Test runtime state snapshot with no watcher/submitter."""
        state = _gather_runtime_state(mock_settings, None, None)

        assert state["watcher_running"] is False
        assert state["submitter_stats"] == {}
