"""
Integration tests for the ED Journal Monitor plugin.
Tests the full pipeline: watcher → parser → validator → submitter.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.modules.activity_log import ActivityLog
from src.modules.parser import JournalParser
from src.modules.submitter import EDDNSubmitter
from src.modules.validator import EDDNValidator
from src.modules.watcher import JournalWatcher


class MockSettings:
    def __init__(self):
        self._data = {"uploader_id": "test-integration", "software_version": "0.1.0", "poll_interval": 10}

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value


class TestEndToEndPipeline:
    """Test the full pipeline with real journal fixture files."""

    @pytest.mark.asyncio
    async def test_process_journal_fixture_file(self, tmp_path):
        """Process a real journal fixture file through the pipeline."""
        settings = MockSettings()
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

        async def mock_submit(message):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Process the file
        await watcher._process_file(str(journal_dir / "Journal.2026-01-12T120000.01.log"))

        # Verify events were processed
        # The fixture has: Fileheader, LoadGame, FSDJump, Scan, FSSDiscoveryScan
        # Reportable: FSDJump, Scan, FSSDiscoveryScan
        reportable_events = [m for m in submitted_messages if m.get("message", {}).get("event") in
                            ["FSDJump", "Scan", "FSSDiscoveryScan"]]
        assert len(reportable_events) == 3

        # Verify LoadGame was captured for session state
        assert parser.session_state.horizons is not None

        # Verify message structure
        for msg in reportable_events:
            assert "$schemaRef" in msg
            assert "header" in msg
            assert "message" in msg
            assert "horizons" in msg["message"]
            assert "odyssey" in msg["message"]

    @pytest.mark.asyncio
    async def test_catch_up_on_restart(self, tmp_path):
        """
        Test catch-up scenario:
        1. Watcher processes initial file
        2. Watcher stops
        3. New content is added
        4. Watcher restarts and catches up
        """
        settings = MockSettings()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message):
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
        settings = MockSettings()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Create a journal file with disallowed fields
        journal_file = tmp_path / "Journal.2026-01-12T120000.01.log"
        journal_file.write_text(
            '{"timestamp":"2026-01-12T12:00:00Z","event":"Fileheader"}\n'
            '{"timestamp":"2026-01-12T12:01:00Z","event":"LoadGame","Horizons":true,"Odyssey":true}\n'
            '{"timestamp":"2026-01-12T12:05:30Z","event":"FSDJump","StarSystem":"Sol","SystemAddress":10477373803,"StarPos":[0,0,0],"JumpDist":15,"FuelUsed":2.3,"FuelLevel":28.6,"ActiveFine":true,"Crew":["NPC1"]}\n',
        )

        await watcher._process_file(str(journal_file))

        # Check that ActiveFine and Crew were stripped
        fsdjump_msg = next(m for m in submitted_messages if m["message"]["event"] == "FSDJump")
        assert "ActiveFine" not in fsdjump_msg["message"]
        assert "Crew" not in fsdjump_msg["message"]
        assert fsdjump_msg["message"]["StarSystem"] == "Sol"

    @pytest.mark.asyncio
    async def test_empty_journal_dir(self, tmp_path):
        """Watching an empty journal directory should not crash."""
        settings = MockSettings()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message):
            submitted_messages.append(message)
            return True

        submitter.submit = mock_submit

        # Poll on empty directory
        await watcher._poll()
        assert len(submitted_messages) == 0

    @pytest.mark.asyncio
    async def test_start_watcher_blocked_when_disabled(self, tmp_path):
        """When enabled=False, start_watcher should refuse to start."""
        settings = MockSettings()
        settings._data["enabled"] = False
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        # Create a valid journal dir so path validation passes
        journal_dir = tmp_path / "journals"
        journal_dir.mkdir()
        (journal_dir / "Journal.2026-01-12T120000.01.log").write_text("{}")

        # Attempt to start watcher while disabled
        await watcher.start(str(journal_dir))

        # Watcher should NOT be running
        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_get_recent_activity_after_simulated_uploads(self, tmp_path):
        """Verify get_recent_activity callable returns expected entries after simulated uploads."""
        settings = MockSettings()
        activity_log = ActivityLog()
        parser = JournalParser()
        validator = EDDNValidator()
        submitter = EDDNSubmitter(settings, activity_log=activity_log)
        watcher = JournalWatcher(settings=settings, parser=parser, validator=validator, submitter=submitter)

        submitted_messages = []

        async def mock_submit(message):
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
