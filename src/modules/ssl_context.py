from __future__ import annotations

"""
Shared SSL context builder.

Decky Loader embeds Python 3.11 via PyInstaller. The bundled Python's default
SSL context may not find system CA certificates because its compiled-in cert
paths don't match the host filesystem layout, causing
[SSL: CERTIFICATE_VERIFY_FAILED] on every HTTPS request.

This helper builds an SSL context with an explicit CA bundle cascade so every
HTTPS client in the plugin (EDDN submitter, EDSM forwarder, ...) shares the same
fix. EDDN behavior is byte-for-byte unchanged — this is the same function, moved
out of ``submitter.py`` into a shared home.
"""

import os
import ssl
from pathlib import Path

import decky

# Known system CA bundle paths (Steam Deck / Arch Linux)
_SYSTEM_CA_PATHS = [
    "/etc/ssl/cert.pem",  # Arch/SteamOS (ca-certificates)
    "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/Fedora
]


def build_ssl_context() -> ssl.SSLContext:
    """
    Build an SSL context with a CA bundle that works in PyInstaller environments.

    We load a CA bundle from, in order:
    1. The SSL_CERT_FILE env var (if set)
    2. certifi's bundle (if the package is available)
    3. Known system CA bundle paths
    4. Fallback to default context (will likely fail on Decky)
    """
    # 1. Honour explicit env override
    env_cert = os.environ.get("SSL_CERT_FILE")
    if env_cert and Path(env_cert).is_file():
        ctx = ssl.create_default_context(cafile=env_cert)
        decky.logger.info(f"SSL context using SSL_CERT_FILE: {env_cert}")
        return ctx

    # 2. Try certifi (bundled with Decky Loader's PyInstaller package)
    try:
        import certifi  # type: ignore[import-untyped]  # noqa: PLC0415

        certifi_path = certifi.where()
        if Path(certifi_path).is_file():
            ctx = ssl.create_default_context(cafile=certifi_path)
            decky.logger.info(f"SSL context using certifi bundle: {certifi_path}")
            return ctx
    except ImportError:
        pass

    # 3. Try known system paths
    for ca_path in _SYSTEM_CA_PATHS:
        if Path(ca_path).is_file():
            ctx = ssl.create_default_context(cafile=ca_path)
            decky.logger.info(f"SSL context using system CA bundle: {ca_path}")
            return ctx

    # 4. Fallback
    decky.logger.warning("No CA bundle found; using default SSL context (may fail)")
    return ssl.create_default_context()
