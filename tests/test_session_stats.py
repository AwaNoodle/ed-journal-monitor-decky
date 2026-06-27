"""
Tests for the SessionStatsAccumulator module.

Covers counting semantics (jumps, distance, bodies scanned, first discoveries,
current system/commander) and session boundary/reset semantics.
"""

import pytest

from src.modules.parser import ParsedEvent
from src.modules.session_stats import SessionStats, SessionStatsAccumulator


def make_event(event_type: str, **fields) -> ParsedEvent:
    """Build a ParsedEvent with the given event type and raw payload fields."""
    raw = {"timestamp": "2026-01-12T12:00:00Z", "event": event_type}
    raw.update(fields)
    return ParsedEvent(raw=raw, event_type=event_type, timestamp=raw["timestamp"])


@pytest.fixture
def accumulator() -> SessionStatsAccumulator:
    return SessionStatsAccumulator()


class TestCounting:
    """Counting semantics for tracked events."""

    def test_fsdjump_increments_jumps_distance_and_system(self, accumulator):
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=15.3))
        assert accumulator.stats.jumps == 1
        assert accumulator.stats.distance_ly == pytest.approx(15.3)
        assert accumulator.stats.star_system == "Sol"

    def test_multiple_fsdjumps_accumulate(self, accumulator):
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        accumulator.observe(make_event("FSDJump", StarSystem="Alpha Centauri", JumpDist=4.4))
        assert accumulator.stats.jumps == 2
        assert accumulator.stats.distance_ly == pytest.approx(14.4)
        assert accumulator.stats.star_system == "Alpha Centauri"

    def test_fsdjump_without_jumpdist_still_counts_jump(self, accumulator):
        accumulator.observe(make_event("FSDJump", StarSystem="Sol"))
        assert accumulator.stats.jumps == 1
        assert accumulator.stats.distance_ly == pytest.approx(0.0)

    def test_scan_increments_bodies_scanned(self, accumulator):
        accumulator.observe(make_event("Scan", ScanType="Detailed", BodyName="Sol 1"))
        assert accumulator.stats.bodies_scanned == 1
        assert accumulator.stats.first_discoveries == 0

    def test_scan_was_discovered_false_increments_first_discoveries(self, accumulator):
        accumulator.observe(make_event("Scan", ScanType="Detailed", WasDiscovered=False))
        assert accumulator.stats.bodies_scanned == 1
        assert accumulator.stats.first_discoveries == 1

    def test_scan_was_discovered_true_does_not_increment_first_discoveries(self, accumulator):
        accumulator.observe(make_event("Scan", ScanType="Detailed", WasDiscovered=True))
        assert accumulator.stats.bodies_scanned == 1
        assert accumulator.stats.first_discoveries == 0

    def test_scan_missing_was_discovered_treated_as_not_first(self, accumulator):
        accumulator.observe(make_event("Scan", ScanType="AutoScan"))
        assert accumulator.stats.bodies_scanned == 1
        assert accumulator.stats.first_discoveries == 0

    def test_location_updates_current_system_without_counting_jump(self, accumulator):
        accumulator.observe(make_event("Location", StarSystem="Shinrarta Dezhra"))
        assert accumulator.stats.star_system == "Shinrarta Dezhra"
        assert accumulator.stats.jumps == 0

    def test_non_tracked_event_is_ignored(self, accumulator):
        before = SessionStats(**vars(accumulator.stats))
        accumulator.observe(make_event("ReceiveText", Message="hello"))
        assert accumulator.stats == before

    def test_non_tracked_event_raises_nothing(self, accumulator):
        # Should not raise even with an unexpected/empty payload
        accumulator.observe(make_event("Music"))


class TestBoundaryAndReset:
    """Session boundary and reset semantics."""

    def test_reset_zeros_all_counters(self, accumulator):
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        accumulator.observe(make_event("Scan", WasDiscovered=False))
        accumulator.reset()
        assert accumulator.stats == SessionStats()

    def test_soft_reset_on_different_commander_loadgame(self, accumulator):
        accumulator.observe(make_event("LoadGame", Commander="Jameson"))
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        accumulator.observe(make_event("Scan", WasDiscovered=False))
        accumulator.observe(make_event("LoadGame", Commander="Hero"))
        assert accumulator.stats.commander == "Hero"
        assert accumulator.stats.jumps == 0
        assert accumulator.stats.distance_ly == pytest.approx(0.0)
        assert accumulator.stats.bodies_scanned == 0
        assert accumulator.stats.first_discoveries == 0

    def test_no_reset_on_same_commander_loadgame(self, accumulator):
        accumulator.observe(make_event("LoadGame", Commander="Jameson"))
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        accumulator.observe(make_event("LoadGame", Commander="Jameson"))
        assert accumulator.stats.commander == "Jameson"
        assert accumulator.stats.jumps == 1
        assert accumulator.stats.distance_ly == pytest.approx(10.0)

    def test_stats_preserved_across_continued_file_roll(self, accumulator):
        accumulator.observe(make_event("LoadGame", Commander="Jameson"))
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        # A Continued event marks a journal file roll; stats must survive it.
        accumulator.observe(make_event("Continued", Part=2))
        accumulator.observe(make_event("FSDJump", StarSystem="Wolf 359", JumpDist=7.8))
        assert accumulator.stats.jumps == 2
        assert accumulator.stats.distance_ly == pytest.approx(17.8)


class TestChangeNotification:
    """Emit-on-change and coalescing (suspend/resume) behaviour."""

    def test_on_change_called_when_stats_change(self):
        seen = []
        acc = SessionStatsAccumulator(on_change=seen.append)
        acc.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        assert len(seen) == 1
        assert seen[-1]["jumps"] == 1

    def test_on_change_not_called_for_ignored_event(self):
        seen = []
        acc = SessionStatsAccumulator(on_change=seen.append)
        acc.observe(make_event("ReceiveText", Message="hi"))
        assert seen == []

    def test_reset_emits_zeroed_stats(self):
        seen = []
        acc = SessionStatsAccumulator(on_change=seen.append)
        acc.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        seen.clear()
        acc.reset()
        assert len(seen) == 1
        assert seen[-1]["jumps"] == 0

    def test_suspend_coalesces_into_single_emit_on_resume(self):
        seen = []
        acc = SessionStatsAccumulator(on_change=seen.append)
        acc.suspend()
        acc.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        acc.observe(make_event("FSDJump", StarSystem="Wolf 359", JumpDist=7.8))
        acc.observe(make_event("Scan", WasDiscovered=False))
        assert seen == []  # nothing emitted while suspended
        acc.resume()
        assert len(seen) == 1  # one settled emit
        assert seen[-1]["jumps"] == 2
        assert seen[-1]["bodies_scanned"] == 1

    def test_resume_without_changes_does_not_emit(self):
        seen = []
        acc = SessionStatsAccumulator(on_change=seen.append)
        acc.suspend()
        acc.resume()
        assert seen == []

    def test_get_stats_returns_current_snapshot_dict(self, accumulator):
        accumulator.observe(make_event("FSDJump", StarSystem="Sol", JumpDist=10.0))
        snapshot = accumulator.get_stats()
        assert snapshot == {
            "commander": "",
            "star_system": "Sol",
            "jumps": 1,
            "distance_ly": pytest.approx(10.0),
            "bodies_scanned": 0,
            "first_discoveries": 0,
        }
