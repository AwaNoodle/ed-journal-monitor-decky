"""Covers scripts/extract-release-notes.sh, which produces the GitHub Release
notes. A silent failure here publishes a release with empty notes, so the
contract is tested rather than trusted."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "extract-release-notes.sh"
REAL_CHANGELOG = REPO_ROOT / "CHANGELOG.md"

SAMPLE = """# Changelog

## [Unreleased]

### Added

- Something not yet released

## [0.7.0] - 2026-07-28

### Added

- Worth-scanning arrival notifications

### Fixed

- A bug

## [0.6.0] - 2026-07-01

### Added

- Older thing
"""


def run(version, changelog):
    return subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT), version, str(changelog)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def changelog(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE)
    return path


def test_extracts_the_requested_section(changelog):
    result = run("0.7.0", changelog)
    assert result.returncode == 0
    assert "Worth-scanning arrival notifications" in result.stdout
    assert "A bug" in result.stdout


def test_stops_at_the_next_version_header(changelog):
    result = run("0.7.0", changelog)
    assert "Older thing" not in result.stdout
    assert "## [0.6.0]" not in result.stdout


def test_excludes_the_version_header_itself(changelog):
    result = run("0.7.0", changelog)
    assert "## [0.7.0]" not in result.stdout


def test_never_returns_the_unreleased_section(changelog):
    result = run("0.7.0", changelog)
    assert "Something not yet released" not in result.stdout


def test_missing_section_fails_loudly(changelog):
    result = run("9.9.9", changelog)
    assert result.returncode == 1
    assert "9.9.9" in result.stderr


def test_empty_section_fails_loudly(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [0.8.0] - 2026-08-12\n\n## [0.7.0] - 2026-07-28\n\n- Real\n")
    result = run("0.8.0", path)
    assert result.returncode == 1
    assert "0.8.0" in result.stderr


def test_version_is_matched_literally_not_as_a_regex(tmp_path):
    """A regex matcher interpolates the version as the pattern, so the dots in
    0.7.0 become wildcards and match a 0X7X0 header - publishing that section's
    notes under the wrong version."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [0X7X0] - 2026-07-28\n\n- Wrong section\n")
    result = run("0.7.0", path)
    assert result.returncode == 1


def test_does_not_prefix_match_a_longer_version(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [0.7.01] - 2026-08-12\n\n- Longer version\n")
    result = run("0.7.0", path)
    assert result.returncode == 1


def test_missing_changelog_file_is_a_usage_error(tmp_path):
    result = run("0.7.0", tmp_path / "nope.md")
    assert result.returncode == 2


def test_stops_at_a_bracket_less_heading(tmp_path):
    """A bracket-less '## Heading' (no version) following the target section
    must still terminate it - the terminator check must not require the
    literal '## [' prefix, or such a heading (and everything after it) gets
    swallowed into the release notes."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## [0.7.0] - 2026-07-28\n\n"
        "- Worth-scanning arrival notifications\n\n"
        "## Older releases\n\n"
        "- Ancient history\n"
    )
    result = run("0.7.0", path)
    assert result.returncode == 0
    assert "Worth-scanning arrival notifications" in result.stdout
    assert "Older releases" not in result.stdout
    assert "Ancient history" not in result.stdout


def test_does_not_stop_at_a_subsection_heading(tmp_path):
    """'### Fixed' etc. are subsections within a version's own notes, not
    section terminators - they must stay in the extracted notes."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n"
        "## [0.7.0] - 2026-07-28\n\n"
        "### Added\n\n"
        "- A feature\n\n"
        "### Fixed\n\n"
        "- A bug\n"
    )
    result = run("0.7.0", path)
    assert result.returncode == 0
    assert "### Added" in result.stdout
    assert "### Fixed" in result.stdout
    assert "A feature" in result.stdout
    assert "A bug" in result.stdout


def test_real_changelog_latest_release_has_notes():
    """Regression guard against the committed CHANGELOG.md: the most recent
    released version must still extract non-empty notes."""
    result = run("0.7.0", REAL_CHANGELOG)
    assert result.returncode == 0
    assert result.stdout.strip()
