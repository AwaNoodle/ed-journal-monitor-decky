"""Covers scripts/verify-tag-version.sh, which stops a tag/package.json
mismatch from being packaged and published. package.json ships inside the
zip and is read at runtime for the EDDN softwareVersion header, so a
mismatch here means a published plugin misreports its own version."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-tag-version.sh"


def run(args):
    return subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def package_json(tmp_path):
    path = tmp_path / "package.json"
    path.write_text('{"name": "ed-journal-monitor", "version": "1.2.3"}')
    return path


def test_matching_tag_passes(package_json):
    result = run(["v1.2.3", str(package_json)])
    assert result.returncode == 0, result.stderr
    assert "matches" in result.stdout


def test_mismatched_tag_fails(package_json):
    result = run(["v9.9.9", str(package_json)])
    assert result.returncode == 1
    assert "::error::tag v9.9.9 does not match package.json version 1.2.3" in result.stdout


def test_empty_tag_is_a_usage_error(package_json):
    result = run(["", str(package_json)])
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_missing_tag_is_a_usage_error(package_json):
    result = subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_tag_missing_v_prefix_fails(package_json):
    result = run(["1.2.3", str(package_json)])
    assert result.returncode == 1
    # A bare "1.2.3" tag never equals "v$pkg" - pins the exact message rather
    # than any ::error::, so a check that only compares numerals (dropping
    # the "v" requirement) cannot pass this silently.
    assert "::error::tag 1.2.3 does not match package.json version 1.2.3" in result.stdout


def test_missing_package_json_is_a_usage_error(tmp_path):
    result = run(["v1.2.3", str(tmp_path / "nope.json")])
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_malformed_package_json_fails_cleanly(tmp_path):
    """jq aborts under set -e on malformed JSON - must not be swallowed into
    a false pass or an unhandled crash."""
    path = tmp_path / "package.json"
    path.write_text("{not valid json")
    result = run(["v1.2.3", str(path)])
    assert result.returncode != 0


def test_default_package_json_path(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"version": "4.5.6"}')
    monkeypatch.chdir(tmp_path)
    result = run(["v4.5.6"])
    assert result.returncode == 0, result.stderr
