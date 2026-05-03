"""
Mock decky module for testing.
Provides the same interface as the real decky plugin module.
"""

import logging

logger = logging.getLogger("decky")


async def emit(event: str, *args):
    """Mock emit - does nothing in tests."""


def migrate_logs(*args, **kwargs):
    pass

def migrate_settings(*args, **kwargs):
    pass

def migrate_runtime(*args, **kwargs):
    pass

# Constants
HOME = "/home/deck"
USER = "deck"
DECKY_USER = "deck"
DECKY_USER_HOME = "/home/deck"
DECKY_HOME = "/home/deck/homebrew"
DECKY_PLUGIN_SETTINGS_DIR = "/tmp/test_settings"
DECKY_PLUGIN_RUNTIME_DIR = "/tmp/test_runtime"
DECKY_PLUGIN_LOG_DIR = "/tmp/test_logs"
DECKY_PLUGIN_DIR = "/tmp/test_plugin"
DECKY_PLUGIN_NAME = "ED Journal Monitor"
DECKY_PLUGIN_VERSION = "0.1.0"
DECKY_PLUGIN_LOG = "/tmp/test_logs/plugin.log"
