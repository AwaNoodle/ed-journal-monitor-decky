"""
Tests for the JournalWatcher module.
Tests position tracking, incremental reading, auxiliary file handling,
and dedicated EDDN schema routing.
"""

from unittest.mock import AsyncMock

import pytest
from conftest import MockSettings

from src.modules.constants import (
    EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF,
    EDDN_CODEXENTRY_1_SCHEMA_REF,
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
    EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)
from src.modules.parser import JournalParser
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


@pytest.fixture
def watcher():
    from src.modules.signal_batcher import SignalBatcher
    settings = MockSettings()
    parser = JournalParser()
    validator = EDDNValidator()
    submitter = EDDNSubmitter(settings)
    signal_batcher = SignalBatcher()
    return JournalWatcher(
        settings=settings,
        parser=parser,
        validator=validator,
        submitter=submitter,
        signal_batcher=signal_batcher,
    )


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
        assert message["message"]["ships"] == ["sidewinder", "eagle"]

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
    async def test_auxiliary_file_retries_on_missing(self, watcher, tmp_path, copy_fixture, monkeypatch):
        """Outfitting event retries reading Outfitting.json when file not immediately available."""
        call_count = 0
        original_parse = watcher.parser.parse_auxiliary_file

        def patched_parse(filepath):
            nonlocal call_count
            call_count += 1
            # Fail first attempt, succeed on second
            if call_count == 1:
                return None
            return original_parse(filepath)

        copy_fixture("Outfitting.json")
        watcher.parser.parse_auxiliary_file = patched_parse
        watcher.submitter.submit = AsyncMock(return_value=True)

        # Speed up retries in test
        import src.modules.watcher as watcher_mod
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr(watcher_mod.asyncio, "sleep", fake_sleep)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Should have retried and succeeded on second attempt
        assert call_count >= 2
        watcher.submitter.submit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auxiliary_file_retries_exhausted(self, watcher, tmp_path, monkeypatch):
        """Outfitting event gives up after max retries when file never appears."""
        watcher.parser.parse_auxiliary_file = lambda filepath: None  # Always return None
        watcher.submitter.submit = AsyncMock(return_value=True)

        # Speed up retries in test
        import src.modules.watcher as watcher_mod

        async def fake_sleep(seconds):
            pass

        monkeypatch.setattr(watcher_mod.asyncio, "sleep", fake_sleep)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Should NOT submit anything when file never appears
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
        """NavRoute now uses navroute/1 schema (not journal/1)."""
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
        assert message["$schemaRef"] == EDDN_NAVROUTE_1_SCHEMA_REF
        assert message["message"]["event"] == "NavRoute"
        assert len(message["message"]["Route"]) == 2
        # Verify event_name is passed for auxiliary schemas
        call_kwargs = watcher.submitter.submit.await_args.kwargs
        assert call_kwargs.get("event_name") == "NavRoute"

    @pytest.mark.asyncio
    async def test_docked_event_does_not_trigger_auxiliary(self, watcher, tmp_path):
        """Docked is reportable but has no auxiliary file — should go through journal/1 only."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T13:00:00Z","event":"Docked","StationName":"Test","StarSystem":"Sol","SystemAddress":10477373803}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # FSDJump and Docked both submitted (Docked gets StarPos from session_state)
        assert watcher.submitter.submit.await_count == 2
        # Find the Docked message
        docked_call = None
        for call in watcher.submitter.submit.await_args_list:
            msg = call.args[0]
            if msg.get("message", {}).get("event") == "Docked":
                docked_call = call
                break
        assert docked_call is not None
        message = docked_call.args[0]
        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF
        # Docked should NOT have event_name override
        assert docked_call.kwargs.get("event_name") is None

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

    def test_today_filename(self, watcher):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"Journal.{today}T120000.01.log"
        assert watcher._is_from_today(filename) is True

    def test_old_filename(self, watcher):
        assert watcher._is_from_today("Journal.2020-01-01T120000.01.log") is False

    def test_invalid_filename(self, watcher):
        assert watcher._is_from_today("notajournal.log") is False


class TestInitialScan:
    """Tests for _initial_scan file selection and session state initialization."""

    @pytest.mark.asyncio
    async def test_first_run_processes_most_recent_file(self, watcher, tmp_path):
        """On first run (no last_active), only the most recent file is processed."""
        # Create two journal files - yesterday's and today's
        yesterday = tmp_path / "Journal.2026-01-11T120000.01.log"
        yesterday.write_text(
            '{"timestamp":"2026-01-11T12:00:00Z","event":"Fileheader","gameversion":"4.2.0.0","build":"r300000/r0"}\n'
            '{"timestamp":"2026-01-11T12:01:15Z","event":"LoadGame","Commander":"OldCmdr","Horizons":true,"Odyssey":false}\n'
        )

        today = tmp_path / "Journal.2026-01-12T120000.01.log"
        today.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.3.0.1","build":"r322188/r0"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"NewCmdr","Horizons":true,"Odyssey":true}\n'
        )

        watcher._journal_path = str(tmp_path)
        await watcher._initial_scan(last_active=None)

        # Most recent file should have been processed (session state from today's file)
        assert watcher.parser.session_state.game_version == "4.3.0.1"
        assert watcher.parser.session_state.game_build == "r322188/r0"
        assert watcher.parser.session_state.commander == "NewCmdr"
        # Older file should have been tracked but not processed
        assert str(yesterday) in watcher._file_positions
        assert watcher._file_positions[str(yesterday)] == 2  # 2 lines tracked

    @pytest.mark.asyncio
    async def test_first_run_skips_older_files(self, watcher, tmp_path):
        """On first run, older files are tracked for position but not processed."""
        old = tmp_path / "Journal.2026-01-10T120000.01.log"
        old.write_text(
            '{"timestamp":"2026-01-10T12:00:00Z","event":"Fileheader","gameversion":"4.1.0.0","build":"r280105/r0"}\n'
        )

        recent = tmp_path / "Journal.2026-01-12T120000.01.log"
        recent.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.3.0.1","build":"r322188/r0"}\n'
        )

        watcher._journal_path = str(tmp_path)
        await watcher._initial_scan(last_active=None)

        # Game version from most recent file, not from old file
        assert watcher.parser.session_state.game_version == "4.3.0.1"
        # Old file tracked but not processed
        assert str(old) in watcher._file_positions

    @pytest.mark.asyncio
    async def test_catch_up_processes_modified_files(self, watcher, tmp_path):
        """On catch-up (with last_active), files modified after last_active are processed."""
        watcher._journal_path = str(tmp_path)

        # Create a file that was modified after last_active
        recent = tmp_path / "Journal.2026-01-12T120000.01.log"
        recent.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.3.0.1","build":"r322188/r0"}\n'
        )

        # last_active is before the file's mtime
        await watcher._initial_scan(last_active="2026-01-11T00:00:00+00:00")

        assert watcher.parser.session_state.game_version == "4.3.0.1"

    @pytest.mark.asyncio
    async def test_game_version_in_submission_header(self, watcher, tmp_path, copy_fixture):
        """Verify gameversion and gamebuild are passed to submitter."""
        copy_fixture("Market.json")
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.3.0.1","build":"r322188/r0"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        watcher.submitter.submit.assert_awaited_once()
        # Verify game_version and game_build are passed through _submit()
        call_kwargs = watcher.submitter.submit.await_args.kwargs
        assert call_kwargs["game_version"] == "4.3.0.1"
        assert call_kwargs["game_build"] == "r322188/r0"


class TestDedicatedSchemaRouting:
    """Tests for dedicated EDDN schema routing in the watcher."""

    @pytest.mark.asyncio
    async def test_fss_signal_discovered_routes_to_batcher(self, watcher, tmp_path):
        """FSSSignalDiscovered should be batched, not immediately submitted."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:03:00Z","event":"FSSSignalDiscovered","SystemAddress":10477373803,"SignalName":"$MULTIPLAYER_SCENARIO42_TITLE;","StarSystem":"Sol","StarPos":[0,0,0]}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # FSDJump should be submitted, but FSSSignalDiscovered should NOT
        # (it goes to the batcher instead)
        submit_calls = watcher.submitter.submit.await_args_list
        submitted_events = []
        for call in submit_calls:
            msg = call.args[0]
            event_name = call.kwargs.get("event_name") or msg.get("message", {}).get("event", "unknown")
            submitted_events.append(event_name)
        assert "FSDJump" in submitted_events
        assert "FSSSignalDiscovered" not in submitted_events

    @pytest.mark.asyncio
    async def test_fss_discovery_scan_triggers_flush_and_uses_dedicated_schema(self, watcher, tmp_path):
        """FSSDiscoveryScan should flush the signal batcher and submit to fssdiscoveryscan/1."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:03:00Z","event":"FSSSignalDiscovered","SystemAddress":10477373803,"SignalName":"$Signal1;","StarSystem":"Sol","StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:03:05Z","event":"FSSSignalDiscovered","SystemAddress":10477373803,"SignalName":"$Signal2;","StarSystem":"Sol","StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T12:15:00Z","event":"FSSDiscoveryScan","StarSystem":"Sol","SystemAddress":10477373803,"BodyCount":21,"NonBodyCount":42}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Should have 3 submissions: FSDJump, FSSSignalDiscovered batch, FSSDiscoveryScan
        assert watcher.submitter.submit.await_count == 3
        # Find the FSSDiscoveryScan and batch submissions
        schema_refs = [call.args[0]["$schemaRef"] for call in watcher.submitter.submit.await_args_list]
        event_names = []
        for call in watcher.submitter.submit.await_args_list:
            event_names.append(call.kwargs.get("event_name") or call.args[0].get("message", {}).get("event", "unknown"))

        # FSSDiscoveryScan should use fssdiscoveryscan/1
        assert EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF in schema_refs
        # FSSSignalDiscovered batch should use fsssignaldiscovered/1
        assert EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF in schema_refs
        # Event name for batch should be FSSSignalDiscovered
        assert "FSSSignalDiscovered" in event_names
        # Event name for FSSDiscoveryScan should be FSSDiscoveryScan
        assert "FSSDiscoveryScan" in event_names

    @pytest.mark.asyncio
    async def test_approach_settlement_uses_dedicated_schema(self, watcher, tmp_path):
        """ApproachSettlement should submit to approachsettlement/1 schema."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:01:20Z","event":"ApproachSettlement","StarSystem":"Sol","SystemAddress":10477373803,"StationName":"Galileo","BodyID":1,"BodyName":"Earth","MarketID":128666762,"Latitude":42.0,"Longitude":-7.0}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Find the ApproachSettlement submission
        approach_call = None
        for call in watcher.submitter.submit.await_args_list:
            if call.kwargs.get("event_name") == "ApproachSettlement":
                approach_call = call
                break
        assert approach_call is not None
        message = approach_call.args[0]
        assert message["$schemaRef"] == EDDN_APPROACHSETTLEMENT_1_SCHEMA_REF

    @pytest.mark.asyncio
    async def test_codex_entry_uses_dedicated_schema(self, watcher, tmp_path):
        """CodexEntry should submit to codexentry/1 schema."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T15:00:00Z","event":"CodexEntry","SystemAddress":10477373803,"Name":"$Codex_Ent_Name_1;","Region":"TestRegion","EntryID":123,"BodyID":1,"BodyName":"Earth"}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Find the CodexEntry submission
        codex_call = None
        for call in watcher.submitter.submit.await_args_list:
            if call.kwargs.get("event_name") == "CodexEntry":
                codex_call = call
                break
        assert codex_call is not None
        message = codex_call.args[0]
        assert message["$schemaRef"] == EDDN_CODEXENTRY_1_SCHEMA_REF

    @pytest.mark.asyncio
    async def test_saa_signals_found_routes_through_journal1(self, watcher, tmp_path):
        """SAASignalsFound should go through journal/1 (it's in the journal/1 enum)."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:05:00Z","event":"SAASignalsFound","StarSystem":"Sol","SystemAddress":10477373803}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Find the SAASignalsFound submission
        saa_call = None
        for call in watcher.submitter.submit.await_args_list:
            msg = call.args[0]
            if msg.get("message", {}).get("event") == "SAASignalsFound":
                saa_call = call
                break
        assert saa_call is not None
        message = saa_call.args[0]
        assert message["$schemaRef"] == EDDN_JOURNAL_1_SCHEMA_REF

    @pytest.mark.asyncio
    async def test_approach_body_not_reportable(self, watcher, tmp_path):
        """ApproachBody has no EDDN schema and should not be submitted."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:00:00Z","event":"ApproachBody","StarSystem":"Sol","SystemAddress":10477373803,"BodyName":"Earth"}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Only FSDJump should be submitted, not ApproachBody
        assert watcher.submitter.submit.await_count == 1
        msg = watcher.submitter.submit.await_args.args[0]
        assert msg["message"]["event"] == "FSDJump"

    @pytest.mark.asyncio
    async def test_leave_body_not_reportable(self, watcher, tmp_path):
        """LeaveBody has no EDDN schema and should not be submitted."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:00:00Z","event":"LeaveBody","StarSystem":"Sol","SystemAddress":10477373803,"BodyName":"Earth"}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        assert watcher.submitter.submit.await_count == 1
        msg = watcher.submitter.submit.await_args.args[0]
        assert msg["message"]["event"] == "FSDJump"

    @pytest.mark.asyncio
    async def test_saa_scan_complete_not_reportable(self, watcher, tmp_path):
        """SAAScanComplete has no EDDN schema and should not be submitted."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:00:00Z","event":"SAAScanComplete","BodyName":"Earth","SystemAddress":10477373803}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        assert watcher.submitter.submit.await_count == 1
        msg = watcher.submitter.submit.await_args.args[0]
        assert msg["message"]["event"] == "FSDJump"

    @pytest.mark.asyncio
    async def test_fsdjump_triggers_signal_batch_flush(self, watcher, tmp_path):
        """FSDJump is a flush trigger AND a system change event."""
        watcher.submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:03:00Z","event":"FSSSignalDiscovered","SystemAddress":10477373803,"SignalName":"$Signal1;","StarSystem":"Sol","StarPos":[0,0,0]}\n'
            '{"timestamp":"2026-01-12T14:05:00Z","event":"FSDJump",'
            '"StarSystem":"Alpha Centauri","SystemAddress":55230754,'
            '"StarPos":[1,2,3]}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        # Should have: FSDJump(Sol), FSSSignalDiscovered(batch flushed by FSDJump), FSDJump(Alpha Centauri)
        assert watcher.submitter.submit.await_count == 3
        # Verify the batch submission used fsssignaldiscovered/1
        batch_call = None
        for call in watcher.submitter.submit.await_args_list:
            if call.kwargs.get("event_name") == "FSSSignalDiscovered":
                batch_call = call
                break
        assert batch_call is not None
        assert batch_call.args[0]["$schemaRef"] == EDDN_FSSSIGNALDISCOVERED_1_SCHEMA_REF
