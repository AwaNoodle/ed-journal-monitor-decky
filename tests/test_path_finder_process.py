"""Tests for process-based ED detection in JournalPathFinder."""

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

from src.modules.path_finder import JournalPathFinder


def _make_finder(journal_path: Optional[str] = None) -> JournalPathFinder:
    settings = MagicMock()
    settings.get = MagicMock(return_value=journal_path)
    return JournalPathFinder(settings)


class TestCheckEdProcess:
    """Tests for _check_ed_process which scans /proc for ED executables."""

    def test_detects_elite_dangerous_64(self, tmp_path):
        """Should detect EliteDangerous64 process via /proc."""
        finder = _make_finder()

        # Create a fake /proc structure with an ED process
        fake_proc = tmp_path / "proc"
        fake_proc.mkdir()
        pid_dir = fake_proc / "1234"
        pid_dir.mkdir()
        (pid_dir / "comm").write_text("EliteDangerous64")

        with (
            patch.object(
                Path, "iterdir",
                side_effect=lambda self: (
                    (fake_proc / "proc").iterdir()
                    if str(self) == "/proc"
                    else self.iterdir()
                ),
            ),
            patch("src.modules.path_finder.Path") as mock_path_cls,
        ):
            mock_proc = MagicMock()
            mock_proc.iterdir.return_value = [pid_dir]
            mock_path_cls.return_value = mock_proc

            result = finder._check_ed_process()
            assert result is True

    def test_detects_elite_dangerous_64_exe(self):
        """Should detect EliteDangerous64.exe process name."""
        finder = _make_finder()

        pid_dir = MagicMock()
        pid_dir.name = "5678"
        pid_dir.__truediv__ = lambda self, key: MagicMock(
            read_text=MagicMock(return_value="EliteDangerous64.exe")
            if key == "comm"
            else MagicMock(),
        )

        with patch("src.modules.path_finder.Path") as mock_path_cls:
            mock_proc = MagicMock()
            mock_proc.iterdir.return_value = [pid_dir]
            mock_path_cls.return_value = mock_proc

            result = finder._check_ed_process()
            assert result is True

    def test_no_ed_process(self):
        """Should return False when no ED process is found."""
        finder = _make_finder()

        fake_entries = []
        for pid_name, comm_name in [("100", "steam"), ("200", "bash"), ("300", "python3")]:
            pid_dir = MagicMock()
            pid_dir.name = pid_name
            pid_dir.__truediv__ = lambda self, key, _c=comm_name: MagicMock(
                read_text=MagicMock(return_value=_c) if key == "comm" else MagicMock(),
            )
            fake_entries.append(pid_dir)

        with patch("src.modules.path_finder.Path") as mock_path_cls:
            mock_proc = MagicMock()
            mock_proc.iterdir.return_value = fake_entries
            mock_path_cls.return_value = mock_proc

            result = finder._check_ed_process()
            assert result is False

    def test_ignores_non_numeric_pid_dirs(self):
        """Should skip /proc entries that aren't PID directories."""
        finder = _make_finder()

        fake_entries = []
        for name in ["cpuinfo", "meminfo", "1234"]:
            pid_dir = MagicMock()
            pid_dir.name = name
            if name.isdigit():
                comm_mock = MagicMock()
                comm_mock.read_text.return_value = "EliteDangerous64"
                pid_dir.__truediv__ = lambda self, key, _cm=comm_mock: (
                    _cm if key == "comm" else MagicMock()
                )
            else:
                pid_dir.__truediv__ = lambda self, key: MagicMock()
            fake_entries.append(pid_dir)

        with patch("src.modules.path_finder.Path") as mock_path_cls:
            mock_proc = MagicMock()
            mock_proc.iterdir.return_value = fake_entries
            mock_path_cls.return_value = mock_proc

            result = finder._check_ed_process()
            assert result is True

    def test_handles_permission_error(self):
        """Should handle PermissionError when reading /proc entries."""
        finder = _make_finder()

        pid_dir = MagicMock()
        pid_dir.name = "999"
        comm_mock = MagicMock()
        comm_mock.read_text.side_effect = PermissionError("no access")
        pid_dir.__truediv__ = lambda self, key, _cm=comm_mock: (
            _cm if key == "comm" else MagicMock()
        )

        with patch("src.modules.path_finder.Path") as mock_path_cls:
            mock_proc = MagicMock()
            mock_proc.iterdir.return_value = [pid_dir]
            mock_path_cls.return_value = mock_proc

            result = finder._check_ed_process()
            assert result is False


class TestIsEdLikelyRunningProcessFallback:
    """Integration test for is_ed_likely_running using process detection."""

    def test_process_detection_takes_priority(self):
        """Process detection should be checked before journal mtime."""
        finder = _make_finder("/some/journal/path")

        with patch.object(finder, "_check_ed_process", return_value=True):
            result = finder.is_ed_likely_running()
            assert result is True

    def test_falls_back_to_journal_mtime(self, tmp_path):
        """When no process found, should fall back to journal file mtime."""
        # Create a journal dir with a recently-modified file
        journal_dir = tmp_path / "journals"
        journal_dir.mkdir()
        journal_file = journal_dir / "Journal.2026-05-08T120000.log"
        journal_file.write_text("{}")

        finder = _make_finder(str(journal_dir))

        with patch.object(finder, "_check_ed_process", return_value=False):
            result = finder.is_ed_likely_running()
            # File was just created, so mtime is recent
            assert result is True

    def test_returns_false_when_neither_detects(self):
        """Should return False when both methods find nothing."""
        finder = _make_finder(None)

        with patch.object(finder, "_check_ed_process", return_value=False):
            result = finder.is_ed_likely_running()
            assert result is False
