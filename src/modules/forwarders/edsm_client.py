from __future__ import annotations

"""
EDSM journal API client (stdlib urllib).

Two endpoints:
  - GET  https://www.edsm.net/api-journal-v1/discard  → public JSON array of
    event names the server refuses (used as a client-side filter).
  - POST https://www.edsm.net/api-journal-v1          → submit one or a batch of
    raw journal events under the commander's own credentials.

Responses carry a numeric ``msgnum`` classified by hundreds digit:
  1xx OK · 2xx fatal request error (no retry) · 5xx server error (transient).
Rate-limit headers (``X-Rate-Limit-Remaining`` / ``X-Rate-Limit-Reset``) are
parsed so the caller can back off when the quota is exhausted.

The raw journal lines are sent verbatim (no EDDN transform). The SSL context is
the shared PyInstaller-safe cascade (see ``ssl_context``).
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    import ssl
    from collections.abc import Sequence

EDSM_JOURNAL_URL = "https://www.edsm.net/api-journal-v1"
EDSM_DISCARD_URL = "https://www.edsm.net/api-journal-v1/discard"
DEFAULT_TIMEOUT = 20  # seconds (matches EDMC)
# EDSM sits behind Cloudflare, which rejects the default Python-urllib
# User-Agent with HTTP 403. A non-default, identifiable UA is required.
DEFAULT_USER_AGENT = "ed-journal-monitor-decky"

# msgnum response classes (hundreds digit) and HTTP boundaries.
_MSGNUM_OK_CLASS = 1  # 1xx — accepted
_MSGNUM_FATAL_CLASS = 2  # 2xx — bad creds/software/Legacy; do not retry
_MSGNUM_SERVER_CLASS = 5  # 5xx — server exception; transient/retry
_HTTP_SERVER_ERROR_MIN = 500


@dataclass
class EdsmResponse:
    """Outcome of an EDSM journal POST."""

    msgnum: int | None = None
    msg: str = ""
    events: list[dict] = field(default_factory=list)
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None
    ok: bool = False  # 1xx
    fatal: bool = False  # 2xx — bad creds/software/Legacy; do not retry
    transient: bool = False  # 5xx or network error — retry with backoff


def _classify(response: EdsmResponse) -> None:
    """Set ok/fatal/transient flags from the top-level msgnum (hundreds digit)."""
    num = response.msgnum
    if num is None:
        return
    hundreds = num // 100
    if hundreds == _MSGNUM_OK_CLASS:
        response.ok = True
    elif hundreds == _MSGNUM_FATAL_CLASS:
        response.fatal = True
    elif hundreds >= _MSGNUM_SERVER_CLASS:
        response.transient = True
    # 3xx/4xx only appear per-event, not at the top level; if seen here, leave
    # all flags False (non-OK, non-retried) and let the caller surface msg.


def rate_limit_wait_seconds(response: EdsmResponse, now: float | None = None) -> float:
    """Seconds to wait before the next request given rate-limit headers.

    Returns the time until reset when the remaining quota is 0, else 0.
    """
    if response.rate_limit_remaining is None or response.rate_limit_reset is None:
        return 0
    if response.rate_limit_remaining > 0:
        return 0
    now = time.time() if now is None else now
    return max(0, response.rate_limit_reset - now)


class EdsmClient:
    """Synchronous stdlib client for the EDSM journal API."""

    def __init__(
        self,
        ssl_context: ssl.SSLContext | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._user_agent = user_agent

    def fetch_discard(self) -> set[str] | None:
        """Fetch the discard list. Returns a set of event names, or None on
        failure / empty response (caller should retry)."""
        try:
            req = urllib.request.Request(
                EDSM_DISCARD_URL, headers={"User-Agent": self._user_agent}, method="GET"
            )
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            decky.logger.warning(f"EDSM discard fetch failed: {e}")
            return None
        if not isinstance(data, list) or not data:
            return None
        return {str(name) for name in data}

    def post_journal(
        self,
        *,
        commander_name: str,
        api_key: str,
        software: str,
        software_version: str,
        game_version: str,
        game_build: str,
        messages: Sequence[dict],
    ) -> EdsmResponse:
        """POST a batch of raw journal events to EDSM. Always returns an
        EdsmResponse (transient=True on network error)."""
        payload = urllib.parse.urlencode(
            {
                "commanderName": commander_name,
                "apiKey": api_key,
                "fromSoftware": software,
                "fromSoftwareVersion": software_version,
                "fromGameVersion": game_version,
                "fromGameBuild": game_build,
                "message": json.dumps(list(messages), ensure_ascii=False),
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                EDSM_JOURNAL_URL,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self._user_agent,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                response = self._parse_body(body)
                self._parse_rate_limit(resp, response)
        except urllib.error.HTTPError as e:
            # HTTP-level error (5xx server / 4xx). Treat 5xx as transient.
            response = EdsmResponse(msg=str(e))
            response.transient = e.code >= _HTTP_SERVER_ERROR_MIN
            return response
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            decky.logger.warning(f"EDSM journal POST failed: {e}")
            return EdsmResponse(msg=str(e), transient=True)

        return response

    @staticmethod
    def _parse_body(body: dict) -> EdsmResponse:
        response = EdsmResponse()
        if isinstance(body, dict):
            num = body.get("msgnum")
            response.msgnum = int(num) if isinstance(num, (int, float)) else None
            response.msg = str(body.get("msg", ""))
            events = body.get("events")
            if isinstance(events, list):
                response.events = [e for e in events if isinstance(e, dict)]
        _classify(response)
        return response

    @staticmethod
    def _parse_rate_limit(resp: object, response: EdsmResponse) -> None:
        getheader = getattr(resp, "getheader", None)
        if not callable(getheader):
            return
        remaining = getheader("X-Rate-Limit-Remaining", None)
        reset = getheader("X-Rate-Limit-Reset", None)
        try:
            response.rate_limit_remaining = int(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            response.rate_limit_remaining = None
        try:
            response.rate_limit_reset = int(reset) if reset is not None else None
        except (TypeError, ValueError):
            response.rate_limit_reset = None
