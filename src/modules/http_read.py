"""
Bounded HTTP response reading.

Every outbound request in the plugin (EDDN submission, EDSM journal POST,
EDSM read endpoints) reads its response body through :func:`read_capped_body`
so that a misbehaving or hostile endpoint cannot exhaust memory on a handheld.
TLS is verified, so the only party that can send a multi-gigabyte body is the
genuine endpoint or whoever has compromised it — the cap is a memory bound, not
an authenticity check.

An over-sized body is rejected outright rather than truncated: a truncated JSON
document would fail to parse anyway, and every caller already has a failure
path for an unusable response.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.modules.constants import MAX_HTTP_RESPONSE_BYTES

if TYPE_CHECKING:
    from typing import Protocol

    class SupportsRead(Protocol):
        """Minimal reader interface satisfied by urllib responses and HTTPError."""

        def read(self, amt: int = ...) -> bytes: ...


class ResponseTooLargeError(ValueError):
    """Raised when a response body exceeds the configured byte cap."""


def read_capped_body(resp: SupportsRead, max_bytes: int = MAX_HTTP_RESPONSE_BYTES) -> bytes:
    """Read at most ``max_bytes`` from ``resp``, raising if the body is larger.

    Reads one byte past the cap so an over-sized body is detectable without
    ever holding more than ``max_bytes + 1`` bytes in memory.
    """
    body = resp.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ResponseTooLargeError(f"response body exceeds {max_bytes} bytes")
    return body
