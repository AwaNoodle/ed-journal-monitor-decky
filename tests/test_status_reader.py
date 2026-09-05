from __future__ import annotations

"""
Tests for the Status.json reader (issue #39).

codexentry-README.md's "BodyID and BodyName" section: the message's
``BodyName`` may only come from Status.json, and only when it can be
trusted to describe the moment the codex entry was logged. These tests
cover every failure mode the reader must resolve to ``None`` for, plus the
timestamp-skew freshness gate and the bounded torn-read retry.
"""

import json

import pytest

from src.modules.constants import STATUS_BODY_MAX_SKEW_SECONDS
from src.modules.status_reader import read_status_body_name

EVENT_TIMESTAMP = "2026-01-12T15:00:00Z"


def _write_status(tmp_path, payload: dict | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (tmp_path / "Status.json").write_text(text, encoding="utf-8")


class TestReadStatusBodyName:
    @pytest.mark.asyncio
    async def test_fresh_body_name_returned(self, tmp_path):
        _write_status(tmp_path, {"timestamp": EVENT_TIMESTAMP, "BodyName": "Earth"})
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result == "Earth"

    @pytest.mark.asyncio
    async def test_body_name_absent_returns_none(self, tmp_path):
        _write_status(tmp_path, {"timestamp": EVENT_TIMESTAMP})
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_body_name_empty_string_returns_none(self, tmp_path):
        _write_status(tmp_path, {"timestamp": EVENT_TIMESTAMP, "BodyName": ""})
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_body_name_non_string_returns_none(self, tmp_path):
        _write_status(tmp_path, {"timestamp": EVENT_TIMESTAMP, "BodyName": 123})
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_file_missing_returns_none(self, tmp_path):
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_non_dict_json_returns_none(self, tmp_path):
        _write_status(tmp_path, json.dumps(["not", "a", "dict"]))
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_timestamp_missing_returns_none(self, tmp_path):
        _write_status(tmp_path, {"BodyName": "Earth"})
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_skew_beyond_window_future_returns_none(self, tmp_path):
        # Status.json newer than the event by more than the skew window.
        _write_status(
            tmp_path,
            {"timestamp": "2026-01-12T15:02:01Z", "BodyName": "Earth"},
        )
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_skew_beyond_window_past_returns_none(self, tmp_path):
        # Status.json older than the event by more than the skew window
        # (e.g. a replayed codex entry from a previous session).
        _write_status(
            tmp_path,
            {"timestamp": "2026-01-12T14:57:59Z", "BodyName": "Earth"},
        )
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_skew_inside_window_returned(self, tmp_path):
        assert STATUS_BODY_MAX_SKEW_SECONDS == 60
        _write_status(
            tmp_path,
            {"timestamp": "2026-01-12T15:00:45Z", "BodyName": "Earth"},
        )
        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result == "Earth"

    @pytest.mark.asyncio
    async def test_torn_read_parses_on_later_attempt(self, tmp_path, monkeypatch):
        status_path = tmp_path / "Status.json"
        status_path.write_text(json.dumps({"timestamp": EVENT_TIMESTAMP, "BodyName": "Earth"}), encoding="utf-8")

        import src.modules.status_reader as status_reader_mod

        call_count = 0
        original_open = status_reader_mod.Path.open

        def flaky_open(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and self == status_path:
                raise OSError("simulated torn read")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(status_reader_mod.Path, "open", flaky_open)

        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr(status_reader_mod.asyncio, "sleep", fake_sleep)

        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result == "Earth"
        assert call_count >= 2
        assert sleep_calls

    @pytest.mark.asyncio
    async def test_torn_on_every_attempt_returns_none(self, tmp_path, monkeypatch):
        status_path = tmp_path / "Status.json"
        status_path.write_text(json.dumps({"timestamp": EVENT_TIMESTAMP, "BodyName": "Earth"}), encoding="utf-8")

        import src.modules.status_reader as status_reader_mod

        def always_broken_open(self, *args, **kwargs):
            raise OSError("simulated torn read")

        monkeypatch.setattr(status_reader_mod.Path, "open", always_broken_open)

        async def fake_sleep(seconds):
            pass

        monkeypatch.setattr(status_reader_mod.asyncio, "sleep", fake_sleep)

        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_json_returns_none(self, tmp_path, monkeypatch):
        _write_status(tmp_path, "{not valid json")

        async def fake_sleep(seconds):
            pass

        import src.modules.status_reader as status_reader_mod
        monkeypatch.setattr(status_reader_mod.asyncio, "sleep", fake_sleep)

        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_offsetless_status_timestamp_read_as_utc(self, tmp_path):
        """A Status.json timestamp without a UTC offset must not raise.

        Both files write UTC, so an offset-less value is read as UTC.
        Subtracting it from the aware event timestamp would otherwise raise
        TypeError and drop the codex entry instead of omitting body keys.
        """
        _write_status(tmp_path, {"timestamp": "2026-01-12T15:00:30", "BodyName": "Earth"})

        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result == "Earth"

    @pytest.mark.asyncio
    async def test_offsetless_status_timestamp_still_skew_gated(self, tmp_path):
        _write_status(tmp_path, {"timestamp": "2026-01-12T13:00:00", "BodyName": "Earth"})

        result = await read_status_body_name(str(tmp_path), EVENT_TIMESTAMP)
        assert result is None

    @pytest.mark.asyncio
    async def test_offsetless_event_timestamp_read_as_utc(self, tmp_path):
        _write_status(tmp_path, {"timestamp": EVENT_TIMESTAMP, "BodyName": "Earth"})

        result = await read_status_body_name(str(tmp_path), "2026-01-12T15:00:00")
        assert result == "Earth"
