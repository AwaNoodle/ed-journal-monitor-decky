"""
Tests for the per-system TTL cache used by the EDSM lookup path.

Covers: cache hit (no new request), cache miss after TTL expiry,
basic set/get round-trip, and the LRU entry cap.
"""

import time
from unittest.mock import patch

from src.modules.constants import MAX_SYSTEM_CACHE_ENTRIES
from src.modules.edsm_read_client import (
    STATUS_OK,
    STATUS_UNKNOWN,
    SystemBodiesResult,
    SystemValueResult,
)
from src.modules.edsm_system_cache import SystemLookupCache


def _ok_result(system_name: str) -> SystemBodiesResult:
    return SystemBodiesResult(status=STATUS_OK, system_name=system_name, bodies=[], body_count=0)


def _unknown_result(system_name: str) -> SystemBodiesResult:
    return SystemBodiesResult(status=STATUS_UNKNOWN, system_name=system_name)


def _ok_value_result(system_name: str) -> SystemValueResult:
    return SystemValueResult(status=STATUS_OK, system_name=system_name, total_value=1000, valuable_bodies=[])


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


class TestValueCache:
    """The value cache is a parallel store on the same instance/TTL as bodies."""

    def test_get_value_returns_cached_result_within_ttl(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        result = _ok_value_result("Sol")
        cache.set_value("Sol", result)
        assert cache.get_value("Sol") is result

    def test_get_value_returns_none_for_unknown_key(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        assert cache.get_value("Nonexistent System") is None

    def test_get_value_returns_none_after_ttl_expiry(self):
        cache = SystemLookupCache(ttl_seconds=60)
        result = _ok_value_result("Sol")
        cache.set_value("Sol", result)
        with patch("src.modules.edsm_system_cache.time.monotonic", return_value=time.monotonic() + 61):
            assert cache.get_value("Sol") is None

    def test_value_cache_independent_of_bodies_cache(self):
        """Bodies and value entries for the same system are stored independently."""
        cache = SystemLookupCache(ttl_seconds=3600)
        cache.set("Sol", _ok_result("Sol"))
        assert cache.get_value("Sol") is None

    def test_clear_discards_value_entries(self):
        cache = SystemLookupCache(ttl_seconds=3600)
        cache.set_value("Sol", _ok_value_result("Sol"))
        cache.clear()
        assert cache.get_value("Sol") is None


class TestEntryCap:
    """Each store is bounded: a long route must not grow the cache without limit."""

    def test_default_cap_is_the_shared_constant(self):
        cache = SystemLookupCache()
        for i in range(MAX_SYSTEM_CACHE_ENTRIES + 10):
            cache.set(f"System {i}", _ok_result(f"System {i}"))
        assert len(cache._store) == MAX_SYSTEM_CACHE_ENTRIES

    def test_insert_past_cap_evicts_least_recently_used(self):
        cache = SystemLookupCache(ttl_seconds=3600, max_entries=3)
        for name in ("Sol", "Maia", "Wolf 359"):
            cache.set(name, _ok_result(name))

        cache.set("Colonia", _ok_result("Colonia"))

        assert cache.get("Sol") is None  # oldest, evicted
        assert cache.get("Maia") is not None
        assert cache.get("Wolf 359") is not None
        assert cache.get("Colonia") is not None

    def test_read_protects_an_older_entry_from_eviction(self):
        cache = SystemLookupCache(ttl_seconds=3600, max_entries=3)
        for name in ("Sol", "Maia", "Wolf 359"):
            cache.set(name, _ok_result(name))

        assert cache.get("Sol") is not None  # re-read makes Sol most recent
        cache.set("Colonia", _ok_result("Colonia"))

        assert cache.get("Sol") is not None
        assert cache.get("Maia") is None  # now the least recently used

    def test_reinsert_refreshes_recency_without_growing_the_store(self):
        cache = SystemLookupCache(ttl_seconds=3600, max_entries=2)
        cache.set("Sol", _ok_result("Sol"))
        cache.set("Maia", _ok_result("Maia"))

        cache.set("Sol", _ok_result("Sol"))  # overwrite, not a new slot
        cache.set("Colonia", _ok_result("Colonia"))

        assert cache.get("Maia") is None
        assert cache.get("Sol") is not None
        assert cache.get("Colonia") is not None

    def test_read_does_not_extend_the_ttl(self):
        """LRU recency and TTL freshness are separate: a hit must not renew the TTL."""
        cache = SystemLookupCache(ttl_seconds=60, max_entries=8)
        cache.set("Sol", _ok_result("Sol"))
        assert cache.get("Sol") is not None

        with patch("src.modules.edsm_system_cache.time.monotonic", return_value=time.monotonic() + 61):
            assert cache.get("Sol") is None

    def test_bodies_eviction_does_not_evict_the_value_entry(self):
        cache = SystemLookupCache(ttl_seconds=3600, max_entries=1)
        cache.set("Sol", _ok_result("Sol"))
        value = _ok_value_result("Sol")
        cache.set_value("Sol", value)

        cache.set("Maia", _ok_result("Maia"))  # evicts Sol from the bodies store only

        assert cache.get("Sol") is None
        assert cache.get_value("Sol") is value

    def test_value_store_is_capped_independently(self):
        cache = SystemLookupCache(ttl_seconds=3600, max_entries=2)
        bodies = _ok_result("Sol")
        cache.set("Sol", bodies)
        for name in ("Sol", "Maia", "Wolf 359"):
            cache.set_value(name, _ok_value_result(name))

        assert cache.get_value("Sol") is None  # evicted from the value store
        assert cache.get("Sol") is bodies  # bodies entry untouched
