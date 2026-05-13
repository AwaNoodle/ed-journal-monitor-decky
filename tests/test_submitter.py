"""
Tests for the EDDNSubmitter module.
Tests message construction, retry logic, and SSL context with mocked HTTP.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from src.modules.submitter import EDDN_URL, MAX_RETRIES, EDDNSubmitter, _build_ssl_context


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
        assert "gatewayTimestamp" in message["header"]

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

    @pytest.mark.asyncio
    async def test_get_stats_includes_last_upload_event(self):
        submitter = EDDNSubmitter(MockSettings())
        message = {"$schemaRef": "", "header": {}, "message": {"event": "Docked"}}

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
        assert stats["last_upload_event"] == "Docked"


class TestSSLContext:
    """Tests for SSL context construction (PyInstaller/Decky fix)."""

    def test_env_var_takes_priority(self):
        """SSL_CERT_FILE env var takes priority over other sources."""
        with patch.dict("os.environ", {"SSL_CERT_FILE": "/custom/ca.pem"}), \
             patch("src.modules.submitter.Path") as mock_path:
            mock_path.return_value.is_file.return_value = True
            with patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                _build_ssl_context()
            mock_create.assert_called_once_with(cafile="/custom/ca.pem")

    def test_certifi_used_when_no_env_var(self):
        """certifi bundle is used when SSL_CERT_FILE is not set."""
        mock_certifi = MagicMock()
        mock_certifi.where.return_value = "/tmp/_MEI/certifi/cacert.pem"
        with patch.dict("os.environ", {}, clear=True), \
             patch.dict("sys.modules", {"certifi": mock_certifi}), \
             patch("src.modules.submitter.Path") as mock_path:
            mock_path.return_value.is_file.return_value = True
            with patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                _build_ssl_context()
            mock_create.assert_called_once_with(cafile="/tmp/_MEI/certifi/cacert.pem")

    def test_system_ca_used_when_certifi_missing(self):
        """System CA bundle is used when certifi is not available."""
        # Simulate ImportError for certifi by making the try/except catch it
        original_import = __import__
        certifi_block_count = 0

        def blocking_import(name, *args, **kwargs):
            nonlocal certifi_block_count
            if name == "certifi":
                certifi_block_count += 1
                raise ImportError("certifi")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", {}, clear=True), \
             patch("src.modules.submitter._SYSTEM_CA_PATHS", ["/etc/ssl/cert.pem"]), \
             patch("src.modules.submitter.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = True
            mock_path.return_value = mock_path_instance
            with patch("builtins.__import__", side_effect=blocking_import), \
                 patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                _build_ssl_context()
            mock_create.assert_called_once_with(cafile="/etc/ssl/cert.pem")
        assert certifi_block_count > 0  # certifi was attempted and blocked

    def test_default_context_when_nothing_found(self):
        """Returns default context when no CA bundle is available."""
        original_import = __import__

        def blocking_import(name, *args, **kwargs):
            if name == "certifi":
                raise ImportError("certifi")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", {}, clear=True), \
             patch("src.modules.submitter._SYSTEM_CA_PATHS", []), \
             patch("src.modules.submitter.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = False
            mock_path.return_value = mock_path_instance
            with patch("builtins.__import__", side_effect=blocking_import), \
                 patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                _build_ssl_context()
            # Should be called with no cafile (default context)
            mock_create.assert_called_once_with()

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

    @pytest.mark.asyncio
    async def test_event_name_override_used_in_stats(self):
        submitter = EDDNSubmitter(MockSettings())
        message = {
            "$schemaRef": "https://eddn.edcd.io/schemas/outfitting/2",
            "header": {},
            "message": {"systemName": "Sol", "stationName": "Test", "modules": []},
        }

        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message, event_name="Outfitting")

        stats = submitter.get_stats()
        assert stats["last_upload_event"] == "Outfitting"  # Not "unknown"

    @pytest.mark.asyncio
    async def test_event_name_defaults_to_message_event(self, submitter):
        """When event_name is not provided, it falls back to message['event']."""
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

            with patch("src.modules.submitter.decky") as mock_decky:
                mock_decky.emit = AsyncMock()
                await submitter.submit(message)

        stats = submitter.get_stats()
        assert stats["last_upload_event"] == "FSDJump"


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
