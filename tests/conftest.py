"""
Pytest conftest - injects mock decky module before any test imports.
"""
import sys
from pathlib import Path

# Add the mock decky module to sys.modules before any test module imports it
mock_decky_path = Path(__file__).parent / "mock_decky.py"
sys.path.insert(0, str(mock_decky_path.parent))

import importlib

spec = importlib.util.spec_from_file_location("decky", str(mock_decky_path))
decky_module = importlib.util.module_from_spec(spec)
sys.modules["decky"] = decky_module
spec.loader.exec_module(decky_module)
