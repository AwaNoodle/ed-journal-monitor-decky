"""Tests for the system value summary derivation.

Covers: total + ranked priority bodies, the no-valuable-bodies (zero/empty)
case, top-N truncation, and the neutral/None state for disabled/in-flight/
failed/unknown lookups.
"""
from __future__ import annotations

from src.modules.edsm_read_client import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    SystemValueResult,
)
from src.modules.edsm_system_value import derive_value_summary


def _body(name: str, value: int) -> dict:
    return {"bodyId": 1, "bodyName": name, "distance": 100, "valueMax": value}


def _ok(bodies: list[dict], total_value: int = 0) -> SystemValueResult:
    return SystemValueResult(
        status=STATUS_OK,
        system_name="Test System",
        total_value=total_value,
        valuable_bodies=bodies,
    )


class TestSummaryWithPriorityBodies:
    def test_total_and_ranked_bodies(self):
        bodies = [_body("Low", 100), _body("High", 900), _body("Mid", 500)]
        result = _ok(bodies, total_value=1500)

        summary = derive_value_summary(result)

        assert summary is not None
        assert summary.total_value == 1500
        assert [b["name"] for b in summary.priority_bodies] == ["High", "Mid", "Low"]
        assert [b["value"] for b in summary.priority_bodies] == [900, 500, 100]

    def test_top_n_truncates_to_default_of_three(self):
        bodies = [_body(f"Body{i}", i * 100) for i in range(1, 6)]
        result = _ok(bodies, total_value=1500)

        summary = derive_value_summary(result)

        assert summary is not None
        assert len(summary.priority_bodies) == 3
        assert [b["value"] for b in summary.priority_bodies] == [500, 400, 300]

    def test_top_n_is_configurable(self):
        bodies = [_body(f"Body{i}", i * 100) for i in range(1, 6)]
        result = _ok(bodies, total_value=1500)

        summary = derive_value_summary(result, top_n=2)

        assert summary is not None
        assert len(summary.priority_bodies) == 2


class TestSummaryWithNoValuableBodies:
    def test_zero_value_no_bodies_reports_zero_state(self):
        result = _ok([], total_value=0)

        summary = derive_value_summary(result)

        assert summary is not None
        assert summary.total_value == 0
        assert summary.priority_bodies == []

    def test_nonzero_total_but_no_valuable_bodies(self):
        """A modest system total with no standout bodies is not an error state."""
        result = _ok([], total_value=2205)

        summary = derive_value_summary(result)

        assert summary is not None
        assert summary.total_value == 2205
        assert summary.priority_bodies == []


class TestNeutralSummary:
    def test_unavailable_is_neutral(self):
        result = SystemValueResult(status=STATUS_UNAVAILABLE, system_name="Sol")
        assert derive_value_summary(result) is None

    def test_unknown_system_is_neutral(self):
        result = SystemValueResult(status=STATUS_UNKNOWN, system_name="Virgin System")
        assert derive_value_summary(result) is None

    def test_none_result_is_neutral(self):
        assert derive_value_summary(None) is None


class TestModuleDocstring:
    def test_module_docstring_is_accessible(self):
        import src.modules.edsm_system_value as m
        assert m.__doc__ is not None
        assert "value" in m.__doc__
