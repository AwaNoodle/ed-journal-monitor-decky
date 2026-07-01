from __future__ import annotations

"""
EDDN submitter.
Submits validated events to the EDDN API with retry logic.
"""

import asyncio as _asyncio
import json
import random
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    import ssl

    from src.modules.activity_log import ActivityLog
    from src.modules.settings import PluginSettings

from src.modules import constants
from src.modules.ssl_context import build_ssl_context

# Re-exported for backwards compatibility: the SSL context builder now lives in
# the shared ``ssl_context`` module and is reused by the EDSM forwarder.
_build_ssl_context = build_ssl_context

EDDN_URL = "https://eddn.edcd.io:4430/upload/"
DEFAULT_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5  # seconds
HTTP_OK = 200
HTTP_RATE_LIMITED = 429
HTTP_CLIENT_ERROR_MIN = 400
HTTP_SERVER_ERROR_MIN = 500


class EDDNSubmitter:
    """Submits EDDN messages with exponential backoff retry."""

    def __init__(self, settings: PluginSettings, activity_log: ActivityLog | None = None) -> None:
        self.settings = settings
        self.activity_log = activity_log
        self._ssl_context: ssl.SSLContext = build_ssl_context()
        self._success_count: int = 0
        self._fail_count: int = 0
        self._last_error_message: str | None = None
        self._last_http_status: int | None = None

    async def submit(
        self, message: dict, event_name: str | None = None, game_version: str = "", game_build: str = ""
    ) -> bool:
        """
        Submit an EDDN message. Populates header with settings, then POSTs.
        Returns True on success, False on failure.

        Args:
            message: EDDN message dict with $schemaRef, header, and message keys.
            event_name: Override for the event name used in activity log and UI.
                If not provided, extracted from message["message"]["event"].
                Needed for auxiliary schemas (commodity/outfitting/shipyard)
                which don't have an "event" field in the message payload.
            game_version: Game version string from Fileheader event (e.g. "4.1.0.404").
            game_build: Game build string from Fileheader event (e.g. "r280105/r0 ").
        """
        # Populate header
        header = {
            "uploaderID": self.settings.get("uploader_id", ""),
            "softwareName": constants.SOFTWARE_NAME,
            "softwareVersion": self.settings.get("software_version", constants.SOFTWARE_VERSION),
            "gatewayTimestamp": datetime.now(timezone.utc).isoformat(),
        }
        if game_version:
            header["gameversion"] = game_version
        if game_build:
            header["gamebuild"] = game_build
        message["header"] = header

        self._last_error_message = None
        self._last_http_status = None
        success = await self._submit_with_retry(message)

        resolved_name = event_name or message.get("message", {}).get("event", "unknown")

        if success:
            self._success_count += 1
            if self.activity_log:
                try:
                    await self.activity_log.record_success(resolved_name)
                except Exception as e:
                    decky.logger.error(f"Activity log record error: {e}")
            try:
                await decky.emit(
                    "upload_success",
                    {
                        "event": resolved_name,
                        "event_name": resolved_name,
                        "total_success": self._success_count,
                    },
                )
            except Exception as e:
                decky.logger.error(f"decky emit upload_success error: {e}")
        else:
            self._fail_count += 1
            if self.activity_log:
                try:
                    error_type = self._classify_error()
                    error_message = self._last_error_message or "Unknown error"
                    http_status = self._last_http_status
                    await self.activity_log.record_failure(resolved_name, error_type, error_message, http_status)
                except Exception as e:
                    decky.logger.error(f"Activity log record error: {e}")
            try:
                await decky.emit(
                    "upload_failed",
                    {
                        "event": resolved_name,
                        "total_failed": self._fail_count,
                    },
                )
            except Exception as e:
                decky.logger.error(f"decky emit upload_failed error: {e}")

        # The full per-target status_update snapshot is owned by main.py (which
        # aggregates EDDN with every other target). The per-event upload_success
        # /upload_failed emits above carry EDDN's running totals to the frontend.
        return success

    def _classify_error(self) -> str:
        """Classify the last error type for activity log recording."""
        if self._last_http_status is not None:
            return "http_error"
        return "network_error"

    async def _submit_with_retry(self, message: dict) -> bool:
        """Submit with exponential backoff retry for transient errors."""
        payload = json.dumps(message).encode("utf-8")

        for attempt in range(MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    EDDN_URL,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": (
                            f"ed-journal-monitor-decky/"
                            f"{self.settings.get('software_version', constants.SOFTWARE_VERSION)}"
                        ),
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=self._ssl_context) as response:
                    if response.status == HTTP_OK:
                        decky.logger.debug("EDDN submission successful")
                        return True
                    decky.logger.warning(f"EDDN returned status {response.status}")

            except urllib.error.HTTPError as e:
                if e.code == HTTP_RATE_LIMITED:
                    # Rate limited - retry
                    delay = self._calculate_retry_delay(attempt)
                    decky.logger.warning(f"EDDN rate limited, retrying in {delay}s")
                    if attempt < MAX_RETRIES:
                        await asyncio_sleep(delay)
                        continue

                elif HTTP_CLIENT_ERROR_MIN <= e.code < HTTP_SERVER_ERROR_MIN and e.code != HTTP_RATE_LIMITED:
                    # Client error - don't retry
                    self._last_error_message = e.reason
                    self._last_http_status = e.code
                    try:
                        body = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        body = "(unable to read response body)"
                    decky.logger.error(f"EDDN client error {e.code}: {e.reason} — {body}")
                    return False

                elif e.code >= HTTP_SERVER_ERROR_MIN:
                    # Server error - retry
                    delay = self._calculate_retry_delay(attempt)
                    decky.logger.warning(f"EDDN server error {e.code}, retrying in {delay}s")
                    if attempt < MAX_RETRIES:
                        await asyncio_sleep(delay)
                        continue

            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # Network/timeout error - retry
                self._last_error_message = str(e)
                delay = self._calculate_retry_delay(attempt)
                decky.logger.warning(f"EDDN network error, retrying in {delay}s: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio_sleep(delay)
                    continue

            except Exception as e:
                self._last_error_message = str(e)
                decky.logger.error(f"Unexpected EDDN submission error: {e}")
                return False

        self._last_error_message = "Max retries exceeded"
        decky.logger.error("EDDN submission failed after max retries")
        return False

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = INITIAL_RETRY_DELAY * (2**attempt)
        jitter = random.uniform(0, 1)
        return min(delay + jitter, 60.0)

    def get_stats(self) -> dict:
        """Return current upload statistics."""
        return {
            "success_count": self._success_count,
            "fail_count": self._fail_count,
        }

    def reset_stats(self) -> None:
        """Reset all upload statistics. Called when ED starts a new session."""
        self._success_count = 0
        self._fail_count = 0


async def asyncio_sleep(seconds: float) -> None:
    """Async sleep helper for testability."""
    await _asyncio.sleep(seconds)
