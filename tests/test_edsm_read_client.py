"""
Tests for the EDSM read-side client (api-system-v1/bodies GET).

Network is mocked at the urllib layer.  Covers: known-system fetch, unknown
system, and all contained-failure scenarios (network error, timeout, non-200,
malformed response).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.modules.edsm_read_client import (
    DEFAULT_SPHERE_RADIUS,
    EDSM_BODIES_URL,
    EDSM_SPHERE_URL,
    EDSM_VALUE_URL,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    EdsmReadClient,
)


def _http_response(body, status=200):
    """Build a context-manager mock mimicking urllib's urlopen response."""
    raw = json.dumps(body).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@pytest.fixture
def client():
    return EdsmReadClient(timeout=5)


@pytest.fixture
def known_bodies_fixture(load_fixture):
    return load_fixture("edsm_bodies_known.json")


@pytest.fixture
def known_value_fixture(load_fixture):
    return load_fixture("edsm_estimated_value_known.json")


@pytest.fixture
def sphere_systems_fixture(load_fixture):
    return load_fixture("edsm_sphere_systems_known.json")


class TestGetSystemBodies:
    def test_known_system_returns_ok_with_bodies(self, client, known_bodies_fixture):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(known_bodies_fixture)
            result = client.get_system_bodies("Wolf 359")
        assert result.status == STATUS_OK
        assert len(result.bodies) == 3
        assert result.body_count == 3
        assert result.system_name == "Wolf 359"

    def test_sends_custom_user_agent(self, client):
        """EDSM sits behind Cloudflare — a custom UA is required to avoid 403."""
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "bodyCount": 0, "bodies": []})
            client.get_system_bodies("Sol")
        req = mock_open.call_args.args[0]
        assert req.get_header("User-agent")

    def test_url_contains_system_name(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "bodyCount": 0, "bodies": []})
            client.get_system_bodies("Wolf 359")
        req = mock_open.call_args.args[0]
        assert "Wolf+359" in req.full_url or "Wolf%20359" in req.full_url
        assert EDSM_BODIES_URL in req.full_url

    def test_uses_ssl_context_from_constructor(self):
        """SSL context is passed through to urlopen — needed for PyInstaller CA cascade."""
        import ssl
        ctx = ssl.create_default_context()
        client = EdsmReadClient(ssl_context=ctx, timeout=5)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "bodyCount": 0, "bodies": []})
            client.get_system_bodies("Sol")
        _args, kwargs = mock_open.call_args
        assert kwargs.get("context") is ctx

    def test_no_api_key_required(self, client, known_bodies_fixture):
        """Read client must work without any API key dependency."""
        captured = {}
        def fake_urlopen(req, timeout=None, context=None):
            captured["req"] = req
            return _http_response(known_bodies_fixture)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.get_system_bodies("Wolf 359")
        assert result.status == STATUS_OK
        # No apiKey or commanderName in the request
        assert "apiKey" not in captured["req"].full_url
        assert "commanderName" not in captured["req"].full_url


class TestUnknownSystem:
    def test_empty_dict_is_unknown(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({})
            result = client.get_system_bodies("Unexplored System XYZ")
        assert result.status == STATUS_UNKNOWN
        assert result.bodies == []
        assert result.system_name == "Unexplored System XYZ"

    def test_missing_id_is_unknown(self, client):
        """EDSM returns {} for systems it doesn't know; id=0 is also treated as unknown."""
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 0, "bodyCount": 0, "bodies": []})
            result = client.get_system_bodies("New System")
        assert result.status == STATUS_UNKNOWN


class TestContainedFailures:
    """All failure modes must return STATUS_UNAVAILABLE without raising."""

    def test_network_error_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=OSError("Network error")):
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE
        assert result.system_name == "Sol"

    def test_timeout_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_200_http_error_is_unavailable(self, client):
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(url="", code=503, msg="Service Unavailable", hdrs=None, fp=None),
        ):
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_malformed_json_is_unavailable(self, client):
        resp = MagicMock()
        resp.read.return_value = b"not json{"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", return_value=resp):
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_dict_response_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])  # list instead of dict
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_url_error_is_unavailable(self, client):
        """URLError (e.g. DNS failure) must be contained."""
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Name or service not known"),
        ):
            result = client.get_system_bodies("Sol")
        assert result.status == STATUS_UNAVAILABLE


class TestGetEstimatedValue:
    """Tests for the api-system-v1/estimated-value GET (system value lookup)."""

    def test_known_system_returns_ok_with_value(self, client, known_value_fixture):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(known_value_fixture)
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_OK
        assert result.system_name == "Sol"
        assert result.total_value == 605867
        assert len(result.valuable_bodies) == 2
        assert result.valuable_bodies[0]["bodyName"] == "Earth"
        assert result.valuable_bodies[0]["valueMax"] == 945428

    def test_sends_custom_user_agent(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "estimatedValue": 0, "valuableBodies": []})
            client.get_estimated_value("Sol")
        req = mock_open.call_args.args[0]
        assert req.get_header("User-agent")

    def test_url_contains_system_name(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "estimatedValue": 0, "valuableBodies": []})
            client.get_estimated_value("Wolf 359")
        req = mock_open.call_args.args[0]
        assert "Wolf+359" in req.full_url or "Wolf%20359" in req.full_url
        assert EDSM_VALUE_URL in req.full_url

    def test_uses_ssl_context_from_constructor(self):
        import ssl
        ctx = ssl.create_default_context()
        client = EdsmReadClient(ssl_context=ctx, timeout=5)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 1, "estimatedValue": 0, "valuableBodies": []})
            client.get_estimated_value("Sol")
        _args, kwargs = mock_open.call_args
        assert kwargs.get("context") is ctx

    def test_no_api_key_required(self, client, known_value_fixture):
        captured = {}
        def fake_urlopen(req, timeout=None, context=None):
            captured["req"] = req
            return _http_response(known_value_fixture)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_OK
        assert "apiKey" not in captured["req"].full_url
        assert "commanderName" not in captured["req"].full_url


class TestEstimatedValueUnknownSystem:
    def test_empty_dict_is_unknown(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({})
            result = client.get_estimated_value("Unexplored System XYZ")
        assert result.status == STATUS_UNKNOWN
        assert result.total_value is None
        assert result.valuable_bodies == []

    def test_missing_id_is_unknown(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({"id": 0, "estimatedValue": 0, "valuableBodies": []})
            result = client.get_estimated_value("New System")
        assert result.status == STATUS_UNKNOWN


class TestEstimatedValueNoValuableBodies:
    def test_known_system_with_no_valuable_bodies(self, client):
        """A system EDSM knows about but with no standout bodies still reports a total."""
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({
                "id": 7, "name": "Wolf 359",
                "estimatedValue": 2205, "estimatedValueMapped": 3796,
                "valuableBodies": [],
            })
            result = client.get_estimated_value("Wolf 359")
        assert result.status == STATUS_OK
        assert result.total_value == 2205
        assert result.valuable_bodies == []


class TestEstimatedValueContainedFailures:
    """All failure modes must return STATUS_UNAVAILABLE without raising."""

    def test_network_error_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=OSError("Network error")):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE
        assert result.system_name == "Sol"

    def test_timeout_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_200_http_error_is_unavailable(self, client):
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(url="", code=503, msg="Service Unavailable", hdrs=None, fp=None),
        ):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_malformed_json_is_unavailable(self, client):
        resp = MagicMock()
        resp.read.return_value = b"not json{"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", return_value=resp):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_dict_response_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_url_error_is_unavailable(self, client):
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Name or service not known"),
        ):
            result = client.get_estimated_value("Sol")
        assert result.status == STATUS_UNAVAILABLE


class TestGetSphereSystems:
    """Tests for the api-v1/sphere-systems GET (nearby systems + primary star)."""

    def test_known_system_returns_ok_with_systems(self, client, sphere_systems_fixture):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(sphere_systems_fixture)
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_OK
        assert result.system_name == "Sol"
        assert len(result.systems) == len(sphere_systems_fixture)
        assert result.systems[1]["name"] == "Barnard's Star"
        assert result.systems[1]["primaryStar"]["isScoopable"] is True

    def test_sends_custom_user_agent(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            client.get_sphere_systems("Sol")
        req = mock_open.call_args.args[0]
        assert req.get_header("User-agent")

    def test_url_contains_system_name_radius_and_primary_star_flag(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            client.get_sphere_systems("Wolf 359")
        req = mock_open.call_args.args[0]
        assert "Wolf+359" in req.full_url or "Wolf%20359" in req.full_url
        assert EDSM_SPHERE_URL in req.full_url
        assert f"radius={DEFAULT_SPHERE_RADIUS}" in req.full_url
        assert "showPrimaryStar=1" in req.full_url

    def test_custom_radius_overrides_default(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            client.get_sphere_systems("Sol", radius=10)
        req = mock_open.call_args.args[0]
        assert "radius=10" in req.full_url

    def test_uses_ssl_context_from_constructor(self):
        import ssl
        ctx = ssl.create_default_context()
        client = EdsmReadClient(ssl_context=ctx, timeout=5)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response([])
            client.get_sphere_systems("Sol")
        _args, kwargs = mock_open.call_args
        assert kwargs.get("context") is ctx

    def test_no_api_key_required(self, client, sphere_systems_fixture):
        captured = {}
        def fake_urlopen(req, timeout=None, context=None):
            captured["req"] = req
            return _http_response(sphere_systems_fixture)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_OK
        assert "apiKey" not in captured["req"].full_url
        assert "commanderName" not in captured["req"].full_url


class TestSphereSystemsUnknownSystem:
    def test_empty_dict_is_unknown(self, client):
        """EDSM returns {} when the queried system itself isn't known to it."""
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response({})
            result = client.get_sphere_systems("Unexplored System XYZ")
        assert result.status == STATUS_UNKNOWN
        assert result.systems == []


class TestSphereSystemsContainedFailures:
    """All failure modes must return STATUS_UNAVAILABLE without raising."""

    def test_network_error_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=OSError("Network error")):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE
        assert result.system_name == "Sol"

    def test_timeout_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_200_http_error_is_unavailable(self, client):
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(url="", code=503, msg="Service Unavailable", hdrs=None, fp=None),
        ):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_malformed_json_is_unavailable(self, client):
        resp = MagicMock()
        resp.read.return_value = b"not json{"
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        with patch("src.modules.edsm_read_client.urllib.request.urlopen", return_value=resp):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_non_list_non_dict_response_is_unavailable(self, client):
        with patch("src.modules.edsm_read_client.urllib.request.urlopen") as mock_open:
            mock_open.return_value = _http_response(42)
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE

    def test_url_error_is_unavailable(self, client):
        import urllib.error
        with patch(
            "src.modules.edsm_read_client.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Name or service not known"),
        ):
            result = client.get_sphere_systems("Sol")
        assert result.status == STATUS_UNAVAILABLE
