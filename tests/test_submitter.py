"""
Tests for the EDDNSubmitter module.
Tests message construction, retry logic, and SSL context with mocked HTTP.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from src.modules.submitter import EDDN_URL, INITIAL_RETRY_DELAY, MAX_RETRIES, EDDNSubmitter


@pytest.fixture
def submitter():
    return EDDNSubmitter(MockSettings(initial_data={"uploader_id": "test-uploader", "software_version": "0.1.0"}))


class TestMessageConstruction:
    """Tests for message header population."""

    @pytest.mark.asyncio
    async def test_submit_populates_header(self, submitter):
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
            "header": {},
            "message": {"event": "FSDJump", "StarSystem": "Sol"},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = await submitter.submit(message)

        assert result is True
        assert message["header"]["uploaderID"] == "test-uploader"
        assert message["header"]["softwareName"] == "ED Journal Monitor Decky"
        assert message["header"]["softwareVersion"] == "0.1.0"
        # EDDN schemas: "this property will be overwritten by the gateway;
        # submitters are not intended to populate this property."
        assert "gatewayTimestamp" not in message["header"]

    @pytest.mark.asyncio
    async def test_submit_includes_game_version_in_header(self, submitter):
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
            "header": {},
            "message": {"event": "FSDJump", "StarSystem": "Sol"},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = await submitter.submit(
                message,
                game_version="4.1.0.404",
                game_build="r280105/r0 ",
            )

        assert result is True
        assert message["header"]["gameversion"] == "4.1.0.404"
        assert message["header"]["gamebuild"] == "r280105/r0 "

    @pytest.mark.asyncio
    async def test_submit_sends_empty_string_game_version_when_not_provided(self, submitter):
        """docs/Developers.md: if a data-source value can't be set, the field
        MUST still be sent with an empty string value, not omitted."""
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
            "header": {},
            "message": {"event": "FSDJump", "StarSystem": "Sol"},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            result = await submitter.submit(message)

        assert result is True
        assert message["header"]["gameversion"] == ""
        assert message["header"]["gamebuild"] == ""

    @pytest.mark.asyncio
    async def test_submit_sends_correct_url(self, submitter):
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/journal/1",
            "header": {},
            "message": {"event": "FSDJump"},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            await submitter.submit(message)

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.full_url == EDDN_URL
        assert request.method == "POST"
        assert request.get_header("Content-type") == "application/json"


class TestRetryLogic:
    """Tests for exponential backoff retry."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, submitter):
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock):
                result = await submitter.submit(message)

        assert result is True
        assert mock_urlopen.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_429(self, submitter):
        import urllib.error

        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            # First call: 429, second call: 200
            mock_response_ok = MagicMock()
            mock_response_ok.status = 200
            mock_response_ok.__enter__ = lambda s: s
            mock_response_ok.__exit__ = MagicMock(return_value=False)

            error_429 = urllib.error.HTTPError(
                EDDN_URL, 429, "Rate Limited", {}, None,
            )
            mock_urlopen.side_effect = [error_429, mock_response_ok]

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock):
                result = await submitter.submit(message)

        assert result is True
        assert mock_urlopen.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, submitter):
        import urllib.error

        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            error_400 = urllib.error.HTTPError(
                EDDN_URL, 400, "Bad Request", {}, None,
            )
            mock_urlopen.side_effect = error_400

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock):
                result = await submitter.submit(message)

        assert result is False
        assert mock_urlopen.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_retries_on_5xx_up_to_max(self, submitter):
        import urllib.error

        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            error_500 = urllib.error.HTTPError(
                EDDN_URL, 500, "Internal Server Error", {}, None,
            )
            mock_urlopen.side_effect = error_500

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock):
                result = await submitter.submit(message)

        assert result is False
        assert mock_urlopen.call_count == MAX_RETRIES + 1  # Initial + retries

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, submitter):

        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Connection timed out")

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock):
                result = await submitter.submit(message)

        assert result is False
        assert mock_urlopen.call_count == MAX_RETRIES + 1


class TestRetryDelay:
    """docs/Developers.md: 'You MUST wait some reasonable time (minimum
    1 minute) before retrying any failed message.'"""

    def test_initial_retry_delay_meets_minimum(self, submitter):
        assert INITIAL_RETRY_DELAY >= 60

    def test_first_retry_delay_is_at_least_60_seconds(self, submitter):
        delay = submitter._calculate_retry_delay(0)
        assert delay >= 60.0

    def test_backoff_still_grows_with_attempts(self, submitter):
        first = submitter._calculate_retry_delay(0)
        second = submitter._calculate_retry_delay(1)
        # Jitter is at most 1s, so a real doubling is still detectable.
        assert second > first + 1


class TestActivityLogIntegration:
    """Tests for ActivityLog integration in submitter."""

    @pytest.mark.asyncio
    async def test_success_records_activity(self):
        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        entries = log.get_recent()
        assert len(entries) == 1
        assert entries[0]["outcome"] == "success"
        assert entries[0]["event_type"] == "FSDJump"

    @pytest.mark.asyncio
    async def test_http_failure_records_activity(self):
        import urllib.error

        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        message = {"$schemaRef": "", "header": {}, "message": {"event": "Scan"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            error_400 = urllib.error.HTTPError(
                EDDN_URL, 400, "Bad Request", {}, None,
            )
            mock_urlopen.side_effect = error_400

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        entries = log.get_recent()
        assert len(entries) == 1
        assert entries[0]["outcome"] == "failure"
        assert entries[0]["event_type"] == "Scan"
        assert entries[0]["error_type"] == "http_error"
        assert entries[0]["http_status"] == 400

    @pytest.mark.asyncio
    async def test_network_failure_records_activity(self):
        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        message = {"$schemaRef": "", "header": {}, "message": {"event": "Docked"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = TimeoutError("Connection timed out")

            with patch("src.modules.submitter.asyncio_sleep", new_callable=AsyncMock), \
                 patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        entries = log.get_recent()
        assert len(entries) == 1
        assert entries[0]["outcome"] == "failure"
        assert entries[0]["error_type"] == "network_error"
        assert entries[0]["http_status"] is None

    @pytest.mark.asyncio
    async def test_upload_success_event_includes_event_name(self):
        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        # Find the upload_success emit call
        emit_calls = mock_decky.emit.call_args_list
        success_call = next(c for c in emit_calls if c[0][0] == "upload_success")
        assert success_call[0][1]["event_name"] == "FSDJump"


class TestSSLContext:
    """Tests that the submitter wires the shared SSL context into requests."""

    @pytest.mark.asyncio
    async def test_submit_passes_ssl_context_to_urlopen(self, submitter):
        """Verify that urlopen is called with the context kwarg."""
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        call_kwargs = mock_urlopen.call_args
        assert "context" in call_kwargs.kwargs
        assert call_kwargs.kwargs["context"] is submitter._ssl_context


class TestEventNameOverride:
    """Tests for event_name parameter in submit()."""

    @pytest.mark.asyncio
    async def test_event_name_override_used_in_activity_log(self):
        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        # Commodity/3 message has no "event" key in message payload
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/commodity/3",
            "header": {},
            "message": {"systemName": "Sol", "stationName": "Test", "commodities": []},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message, event_name="Market")

        entries = log.get_recent()
        assert len(entries) == 1
        assert entries[0]["event_type"] == "Market"  # Not "unknown"



class TestStats:
    """Tests for upload statistics tracking."""

    @pytest.mark.asyncio
    async def test_success_increments_count(self, submitter):
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        stats = submitter.get_stats()
        assert stats["success_count"] == 1
        assert stats["fail_count"] == 0

    @pytest.mark.asyncio
    async def test_failure_increments_fail_count(self, submitter):
        import urllib.error

        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            error_400 = urllib.error.HTTPError(
                EDDN_URL, 400, "Bad Request", {}, None,
            )
            mock_urlopen.side_effect = error_400

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        stats = submitter.get_stats()
        assert stats["success_count"] == 0
        assert stats["fail_count"] == 1


class TestResetStats:
    """Tests for resetting upload statistics on ED session start."""

    def test_reset_stats_clears_all_counters(self):
        """After submissions, reset_stats() zeros all counters."""
        submitter = EDDNSubmitter(MockSettings(initial_data={"uploader_id": "test", "software_version": "0.1.0"}))
        # Manually set counters to simulate prior activity
        submitter._success_count = 5
        submitter._fail_count = 2

        submitter.reset_stats()

        stats = submitter.get_stats()
        assert stats["success_count"] == 0
        assert stats["fail_count"] == 0

    def test_reset_stats_is_idempotent(self):
        """Calling reset_stats() multiple times is safe."""
        submitter = EDDNSubmitter(MockSettings(initial_data={"uploader_id": "test", "software_version": "0.1.0"}))

        submitter.reset_stats()
        submitter.reset_stats()

        stats = submitter.get_stats()
        assert stats["success_count"] == 0
        assert stats["fail_count"] == 0

    @pytest.mark.asyncio
    async def test_reset_stats_does_not_clear_activity_log(self):
        """Resetting stats preserves activity log entries."""
        from src.modules.activity_log import ActivityLog

        log = ActivityLog()
        submitter = EDDNSubmitter(MockSettings(), activity_log=log)
        message = {"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}}

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        assert len(log.get_recent()) == 1  # Activity recorded

        submitter.reset_stats()

        assert len(log.get_recent()) == 1  # Still present after reset
