"""
Tests for the JournalWatcher module.
Tests position tracking, incremental reading, and auxiliary file handling.
"""

from unittest.mock import AsyncMock

import pytest
from conftest import MockSettings

from src.modules.constants import (
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)
from src.modules.parser import JournalParser
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


@pytest.fixture
def watcher():
    settings = MockSettings()
    parser = JournalParser()
    validator = EDDNValidator()
    submitter = EDDNSubmitter(settings)
    return JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)


class TestFilePositions:
    """Tests for file position tracking."""

    def test_initial_position_is_zero(self, watcher):
        assert watcher._file_positions == {}

    def test_position_updates_after_processing(self, watcher, tmp_path):
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n',
        )

        import asyncio

        asyncio.run(watcher._process_file(str(journal_file)))

        assert watcher._file_positions[str(journal_file)] == 2

    def test_incremental_reading(self, watcher, tmp_path):
        """File is written to after initial read - only new lines should be processed."""
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n',
        )

        import asyncio

        asyncio.run(watcher._process_file(str(journal_file)))
        assert watcher._file_positions[str(journal_file)] == 2

        # Append new content
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame"}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6}\n',
        )

        asyncio.run(watcher._process_file(str(journal_file)))
        assert watcher._file_positions[str(journal_file)] == 3


class TestAuxiliaryFileHandling:
    @pytest.mark.asyncio
    async def test_market_event_uses_market_json(self, watcher, tmp_path, copy_fixture):
        copy_fixture("Market.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        message = watcher.submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_COMMODITY_3_SCHEMA_REF
        assert message["message"]["stationName"] == "Jameson Memorial"
        assert message["message"]["timestamp"] == "2026-01-12T13:05:00Z"
        assert len(message["message"]["commodities"]) == 2
        # Verify Market is NOT sent as journal/1
        assert message["$schemaRef"] != EDDN_JOURNAL_1_SCHEMA_REF

    @pytest.mark.asyncio
    async def test_outfitting_event_uses_outfitting_json(self, watcher, tmp_path, copy_fixture):
        copy_fixture("Outfitting.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        message = watcher.submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_OUTFITTING_2_SCHEMA_REF
        # EDDN outfitting/2: modules is array of strings
        assert message["message"]["modules"] == [
            "int_cargo_rack_size6_class1",
            "int_shieldgenerator_size8_class5_fast",
        ]

    @pytest.mark.asyncio
    async def test_shipyard_event_uses_shipyard_json(self, watcher, tmp_path, copy_fixture):
        copy_fixture("Shipyard.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":false,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Shipyard","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        message = watcher.submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_SHIPYARD_2_SCHEMA_REF
        # EDDN shipyard/2: ships is array of strings
        assert message["message"]["ships"] == ["sidey", "eagle"]

    @pytest.mark.asyncio
    async def test_market_event_missing_market_json(self, watcher, tmp_path):
        """Market event with no Market.json file should result in zero submissions."""
        # Do NOT copy Market.json fixture
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auxiliary_submission_passes_event_name(self, watcher, tmp_path, copy_fixture):
        """Auxiliary schema submissions should pass event_name to submitter."""
        copy_fixture("Market.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Verify event_name is passed as keyword arg
        call_kwargs = watcher.submitter.submit.await_args.kwargs
        assert call_kwargs.get("event_name") == "Market"

    @pytest.mark.asyncio
    async def test_navroute_event_uses_navroute_json(self, watcher, tmp_path, copy_fixture):
        copy_fixture("NavRoute.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T14:00:00Z","event":"NavRoute"}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        message = watcher.submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF
        assert message["message"]["event"] == "NavRoute"
        assert len(message["message"]["Route"]) == 2

    @pytest.mark.asyncio
    async def test_docked_event_does_not_trigger_auxiliary(self, watcher, tmp_path):
        """Docked is reportable but has no auxiliary file — should go through journal/1 only."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:00:00Z","event":"Docked","StationName":"Test","StarSystem":"Sol","SystemAddress":10477373803}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        message = watcher.submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF
        # Docked should NOT have event_name override
        assert watcher.submitter.submit.await_args.kwargs.get("event_name") is None

    @pytest.mark.asyncio
    async def test_invalid_auxiliary_json_no_submission(self, watcher, tmp_path):
        """Auxiliary file with invalid JSON should result in no submission."""
        # Create a broken Market.json
        (tmp_path / "Market.json").write_text("{broken", encoding="utf-8")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_market_no_submission(self, watcher, tmp_path):
        """Market.json with all items filtered (empty commodities) → no submission."""
        (tmp_path / "Market.json").write_text(
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762,'
            '"StationName":"Test","StarSystem":"Sol",'
            '"Items":[{"Name":"junk","StockBracket":0,"DemandBracket":0}]}\n',
            encoding="utf-8",
        )
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resolve_auxiliary_path_with_journal_path(self, watcher, tmp_path, copy_fixture):
        """When source_filepath is None, _journal_path is used to find auxiliary files."""
        copy_fixture("Market.json")
        watcher.submitter.submit = AsyncMock(return_value=True)
        watcher._journal_path = str(tmp_path)  # Simulate runtime state

        # Call _process_reportable_event directly with source_filepath=None
        # to exercise the _journal_path branch
        from src.modules.parser import JournalParser, ParsedEvent
        watcher.parser = JournalParser()
        watcher.parser.session_state.horizons = True
        watcher.parser.session_state.odyssey = False

        event = ParsedEvent(
            raw={"timestamp": "2026-01-12T13:05:00Z", "event": "Market", "MarketID": 128666762},
            event_type="Market",
            timestamp="2026-01-12T13:05:00Z",
        )

        await watcher._process_reportable_event(event, source_filepath=None)

        watcher.submitter.submit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_per_event_exception_does_not_block_later_events(self, watcher, tmp_path):
        """If processing one event raises, subsequent events in the same file are still processed."""
        watcher.submitter.submit = AsyncMock(side_effect=[Exception("boom"), True])

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T12:10:45Z","event":"Scan","ScanType":"Detailed","BodyName":"Sol","DistanceFromArrivalLS":0.0}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Position should still be updated even if one event failed
        assert watcher._file_positions[str(journal_file)] == 4
        # FSDJump submit raises, Scan submit succeeds
        assert watcher.submitter.submit.await_count == 2
    """Tests for _is_from_today."""

    def test_today_filename(self, watcher):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"Journal.{today}T120000.01.log"
        assert watcher._is_from_today(filename) is True

    def test_old_filename(self, watcher):
        assert watcher._is_from_today("Journal.2020-01-01T120000.01.log") is False

    def test_invalid_filename(self, watcher):
        assert watcher._is_from_today("notajournal.log") is False
