"""
Integration tests for the ED Journal Monitor plugin.
Tests the full pipeline: watcher → parser → validator → submitter.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import MockSettings

from main import Plugin
from src.modules.activity_log import ActivityLog
from src.modules.constants import (
    EDDN_COMMODITY_3_SCHEMA_REF,
    EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF,
    EDDN_JOURNAL_1_SCHEMA_REF,
    EDDN_NAVROUTE_1_SCHEMA_REF,
    EDDN_OUTFITTING_2_SCHEMA_REF,
    EDDN_SHIPYARD_2_SCHEMA_REF,
)
from src.modules.parser import JournalParser
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


class TestEndToEndPipeline:
    """Test the full pipeline with real journal fixture files."""

    @pytest.mark.asyncio
    async def test_process_journal_fixture_file(self, tmp_path):
        """Process a real journal fixture file through the pipeline."""
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        # Copy fixture to temp directory
        fixture_dir = Path(__file__).parent / "fixtures"
        journal_dir = tmp_path
        if (fixture_dir / "Journal.2026-01-12T120000.01.log").exists():
            import shutil
            shutil.copy(fixture_dir / "Journal.2026-01-12T120000.01.log", journal_dir)

        # Patch submitter to not actually POST
        submitted_messages = []

        async def mock_submit(message, event_name=None, game_version="", game_build=""):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Process the file
        await watcher._process_file(str(journal_dir / "Journal.2026-01-12T120000.01.log"))

        # Verify events were processed
        # The fixture has: Fileheader, LoadGame, FSDJump, Scan, FSSDiscoveryScan
        # Reportable: FSDJump (journal/1), Scan (journal/1), FSSDiscoveryScan (fssdiscoveryscan/1)
        reportable_events = [m for m in submitted_messages if m.get("message", {}).get("event") in
                            ["FSDJump", "Scan", "FSSDiscoveryScan"]]
        assert len(reportable_events) == 3

        # Verify schemas: FSDJump and Scan use journal/1, FSSDiscoveryScan uses fssdiscoveryscan/1
        schema_refs = {m["$schemaRef"] for m in reportable_events}
        assert EDDN_JOURNAL_1_SCHEMA_REF in schema_refs
        assert EDDN_FSSDISCOVERYSCAN_1_SCHEMA_REF in schema_refs

        # Verify LoadGame was captured for session state. This fixture's LoadGame
        # has no Horizons/Odyssey keys (a 3.8-era shape), so those stay unknown
        # (None) rather than being guessed -- see TestSessionState in
        # test_parser.py and test_omits_horizons_odyssey_when_unknown in
        # test_validator.py for the dedicated coverage.
        assert parser.session_state.commander == "TestCommander"
        assert parser.session_state.horizons is None
        assert parser.session_state.odyssey is None

        # Verify message structure
        for msg in reportable_events:
            assert "$schemaRef" in msg
            assert "header" in msg
            assert "message" in msg
            assert "horizons" not in msg["message"]
            assert "odyssey" not in msg["message"]

    @pytest.mark.asyncio
    async def test_market_auxiliary_pipeline(self, tmp_path, copy_fixture):
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        copy_fixture("Market.json")
        submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":false}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Market","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        submitter.submit.assert_awaited_once()
        message = submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_COMMODITY_3_SCHEMA_REF
        assert message["message"]["timestamp"] == "2026-01-12T13:05:00Z"
        assert message["message"]["stationName"] == "Jameson Memorial"
        assert len(message["message"]["commodities"]) == 2

    @pytest.mark.asyncio
    async def test_outfitting_auxiliary_pipeline(self, tmp_path, copy_fixture):
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        copy_fixture("Outfitting.json")
        submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Outfitting","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        submitter.submit.assert_awaited_once()
        message = submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_OUTFITTING_2_SCHEMA_REF
        assert message["message"]["timestamp"] == "2026-01-12T13:05:00Z"
        # EDDN outfitting/2: modules is array of strings
        assert message["message"]["modules"] == [
            "int_cargo_rack_size6_class1",
            "int_shieldgenerator_size8_class5_fast",
        ]

    @pytest.mark.asyncio
    async def test_shipyard_auxiliary_pipeline(self, tmp_path, copy_fixture):
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        copy_fixture("Shipyard.json")
        submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":false,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T13:05:00Z","event":"Shipyard","MarketID":128666762}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        submitter.submit.assert_awaited_once()
        message = submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_SHIPYARD_2_SCHEMA_REF
        assert message["message"]["timestamp"] == "2026-01-12T13:05:00Z"
        # EDDN shipyard/2: ships is array of strings
        assert message["message"]["ships"] == ["sidewinder", "eagle"]

    @pytest.mark.asyncio
    async def test_navroute_auxiliary_pipeline(self, tmp_path, copy_fixture):
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        copy_fixture("NavRoute.json")
        submitter.submit = AsyncMock(return_value=True)

        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T14:00:00Z","event":"NavRoute"}\n',
            encoding="utf-8",
        )

        await watcher._process_file(str(journal_file))

        submitter.submit.assert_awaited_once()
        message = submitter.submit.await_args.args[0]
        assert message["$schemaRef"] == EDDN_NAVROUTE_1_SCHEMA_REF
        assert message["message"]["event"] == "NavRoute"
        assert len(message["message"]["Route"]) == 2

    @pytest.mark.asyncio
    async def test_catch_up_on_restart(self, tmp_path):
        """
        Test catch-up scenario:
        1. Watcher processes initial file
        2. Watcher stops
        3. New content is added
        4. Watcher restarts and catches up
        """
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message, event_name=None, game_version="", game_build=""):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Create initial journal file
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.0.0.1","build":"r293895/r0 "}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6}\n',
        )

        # Process initial content
        await watcher._process_file(str(journal_file))
        initial_count = len(submitted_messages)
        assert initial_count == 1  # FSDJump is the only reportable event

        # Append new content (simulating game continuing after watcher stops)
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.0.0.1","build":"r293895/r0 "}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6}\n'
            '{"timestamp":"2026-01-12T12:10:45Z","event":"Scan","ScanType":"Detailed","BodyName":"Sol","DistanceFromArrivalLS":0.0}\n'
            '{"timestamp":"2026-01-12T12:15:00Z","event":"Docked","StationName":"TestStation","StarSystem":"Sol","SystemAddress":10477373803}\n',
        )

        # Process again (catch-up) - should only process new lines
        await watcher._process_file(str(journal_file))
        # Should have 2 more reportable events: Scan + Docked
        assert len(submitted_messages) == initial_count + 2

    @pytest.mark.asyncio
    async def test_field_stripping_in_pipeline(self, tmp_path):
        """Verify disallowed fields are stripped in the full pipeline."""
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message, event_name=None, game_version="", game_build=""):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Create a journal file with disallowed fields
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:00Z","event":"LoadGame","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6,"ActiveFine":true,"Wanted":true,"Government_Localised":"Democracy"}\n',
        )

        await watcher._process_file(str(journal_file))

        # Check that disallowed fields and _Localised keys were stripped
        fsdjump_msg = next(m for m in submitted_messages if m["message"]["event"] == "FSDJump")
        assert "ActiveFine" not in fsdjump_msg["message"]
        assert "Wanted" not in fsdjump_msg["message"]
        assert "Government_Localised" not in fsdjump_msg["message"]
        # JumpDist, FuelUsed, FuelLevel are also disallowed by EDDN schema
        assert "JumpDist" not in fsdjump_msg["message"]
        assert "FuelUsed" not in fsdjump_msg["message"]
        assert "FuelLevel" not in fsdjump_msg["message"]
        assert fsdjump_msg["message"]["StarSystem"] == "Sol"

    @pytest.mark.asyncio
    async def test_empty_journal_dir(self, tmp_path):
        """Watching an empty journal directory should not crash."""
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message, event_name=None, game_version="", game_build=""):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Poll on empty directory
        await watcher._poll()
        assert len(submitted_messages) == 0

    @pytest.mark.asyncio
    async def test_start_watcher_blocked_when_disabled(self):
        """Plugin.start_watcher returns disabled error when enabled=False."""
        plugin = Plugin()
        settings = MockSettings(initial_data={"enabled": False})

        plugin.settings = settings
        plugin.watcher = MagicMock()
        plugin.watcher.is_running = False
        plugin.watcher.start = AsyncMock()
        plugin.path_finder = MagicMock()
        plugin.path_finder.find_journal_path = AsyncMock(return_value="/tmp/journals")

        result = await plugin.start_watcher()

        assert result == {"success": False, "error": "Monitor is disabled"}
        plugin.path_finder.find_journal_path.assert_not_called()
        plugin.watcher.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_recent_activity_after_simulated_uploads(self, tmp_path):
        """Verify get_recent_activity callable returns expected entries after simulated uploads."""
        settings = MockSettings(initial_data={"uploader_id": "test-integration", "software_version": "0.1.0"})
        activity_log = ActivityLog()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings, activity_log=activity_log)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message, event_name=None, game_version="", game_build=""):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Create a journal file with reportable events
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader","gameversion":"4.0.0.1","build":"r293895/r0 "}\n'
            '{"timestamp":"2026-01-12T12:01:15Z","event":"LoadGame","Commander":"TestCmdr","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6}\n'
            '{"timestamp":"2026-01-12T12:10:00Z","event":"Scan","ScanType":"Detailed","BodyName":"Sol","DistanceFromArrivalLS":0.0}\n'
        )

        await watcher._process_file(str(journal_file))

        # Activity log should have entries from the submit calls
        # Since we replaced submit, activity_log won't be populated directly
        # Instead test with the real submitter path
        activity_log2 = ActivityLog()
        with patch("src.modules.submitter.urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            submitter2 = EDDNSubmitter(settings, activity_log=activity_log2)
            await submitter2.submit({"$schemaRef": "", "header": {}, "message": {"event": "FSDJump"}})
            await submitter2.submit({"$schemaRef": "", "header": {}, "message": {"event": "Scan"}})

        # Verify get_recent_activity returns entries
        entries = activity_log2.get_recent()
        assert len(entries) == 2
        assert entries[0]["event_type"] == "Scan"  # newest first
        assert entries[1]["event_type"] == "FSDJump"

        # Verify filtering works
        # All are successes, so filtering by failure should return empty
        failures = activity_log2.get_recent(outcome="failure")
        assert len(failures) == 0
