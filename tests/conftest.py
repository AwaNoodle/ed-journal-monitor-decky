"""
Pytest conftest - injects mock decky module before any test imports,
and provides shared fixtures.
"""
import json
import sys
from pathlib import Path
from typing import Optional

import pytest

# Add the mock decky module to sys.modules before any test module imports it
mock_decky_path = Path(__file__).parent / "mock_decky.py"
sys.path.insert(0, str(mock_decky_path.parent))

import importlib

spec = importlib.util.spec_from_file_location("decky", str(mock_decky_path))
decky_module = importlib.util.module_from_spec(spec)
sys.modules["decky"] = decky_module
spec.loader.exec_module(decky_module)


class MockSettings:
    """Shared mock settings for tests. Accepts initial data via constructor."""

    def __init__(self, initial_data: Optional[dict] = None):
        self._data = initial_data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value


@pytest.fixture
def mock_settings():
    """Provide a MockSettings instance with sensible defaults."""
    return MockSettings(initial_data={
        "uploader_id": "test-uploader",
        "software_version": "0.1.0",
        "poll_interval": 10,
    })


@pytest.fixture
def copy_fixture(tmp_path):
    """Return a helper that copies a fixture file to tmp_path and returns the destination path."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    def _copy(filename):
        source = fixtures_dir / filename
        destination = tmp_path / filename
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return destination

    return _copy


@pytest.fixture
def load_fixture():
    """Return a helper that loads and parses a fixture JSON file."""
    fixtures_dir = Path(__file__).parent / "fixtures"

    def _load(filename):
        return json.loads((fixtures_dir / filename).read_text(encoding="utf-8"))

    return _load
