"""
Tests for the stdlib EDSM API client (discard GET + journal POST).

Network is mocked at the urllib layer. Covers: discard-list parsing + retry,
required POST params, msgnum classification (1xx/2xx/5xx), per-event array
handling, and rate-limit header parsing/backoff.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.modules.forwarders.edsm_client import (
    EDSM_DISCARD_URL,
    EDSM_JOURNAL_URL,
    EdsmClient,
    rate_limit_wait_seconds,
)


def _http_response(body, headers=None):
    """Build a context-manager mock mimicking urllib's urlopen response."""
    raw = json.dumps(body).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    hdrs = headers or {}
    resp.headers = hdrs
    resp.getheader = lambda name, default=None: hdrs.get(name, default)
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@pytest.fixture
def client():
    return EdsmClient(timeout=5)


class TestDiscardList:
    def test_discard_parsed_into_set(self, client):
        events = ["Market", "Shipyard", "Music", "Fileheader"]
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(events)
            result = client.fetch_discard()
        assert result == set(events)
        # GET to the discard URL
        req = mock_open.call_args.args[0]
        assert req.full_url == EDSM_DISCARD_URL

    def test_discard_sends_user_agent(self, client):
        # EDSM is behind Cloudflare, which 403s the default urllib UA.
        events = ["Market"]
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(events)
            client.fetch_discard()
        req = mock_open.call_args.args[0]
        assert req.get_header("User-agent")  # header present and non-empty

    def test_discard_empty_returns_none(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            result = client.fetch_discard()
        assert result is None  # empty list treated as "not yet available"

    def test_discard_network_error_returns_none(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen", side_effect=OSError("boom")):
            result = client.fetch_discard()
        assert result is None


class TestPostJournal:
    def _post(self, client, **overrides):
        params = {
            "commander_name": "CmdrTest",
            "api_key": "secret-key",
            "software": "ED Journal Monitor Decky",
            "software_version": "0.4.0",
            "game_version": "4.1.0.404",
            "game_build": "r280105/r0",
            "messages": [{"timestamp": "2026-01-12T12:00:00Z", "event": "FSDJump", "StarSystem": "Sol"}],
        }
        params.update(overrides)
        return client.post_journal(**params)

    def test_post_sends_required_params(self, client):
        captured = {}

        def fake_urlopen(req, timeout=None, context=None):
            captured["url"] = req.full_url
            captured["data"] = req.data
            captured["headers"] = req.headers
            return _http_response({"msgnum": 100, "msg": "OK"})

        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen", side_effect=fake_urlopen):
            self._post(client)

        assert captured["url"] == EDSM_JOURNAL_URL
        assert captured["headers"].get("User-agent")  # Cloudflare requires a non-default UA
        from urllib.parse import parse_qs
        fields = parse_qs(captured["data"].decode("utf-8"))
        assert fields["commanderName"] == ["CmdrTest"]
        assert fields["apiKey"] == ["secret-key"]
        assert fields["fromSoftware"] == ["ED Journal Monitor Decky"]
        assert fields["fromSoftwareVersion"] == ["0.4.0"]
        assert fields["fromGameVersion"] == ["4.1.0.404"]
        assert fields["fromGameBuild"] == ["r280105/r0"]
        # message is json.dumps of the batch list
        message = json.loads(fields["message"][0])
        assert isinstance(message, list)
        assert message[0]["event"] == "FSDJump"

    def test_1xx_is_ok(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"msgnum": 100, "msg": "OK"})
            resp = self._post(client)
        assert resp.ok is True
        assert resp.fatal is False
        assert resp.transient is False
        assert resp.msgnum == 100

    def test_2xx_is_fatal_no_retry(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"msgnum": 203, "msg": "Commander name/API Key not found."})
            resp = self._post(client)
        assert resp.ok is False
        assert resp.fatal is True
        assert resp.transient is False
        assert resp.msgnum == 203

    def test_5xx_is_transient_retry(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"msgnum": 500, "msg": "Exception"})
            resp = self._post(client)
        assert resp.ok is False
        assert resp.fatal is False
        assert resp.transient is True

    def test_network_error_is_transient(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen", side_effect=OSError("boom")):
            resp = self._post(client)
        assert resp.ok is False
        assert resp.transient is True

    def test_per_event_array_handled_defensively(self, client):
        body = {
            "msgnum": 100,
            "msg": "OK",
            "events": [
                {"msgnum": 100, "msg": "OK"},
                {"msgnum": 304, "msg": "Discarded event"},
            ],
        }
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(body)
            resp = self._post(client)
        assert resp.ok is True
        assert len(resp.events) == 2
        assert resp.events[1]["msgnum"] == 304

    def test_missing_per_event_array_is_safe(self, client):
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"msgnum": 100, "msg": "OK"})
            resp = self._post(client)
        assert resp.events == []

    def test_rate_limit_headers_parsed(self, client):
        headers = {"X-Rate-Limit-Remaining": "0", "X-Rate-Limit-Reset": "1893456000"}
        with patch("src.modules.forwarders.edsm_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"msgnum": 100, "msg": "OK"}, headers=headers)
            resp = self._post(client)
        assert resp.rate_limit_remaining == 0
        assert resp.rate_limit_reset == 1893456000


class TestRateLimitBackoff:
    def test_wait_until_reset_when_exhausted(self):
        resp = MagicMock()
        resp.rate_limit_remaining = 0
        resp.rate_limit_reset = 1000
        assert rate_limit_wait_seconds(resp, now=940) == 60

    def test_no_wait_when_quota_remains(self):
        resp = MagicMock()
        resp.rate_limit_remaining = 5
        resp.rate_limit_reset = 1000
        assert rate_limit_wait_seconds(resp, now=940) == 0

    def test_no_wait_when_reset_in_past(self):
        resp = MagicMock()
        resp.rate_limit_remaining = 0
        resp.rate_limit_reset = 900
        assert rate_limit_wait_seconds(resp, now=940) == 0

    def test_no_wait_when_headers_absent(self):
        resp = MagicMock()
        resp.rate_limit_remaining = None
        resp.rate_limit_reset = None
        assert rate_limit_wait_seconds(resp, now=940) == 0
