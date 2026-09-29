"""Tests for how PluginSettings persists to disk (permissions, atomicity, delete)."""

import json
import stat

import pytest

from src.modules.settings import PluginSettings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """A PluginSettings bound to a temporary settings dir."""
    monkeypatch.setenv("DECKY_PLUGIN_SETTINGS_DIR", str(tmp_path / "settings"))
    return PluginSettings()


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def _raise_disk_full(*_args, **_kwargs):
    """Fail the way a full or read-only filesystem does, mid-write."""
    raise OSError(28, "No space left on device")


class TestSavePermissions:
    """The settings file holds the EDSM API key, so it must be owner-only."""

    @pytest.mark.asyncio
    async def test_new_file_is_owner_only(self, settings):
        await settings.set("edsm_api_key", "secret")

        assert _mode(settings._settings_file) == 0o600
        assert _mode(settings._settings_dir) == 0o700
        assert json.loads(settings._settings_file.read_text())["edsm_api_key"] == "secret"

    @pytest.mark.asyncio
    async def test_existing_world_readable_file_is_tightened(self, settings):
        settings._settings_dir.mkdir(parents=True)
        settings._settings_file.write_text("{}")
        settings._settings_file.chmod(0o644)

        await settings.set("edsm_api_key", "secret")

        assert _mode(settings._settings_file) == 0o600

    @pytest.mark.asyncio
    async def test_save_never_raises_on_oserror(self, settings, monkeypatch):
        monkeypatch.setattr("os.open", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

        assert await settings.save() is False  # must not raise


class TestAtomicWrite:
    """The file is the documented home of the EDSM API key: a failed or
    interrupted write must not lose the settings that were already there."""

    @pytest.mark.asyncio
    async def test_failed_write_keeps_previous_contents(self, settings, monkeypatch):
        await settings.set("edsm_api_key", "secret")
        before = settings._settings_file.read_text()

        monkeypatch.setattr(json, "dump", _raise_disk_full)
        assert await settings.save() is False

        assert settings._settings_file.read_text() == before
        assert list(settings._settings_dir.glob("*.tmp")) == []  # no debris left

    @pytest.mark.asyncio
    async def test_existing_directory_is_tightened(self, settings):
        settings._settings_dir.mkdir(parents=True, mode=0o755)

        await settings.set("edsm_api_key", "secret")

        assert _mode(settings._settings_dir) == 0o700


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_key_and_persists(self, settings):
        await settings.set("edsm_api_key", "secret")

        assert await settings.delete("edsm_api_key") is True

        assert settings.get("edsm_api_key") is None
        assert "edsm_api_key" not in json.loads(settings._settings_file.read_text())

        reloaded = PluginSettings()
        await reloaded.load()
        assert reloaded.get("edsm_api_key") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key_is_a_noop(self, settings):
        assert await settings.delete("never_set") is True

        assert not settings._settings_file.exists()

    @pytest.mark.asyncio
    async def test_delete_reports_a_failed_write_and_keeps_the_value(self, settings, monkeypatch):
        """A key still on disk must still read as present in memory, or the UI
        reports consent withdrawn while the next load re-arms the forwarder."""
        await settings.set("edsm_api_key", "secret")

        monkeypatch.setattr(json, "dump", _raise_disk_full)
        assert await settings.delete("edsm_api_key") is False

        assert settings.get("edsm_api_key") == "secret"
        assert json.loads(settings._settings_file.read_text())["edsm_api_key"] == "secret"
