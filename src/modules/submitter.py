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
    from src.modules.activity_log import ActivityLog
    from src.modules.settings import PluginSettings

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
        self._success_count: int = 0
        self._fail_count: int = 0
        self._last_upload_time: str | None = None
        self._last_upload_event: str | None = None
        self._last_error_message: str | None = None
        self._last_http_status: int | None = None

    async def submit(self, message: dict) -> bool:
        """
        Submit an EDDN message. Populates header with settings, then POSTs.
        Returns True on success, False on failure.
        """
        # Populate header
        message["header"] = {
            "uploaderID": self.settings.get("uploader_id", ""),
            "softwareName": "ed-journal-monitor-decky",
            "softwareVersion": self.settings.get("software_version", "0.1.0"),
            "gatewayTimestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._last_error_message = None
        self._last_http_status = None
        success = await self._submit_with_retry(message)

        event_name = message.get("message", {}).get("event", "unknown")

        if success:
            self._success_count += 1
            self._last_upload_time = datetime.now(timezone.utc).isoformat()
            self._last_upload_event = event_name
            if self.activity_log:
                await self.activity_log.record_success(event_name)
            await decky.emit("upload_success", {
                "event": event_name,
                "event_name": event_name,
                "total_success": self._success_count,
            })
        else:
            self._fail_count += 1
            if self.activity_log:
                error_type = self._classify_error()
                error_message = self._last_error_message or "Unknown error"
                http_status = self._last_http_status
                await self.activity_log.record_failure(event_name, error_type, error_message, http_status)
            await decky.emit("upload_failed", {
                "event": event_name,
                "total_failed": self._fail_count,
            })

        await decky.emit("status_update", self.get_stats())
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
                        "User-Agent": f"ed-journal-monitor-decky/{self.settings.get('software_version', '0.1.0')}",
                    },
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
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
                    decky.logger.error(f"EDDN client error {e.code}: {e.reason}")
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
        delay = INITIAL_RETRY_DELAY * (2 ** attempt)
        jitter = random.uniform(0, 1)
        return min(delay + jitter, 60.0)

    def get_stats(self) -> dict:
        """Return current upload statistics."""
        return {
            "success_count": self._success_count,
            "fail_count": self._fail_count,
            "last_upload_time": self._last_upload_time,
            "last_upload_event": self._last_upload_event,
        }


async def asyncio_sleep(seconds: float) -> None:
    """Async sleep helper for testability."""
    await _asyncio.sleep(seconds)
