from __future__ import annotations

"""Tests for process-based ED detection in JournalPathFinder."""

from unittest.mock import MagicMock, patch

from src.modules.path_finder import JournalPathFinder


class _FakeProcEntry:
    def __init__(self, name: str, comm_text: str | Exception | None = None):
        self.name = name
        self._comm_text = comm_text

    def __truediv__(self, key: str):
        file_mock = MagicMock()
        if key == "comm":
            if isinstance(self._comm_text, Exception):
                file_mock.read_text.side_effect = self._comm_text
            else:
                file_mock.read_text.return_value = self._comm_text or ""
        return file_mock


class _FakeProcPath:
    def __init__(self, entries: list[_FakeProcEntry]):
        self._entries = entries

    def iterdir(self):
        return iter(self._entries)


def _make_finder(journal_path: str | None = None) -> JournalPathFinder:
    settings = MagicMock()
    settings.get = MagicMock(return_value=journal_path)
    return JournalPathFinder(settings)


class TestCheckEdProcess:
    """Tests for _check_ed_process which scans /proc for ED executables."""

    def test_detects_elite_dangerous_64(self):
        finder = _make_finder()
        entries = [_FakeProcEntry("1234", "EliteDangerous64")]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is True

    def test_detects_elite_dangerous_64_exe(self):
        finder = _make_finder()
        entries = [_FakeProcEntry("5678", "EliteDangerous64.exe")]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is True

    def test_detects_kernel_truncated_comm_name(self):
        finder = _make_finder()
        entries = [_FakeProcEntry("9012", "EliteDangerous6")]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is True

    def test_no_ed_process(self):
        finder = _make_finder()
        entries = [
            _FakeProcEntry("100", "steam"),
            _FakeProcEntry("200", "bash"),
            _FakeProcEntry("300", "python3"),
        ]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is False

    def test_ignores_non_numeric_pid_dirs(self):
        finder = _make_finder()
        entries = [
            _FakeProcEntry("cpuinfo", "EliteDangerous64"),
            _FakeProcEntry("meminfo", "EliteDangerous64"),
            _FakeProcEntry("1234", "EliteDangerous64"),
        ]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is True

    def test_handles_permission_error(self):
        finder = _make_finder()
        entries = [_FakeProcEntry("999", PermissionError("no access"))]

        with patch("src.modules.path_finder.Path", return_value=_FakeProcPath(entries)):
            assert finder._check_ed_process() is False


class TestIsEdLikelyRunningProcessFallback:
    """Integration test for is_ed_likely_running using process detection."""

    def test_process_detection_takes_priority(self):
        finder = _make_finder("/some/journal/path")

        with patch.object(finder, "_check_ed_process", return_value=True):
            assert finder.is_ed_likely_running() is True

    def test_falls_back_to_journal_mtime(self, tmp_path):
        journal_dir = tmp_path / "journals"
        journal_dir.mkdir()
        journal_file = journal_dir / "Journal.2026-05-08T120000.log"
        journal_file.write_text("{}")

        finder = _make_finder(str(journal_dir))

        with patch.object(finder, "_check_ed_process", return_value=False):
            assert finder.is_ed_likely_running() is True

    def test_returns_false_when_neither_detects(self):
        finder = _make_finder(None)

        with patch.object(finder, "_check_ed_process", return_value=False):
            assert finder.is_ed_likely_running() is False
