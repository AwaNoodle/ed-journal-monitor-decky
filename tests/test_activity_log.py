"""
Tests for the ActivityLog module.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.modules.activity_log import MAX_ENTRIES, ActivityLog


class TestEntryCreation:
    """Tests for recording entries."""

    @pytest.mark.asyncio
    async def test_record_success_creates_entry(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("FSDJump")

        assert len(log._entries) == 1
        entry = log._entries[0]
        assert entry["event_type"] == "FSDJump"
        assert entry["outcome"] == "success"
        assert entry["error_type"] is None
        assert entry["error_message"] is None
        assert entry["http_status"] is None
        assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_record_failure_creates_entry(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_failure("Scan", "http_error", "Bad Request", http_status=400)

        assert len(log._entries) == 1
        entry = log._entries[0]
        assert entry["event_type"] == "Scan"
        assert entry["outcome"] == "failure"
        assert entry["error_type"] == "http_error"
        assert entry["error_message"] == "Bad Request"
        assert entry["http_status"] == 400

    @pytest.mark.asyncio
    async def test_record_failure_network_error_no_http_status(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_failure("Docked", "network_error", "Connection timed out")

        entry = log._entries[0]
        assert entry["error_type"] == "network_error"
        assert entry["http_status"] is None

    @pytest.mark.asyncio
    async def test_record_emits_activity_update(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("FSDJump")

        mock_decky.emit.assert_called_once()
        call_args = mock_decky.emit.call_args
        assert call_args[0][0] == "activity_update"
        emitted_entry = call_args[0][1]
        assert emitted_entry["event_type"] == "FSDJump"
        assert emitted_entry["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_failure_emits_activity_update(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_failure("Scan", "http_error", "Bad Request", http_status=400)

        mock_decky.emit.assert_called_once()
        call_args = mock_decky.emit.call_args
        assert call_args[0][0] == "activity_update"
        emitted_entry = call_args[0][1]
        assert emitted_entry["outcome"] == "failure"


class TestTargetTagging:
    """Tests for the per-entry target field."""

    @pytest.mark.asyncio
    async def test_success_defaults_to_eddn_target(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("FSDJump")

        assert log._entries[0]["target"] == "eddn"

    @pytest.mark.asyncio
    async def test_failure_defaults_to_eddn_target(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_failure("Scan", "http_error", "Bad Request", http_status=400)

        assert log._entries[0]["target"] == "eddn"

    @pytest.mark.asyncio
    async def test_success_records_explicit_edsm_target(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("Rank", target="edsm")

        entry = log._entries[0]
        assert entry["target"] == "edsm"
        assert entry["outcome"] == "success"
        assert entry["event_type"] == "Rank"

    @pytest.mark.asyncio
    async def test_failure_records_explicit_edsm_target(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_failure(
                "FSDJump", "edsm", "[203] Commander name/API Key not found", target="edsm",
            )

        entry = log._entries[0]
        assert entry["target"] == "edsm"
        assert entry["outcome"] == "failure"
        assert entry["error_type"] == "edsm"
        assert "203" in entry["error_message"]
        assert entry["http_status"] is None

    @pytest.mark.asyncio
    async def test_target_included_in_emitted_entry(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("Rank", target="edsm")

        emitted_entry = mock_decky.emit.call_args[0][1]
        assert emitted_entry["target"] == "edsm"


class TestBufferOverflow:
    """Tests for circular buffer behavior."""

    @pytest.mark.asyncio
    async def test_buffer_at_capacity_discards_oldest(self):
        log = ActivityLog(max_entries=5)
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            for i in range(7):
                await log.record_success(f"Event{i}")

        # Should keep only last 5
        assert len(log._entries) == 5
        # Oldest should be Event2, newest Event6
        assert log._entries[0]["event_type"] == "Event2"
        assert log._entries[-1]["event_type"] == "Event6"

    @pytest.mark.asyncio
    async def test_default_max_entries(self):
        log = ActivityLog()
        assert log._entries.maxlen == MAX_ENTRIES


class TestGetRecent:
    """Tests for get_recent retrieval."""

    @pytest.mark.asyncio
    async def test_get_recent_returns_newest_first(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("First")
            await log.record_success("Second")
            await log.record_success("Third")

        result = log.get_recent()
        assert result[0]["event_type"] == "Third"
        assert result[1]["event_type"] == "Second"
        assert result[2]["event_type"] == "First"

    @pytest.mark.asyncio
    async def test_get_recent_with_limit(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            for i in range(10):
                await log.record_success(f"Event{i}")

        result = log.get_recent(limit=3)
        assert len(result) == 3
        assert result[0]["event_type"] == "Event9"

    @pytest.mark.asyncio
    async def test_get_recent_filter_by_outcome(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("FSDJump")
            await log.record_failure("Scan", "http_error", "Bad Request", http_status=400)
            await log.record_success("Docked")
            await log.record_failure("Supercruise", "network_error", "Timeout")

        failures = log.get_recent(outcome="failure")
        assert len(failures) == 2
        assert all(e["outcome"] == "failure" for e in failures)

    @pytest.mark.asyncio
    async def test_get_recent_empty_log(self):
        log = ActivityLog()
        result = log.get_recent()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_filter_with_limit(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            for i in range(5):
                await log.record_success(f"Success{i}")
                await log.record_failure(f"Fail{i}", "http_error", f"Error{i}", http_status=400)

        failures = log.get_recent(limit=2, outcome="failure")
        assert len(failures) == 2
        assert all(e["outcome"] == "failure" for e in failures)

    @pytest.mark.asyncio
    async def test_newest_first_ordering_preserved_with_mixed_entries(self):
        log = ActivityLog()
        with patch("src.modules.activity_log.decky") as mock_decky:
            mock_decky.emit = AsyncMock()
            await log.record_success("A")
            await log.record_failure("B", "http_error", "err")
            await log.record_success("C")

        result = log.get_recent()
        assert result[0]["event_type"] == "C"
        assert result[1]["event_type"] == "B"
        assert result[2]["event_type"] == "A"
