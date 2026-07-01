"""
Tests for the shared SSL context builder.

Verifies the helper lives in its own module and that the EDDN submitter builds
its SSL context via the shared helper (EDDN behavior unchanged after the lift).
"""

from unittest.mock import MagicMock, patch

from conftest import MockSettings

from src.modules import ssl_context
from src.modules.ssl_context import build_ssl_context
from src.modules.submitter import EDDNSubmitter


def test_shared_helper_exists_and_returns_context():
    ctx = ssl_context.build_ssl_context()
    assert ctx is not None


class TestSSLContextBuilder:
    """Tests for SSL context construction (PyInstaller/Decky fix)."""

    def test_env_var_takes_priority(self):
        """SSL_CERT_FILE env var takes priority over other sources."""
        with patch.dict("os.environ", {"SSL_CERT_FILE": "/custom/ca.pem"}), \
             patch("src.modules.ssl_context.Path") as mock_path:
            mock_path.return_value.is_file.return_value = True
            with patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                build_ssl_context()
            mock_create.assert_called_once_with(cafile="/custom/ca.pem")

    def test_certifi_used_when_no_env_var(self):
        """certifi bundle is used when SSL_CERT_FILE is not set."""
        mock_certifi = MagicMock()
        mock_certifi.where.return_value = "/tmp/_MEI/certifi/cacert.pem"
        with patch.dict("os.environ", {}, clear=True), \
             patch.dict("sys.modules", {"certifi": mock_certifi}), \
             patch("src.modules.ssl_context.Path") as mock_path:
            mock_path.return_value.is_file.return_value = True
            with patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                build_ssl_context()
            mock_create.assert_called_once_with(cafile="/tmp/_MEI/certifi/cacert.pem")

    def test_system_ca_used_when_certifi_missing(self):
        """System CA bundle is used when certifi is not available."""
        original_import = __import__
        certifi_block_count = 0

        def blocking_import(name, *args, **kwargs):
            nonlocal certifi_block_count
            if name == "certifi":
                certifi_block_count += 1
                raise ImportError("certifi")
            return original_import(name, *args, **kwargs)

        with patch.dict("os.environ", {}, clear=True), \
             patch("src.modules.ssl_context._SYSTEM_CA_PATHS", ["/etc/ssl/cert.pem"]), \
             patch("src.modules.ssl_context.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = True
            mock_path.return_value = mock_path_instance
            with patch("builtins.__import__", side_effect=blocking_import), \
                 patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                build_ssl_context()
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
             patch("src.modules.ssl_context._SYSTEM_CA_PATHS", []), \
             patch("src.modules.ssl_context.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.is_file.return_value = False
            mock_path.return_value = mock_path_instance
            with patch("builtins.__import__", side_effect=blocking_import), \
                 patch("ssl.create_default_context") as mock_create:
                mock_create.return_value = MagicMock()
                build_ssl_context()
            mock_create.assert_called_once_with()


def test_eddn_submitter_uses_shared_helper():
    """EDDNSubmitter builds its SSL context via the shared helper."""
    sentinel = object()
    with patch("src.modules.submitter.build_ssl_context", return_value=sentinel) as mock_build:
        submitter = EDDNSubmitter(MockSettings(initial_data={"uploader_id": "x"}))

    mock_build.assert_called_once()
    assert submitter._ssl_context is sentinel


def test_submitter_reexports_shared_helper():
    """The legacy name still resolves to the shared helper."""
    from src.modules.submitter import _build_ssl_context

    assert _build_ssl_context is ssl_context.build_ssl_context
