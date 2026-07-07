"""
Tests for the per-system TTL cache used by the EDSM lookup path.

Covers: cache hit (no new request), cache miss after TTL expiry,
and basic set/get round-trip.
"""

import time
from unittest.mock import patch

from src.modules.edsm_read_client import STATUS_OK, STATUS_UNKNOWN, SystemBodiesResult
from src.modules.edsm_system_cache import SystemLookupCache


def _ok_result(system_name: str) -> SystemBodiesResult:
    return SystemBodiesResult(status=STATUS_OK, system_name=system_name, bodies=[], body_count=0)


def _unknown_result(system_name: str) -> SystemBodiesResult:
    return SystemBodiesResult(status=STATUS_UNKNOWN, system_name=system_name)


class TestCacheHit:
    def test_get_returns_cached_result_within_ttl(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        result = _ok_result("Sol")
        cache.set("Sol", result)
        assert cache.get("Sol") is result

    def test_cache_hit_does_not_expire_within_ttl(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        result = _ok_result("Beagle Point")
        cache.set("Beagle Point", result)
        # Simulate time passing but still within TTL
        with patch("src.modules.edsm_system_cache.time.monotonic", return_value=time.monotonic() + 3599):
            assert cache.get("Beagle Point") is result

    def test_cache_stores_unknown_result(self):
        """Unknown-system results should also be cached to avoid repeat requests."""
        cache = SystemLookupCache(ttl_seconds=3600)
        result = _unknown_result("Random XYZ")
        cache.set("Random XYZ", result)
        assert cache.get("Random XYZ") is result


class TestCacheMiss:
    def test_get_returns_none_for_unknown_key(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        assert cache.get("Nonexistent System") is None

    def test_get_returns_none_after_ttl_expiry(self):
        cache = SystemLookupCache(ttl_seconds=60)
        result = _ok_result("Sol")
        cache.set("Sol", result)
        # Simulate time past the TTL
        with patch("src.modules.edsm_system_cache.time.monotonic", return_value=time.monotonic() + 61):
            assert cache.get("Sol") is None

    def test_miss_after_expiry_evicts_stale_entry(self):
        """After expiry, the stale entry should be gone (no resurrection on re-check)."""
        cache = SystemLookupCache(ttl_seconds=60)
        cache.set("Sol", _ok_result("Sol"))
        future = time.monotonic() + 61
        with patch("src.modules.edsm_system_cache.time.monotonic", return_value=future):
            cache.get("Sol")  # triggers eviction
            assert cache.get("Sol") is None


class TestCacheOverwrite:
    def test_set_overwrites_existing_entry(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        old_result = _ok_result("Sol")
        new_result = _ok_result("Sol")
        cache.set("Sol", old_result)
        cache.set("Sol", new_result)
        assert cache.get("Sol") is new_result

    def test_independent_entries_per_system(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        r_sol = _ok_result("Sol")
        r_maia = _ok_result("Maia")
        cache.set("Sol", r_sol)
        cache.set("Maia", r_maia)
        assert cache.get("Sol") is r_sol
        assert cache.get("Maia") is r_maia


def test_module_docstring_is_accessible():
    import src.modules.edsm_system_cache as m
    assert m.__doc__ is not None
    assert "TTL" in m.__doc__
