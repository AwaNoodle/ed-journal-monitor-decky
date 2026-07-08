"""
EDSM read-side client for public system data (stdlib urllib).

Issues GET requests to EDSM's ``api-system-v1`` endpoints.  This module is
completely separate from the write-only journal-forwarding client
(``forwarders/edsm_client.py``).  It shares only:
  - the custom User-Agent (EDSM rejects the default urllib UA behind Cloudflare)
  - ``build_ssl_context()`` for PyInstaller-safe SSL

No API key is required; the system endpoints are public.

Confirmed field naming from live EDSM responses (captured 2026-07-06):
  - ``id``: int, present if system is known to EDSM; absent/0 = unknown
  - ``bodyCount``: int or null, total bodies per honk-scan FSSDiscoveryScan
  - ``bodies``: list of body dicts submitted to EDSM
  - Per body: ``discovery`` dict ``{commander, date}`` = body has been FSS-scanned
    and submitted.  Absent/null = not yet discovered/submitted.
    There is no separate ``isMapped`` field on this endpoint.

``api-system-v1/estimated-value`` (confirmed 2026-07-07):
  - ``id``: int, present if system is known to EDSM; absent/0 = unknown
  - ``estimatedValue``: int, total scan-only value (excludes any mapping bonus) —
    used as the "floor" figure since it doesn't assume the player maps anything
  - ``estimatedValueMapped``: int, total assuming a standard mapping bonus (not
    used here — it isn't the player's personal first-mapped bonus, just a generic
    one)
  - ``valuableBodies``: list of dicts ``{bodyId, bodyName, distance, valueMax}``,
    the highest-value individual bodies in the system
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import decky

if TYPE_CHECKING:
    import ssl

from src.modules.constants import EDSM_USER_AGENT

EDSM_BODIES_URL = "https://www.edsm.net/api-system-v1/bodies"
EDSM_VALUE_URL = "https://www.edsm.net/api-system-v1/estimated-value"
DEFAULT_TIMEOUT = 15  # seconds

# Status sentinel values
STATUS_OK = "ok"
STATUS_UNKNOWN = "unknown"   # system not in EDSM
STATUS_UNAVAILABLE = "unavailable"  # network/parse error


@dataclass
class SystemBodiesResult:
    """Result of an EDSM system-bodies lookup."""

    status: str  # STATUS_OK | STATUS_UNKNOWN | STATUS_UNAVAILABLE
    system_name: str = ""
    bodies: list[dict] = field(default_factory=list)
    body_count: int | None = None  # from top-level bodyCount; None if unavailable


@dataclass
class SystemValueResult:
    """Result of an EDSM system estimated-value lookup."""

    status: str  # STATUS_OK | STATUS_UNKNOWN | STATUS_UNAVAILABLE
    system_name: str = ""
    total_value: int | None = None  # from top-level estimatedValue; None if unavailable/unknown
    valuable_bodies: list[dict] = field(default_factory=list)  # raw valuableBodies dicts


class EdsmReadClient:
    """Synchronous stdlib client for EDSM public system data.

    All errors are caught and returned as STATUS_UNAVAILABLE; nothing is raised
    into the calling path.
    """

    def __init__(
        self,
        ssl_context: ssl.SSLContext | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = EDSM_USER_AGENT,
    ) -> None:
        self._ssl_context = ssl_context
        self._timeout = timeout
        self._user_agent = user_agent

    def get_system_bodies(self, system_name: str) -> SystemBodiesResult:
        """Fetch body list for ``system_name`` from EDSM.

        Returns:
          - STATUS_OK with bodies list when EDSM has data
          - STATUS_UNKNOWN when EDSM has never seen the system
          - STATUS_UNAVAILABLE on network/timeout/non-200/malformed response
        """
        url = f"{EDSM_BODIES_URL}?{urllib.parse.urlencode({'systemName': system_name})}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self._user_agent},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            decky.logger.warning(f"EDSM bodies fetch HTTP error for {system_name!r}: {e}")
            return SystemBodiesResult(status=STATUS_UNAVAILABLE, system_name=system_name)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            decky.logger.warning(f"EDSM bodies fetch failed for {system_name!r}: {e}")
            return SystemBodiesResult(status=STATUS_UNAVAILABLE, system_name=system_name)

        return self._parse_response(system_name, data)

    def get_estimated_value(self, system_name: str) -> SystemValueResult:
        """Fetch the estimated scan value for ``system_name`` from EDSM.

        Returns:
          - STATUS_OK with total_value/valuable_bodies when EDSM has data
          - STATUS_UNKNOWN when EDSM has never seen the system
          - STATUS_UNAVAILABLE on network/timeout/non-200/malformed response
        """
        url = f"{EDSM_VALUE_URL}?{urllib.parse.urlencode({'systemName': system_name})}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self._user_agent},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_context) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            decky.logger.warning(f"EDSM estimated-value fetch HTTP error for {system_name!r}: {e}")
            return SystemValueResult(status=STATUS_UNAVAILABLE, system_name=system_name)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            decky.logger.warning(f"EDSM estimated-value fetch failed for {system_name!r}: {e}")
            return SystemValueResult(status=STATUS_UNAVAILABLE, system_name=system_name)

        return self._parse_value_response(system_name, data)

    @staticmethod
    def _parse_response(system_name: str, data: object) -> SystemBodiesResult:
        if not isinstance(data, dict):
            decky.logger.warning(f"EDSM bodies: unexpected response type for {system_name!r}")
            return SystemBodiesResult(status=STATUS_UNAVAILABLE, system_name=system_name)

        # An empty dict {} means the system is unknown to EDSM.
        if not data or not data.get("id"):
            return SystemBodiesResult(status=STATUS_UNKNOWN, system_name=system_name)

        bodies = data.get("bodies")
        if not isinstance(bodies, list):
            bodies = []

        raw_count = data.get("bodyCount")
        body_count = int(raw_count) if isinstance(raw_count, (int, float)) else None

        return SystemBodiesResult(
            status=STATUS_OK,
            system_name=system_name,
            bodies=bodies,
            body_count=body_count,
        )

    @staticmethod
    def _parse_value_response(system_name: str, data: object) -> SystemValueResult:
        if not isinstance(data, dict):
            decky.logger.warning(f"EDSM estimated-value: unexpected response type for {system_name!r}")
            return SystemValueResult(status=STATUS_UNAVAILABLE, system_name=system_name)

        # An empty dict {} means the system is unknown to EDSM.
        if not data or not data.get("id"):
            return SystemValueResult(status=STATUS_UNKNOWN, system_name=system_name)

        raw_total = data.get("estimatedValue")
        total_value = int(raw_total) if isinstance(raw_total, (int, float)) else None

        valuable_bodies = data.get("valuableBodies")
        if not isinstance(valuable_bodies, list):
            valuable_bodies = []

        return SystemValueResult(
            status=STATUS_OK,
            system_name=system_name,
            total_value=total_value,
            valuable_bodies=valuable_bodies,
        )
