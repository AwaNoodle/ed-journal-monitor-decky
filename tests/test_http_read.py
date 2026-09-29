"""
Tests for the bounded HTTP body reader shared by every outbound client.

Covers the byte cap itself: what is accepted, what is rejected, and that an
over-sized body is never fully pulled into memory.
"""

import pytest

from src.modules.constants import MAX_HTTP_RESPONSE_BYTES
from src.modules.http_read import ResponseTooLargeError, read_capped_body


class FakeResponse:
    """Records the requested read size and honours it, like a real socket read."""

    def __init__(self, body):
        self.body = body
        self.requested = None

    def read(self, amt=None):
        self.requested = amt
        return self.body if amt is None else self.body[:amt]


class TestReadCappedBody:
    def test_body_under_cap_returned_whole(self):
        resp = FakeResponse(b'{"msgnum": 100}')
        assert read_capped_body(resp, max_bytes=1024) == b'{"msgnum": 100}'

    def test_body_exactly_at_cap_accepted(self):
        resp = FakeResponse(b"x" * 1024)
        assert read_capped_body(resp, max_bytes=1024) == b"x" * 1024

    def test_body_one_byte_over_cap_rejected(self):
        resp = FakeResponse(b"x" * 1025)
        with pytest.raises(ResponseTooLargeError):
            read_capped_body(resp, max_bytes=1024)

    def test_never_reads_more_than_cap_plus_one(self):
        """The point of the cap: a multi-GB body must not be pulled into memory."""
        resp = FakeResponse(b"x" * 5000)
        with pytest.raises(ResponseTooLargeError):
            read_capped_body(resp, max_bytes=1024)
        assert resp.requested == 1025

    def test_default_cap_is_the_shared_constant(self):
        resp = FakeResponse(b"")
        read_capped_body(resp)
        assert resp.requested == MAX_HTTP_RESPONSE_BYTES + 1

    def test_too_large_is_a_value_error(self):
        """Callers already funnel ValueError-ish parse failures into their failure path."""
        assert issubclass(ResponseTooLargeError, ValueError)
