"""Covers scripts/verify-package-contents.sh, the guard that stops a broken
or misversioned zip from being attached to a GitHub Release. A silent gap
here ships a plugin missing its backend to every user who installs it - this
is what caught a real vacuous-check bug in #14 (a zip with all backend .py
files stripped but the bare `bin/src/modules/` directory entry retained used
to pass)."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-package-contents.sh"

REQUIRED_FILES = [
    "ed-journal-monitor/package.json",
    "ed-journal-monitor/plugin.json",
    "ed-journal-monitor/main.py",
    "ed-journal-monitor/dist/index.js",
]


def run(zip_path, tag):
    return subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT), str(zip_path), tag],
        capture_output=True,
        text=True,
        check=False,
    )


def make_zip(path, *, version="1.2.3", entries=None, extra_files=None):
    """Build a real, valid zip layout unless overridden by the caller."""
    if entries is None:
        entries = dict(required_files_content(version))
    if extra_files:
        entries.update(extra_files)
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def required_files_content(version):
    return {
        "ed-journal-monitor/package.json": f'{{"version": "{version}"}}',
        "ed-journal-monitor/plugin.json": "{}",
        "ed-journal-monitor/main.py": "# main\n",
        "ed-journal-monitor/dist/index.js": "// bundle\n",
        "ed-journal-monitor/bin/src/modules/watcher.py": "# watcher\n",
        "ed-journal-monitor/bin/src/modules/parser.py": "# parser\n",
    }


@pytest.fixture
def valid_zip(tmp_path):
    return make_zip(tmp_path / "release.zip")


def test_valid_zip_passes(valid_zip):
    result = run(valid_zip, "v1.2.3")
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout


def test_backend_modules_stripped_but_directory_entry_retained_fails(tmp_path):
    """Regression case for the #14 bug: a directory entry with no real .py
    files inside it used to pass the old grep -q check."""
    entries = required_files_content("1.2.3")
    del entries["ed-journal-monitor/bin/src/modules/watcher.py"]
    del entries["ed-journal-monitor/bin/src/modules/parser.py"]
    # A directory entry, not a file - zipfile writes it as a name ending "/".
    entries["ed-journal-monitor/bin/src/modules/"] = ""
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "::error::" in result.stdout
    assert "no backend python modules" in result.stdout


def test_watcher_removed_but_other_modules_present_fails(tmp_path):
    """Guards the -Fxq check on watcher.py specifically: some backend .py
    files present is not the same as the required one being present."""
    entries = required_files_content("1.2.3")
    del entries["ed-journal-monitor/bin/src/modules/watcher.py"]
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "watcher.py missing" in result.stdout


def test_watcher_present_only_as_a_near_miss_name_fails(tmp_path):
    """Guards the -Fxq check on watcher.py against a -q weakening: a
    '.bak' near-miss alongside another genuine .py module satisfies the -E
    regex on the modules check, so only the exact-line watcher check can
    reject this."""
    entries = required_files_content("1.2.3")
    del entries["ed-journal-monitor/bin/src/modules/watcher.py"]
    entries["ed-journal-monitor/bin/src/modules/watcher.py.bak"] = "# stale\n"
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "watcher.py missing" in result.stdout


def test_required_file_present_only_as_a_longer_path_fails(tmp_path):
    """Guards grep -Fxq against a -q (substring) weakening: a path that
    merely *contains* the required path as a suffix is not the required
    file itself, so the check must reject it even though the literal
    plugin.json filename does appear in the listing."""
    entries = required_files_content("1.2.3")
    del entries["ed-journal-monitor/plugin.json"]
    entries["backup/ed-journal-monitor/plugin.json"] = "{}"
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "::error::ed-journal-monitor/plugin.json missing" in result.stdout


def test_tree_nested_one_level_deeper_fails(tmp_path):
    entries = {
        f"extra-wrapper/{name}": content
        for name, content in required_files_content("1.2.3").items()
    }
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    # Pin which check fired: the required-files loop, not the backend-modules
    # regex (which would also reject this zip, for the wrong reason, and
    # mask a weakened required-files check).
    assert "::error::ed-journal-monitor/package.json missing" in result.stdout


def test_bundled_version_mismatch_fails(valid_zip):
    result = run(valid_zip, "v9.9.9")
    assert result.returncode == 1
    assert "::error::" in result.stdout
    assert "expected 9.9.9" in result.stdout


@pytest.mark.parametrize("missing", REQUIRED_FILES)
def test_each_required_file_removed_in_turn_fails(tmp_path, missing):
    entries = required_files_content("1.2.3")
    del entries[missing]
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert f"::error::{missing} missing" in result.stdout


def test_corrupt_zip_fails_cleanly(tmp_path):
    """A non-zip file must not be silently treated as an empty/valid
    archive - unzip aborts under set -e, which the caller sees as a
    failure, not a false pass."""
    bad_zip = tmp_path / "release.zip"
    bad_zip.write_text("not a zip file")

    result = run(bad_zip, "v1.2.3")
    assert result.returncode != 0  # non-zero regardless of unzip's exact abort code


def test_malformed_bundled_package_json_fails_cleanly(tmp_path):
    """Malformed JSON inside the zip must abort rather than let jq's error
    output silently compare unequal-but-truthy against the tag."""
    entries = required_files_content("1.2.3")
    entries["ed-journal-monitor/package.json"] = "{not valid json"
    zip_path = make_zip(tmp_path / "release.zip", entries=entries)

    result = run(zip_path, "v1.2.3")
    assert result.returncode != 0


def test_nonexistent_zip_fails_cleanly(tmp_path):
    result = run(tmp_path / "nope.zip", "v1.2.3")
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_missing_zip_arg_is_a_usage_error():
    result = subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_missing_tag_arg_is_a_usage_error(valid_zip):
    result = subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT), str(valid_zip)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_compiled_bytecode_file_fails(tmp_path):
    """A .pyc anywhere in the zip must be rejected. CI runs pytest before
    packaging, which populates src/modules/__pycache__; the copy step used
    to sweep that into the release zip, shipping stale bytecode built for
    the wrong Python version and roughly doubling the download size."""
    zip_path = make_zip(
        tmp_path / "release.zip",
        extra_files={
            "ed-journal-monitor/bin/src/modules/__pycache__/watcher.cpython-39.pyc": "\x00\x00",
        },
    )

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "::error::" in result.stdout
    assert "compiled python" in result.stdout.lower()


def test_pycache_directory_entry_alone_fails(tmp_path):
    """The bare __pycache__ directory entry, with no .pyc inside it, must
    also fail: a check that only looked for '*.pyc' would pass this zip and
    still ship a stray directory the plugin never needs."""
    zip_path = make_zip(
        tmp_path / "release.zip",
        extra_files={"ed-journal-monitor/bin/src/modules/__pycache__/": ""},
    )

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "::error::" in result.stdout
    assert "compiled python" in result.stdout.lower()


def test_pyc_outside_the_modules_directory_fails(tmp_path):
    """The check is not scoped to bin/src/modules/ - bytecode alongside
    main.py at the plugin root is just as unwanted, so a check anchored to
    the modules path would be a silent gap."""
    zip_path = make_zip(
        tmp_path / "release.zip",
        extra_files={"ed-journal-monitor/__pycache__/main.cpython-39.pyc": "\x00\x00"},
    )

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 1
    assert "compiled python" in result.stdout.lower()


def test_filename_merely_containing_pyc_is_not_rejected(tmp_path):
    """Guards the .pyc check against an over-broad substring match: a real
    module whose name happens to contain 'pyc' is legitimate and must not
    abort a good release."""
    zip_path = make_zip(
        tmp_path / "release.zip",
        extra_files={"ed-journal-monitor/bin/src/modules/pycache_helper.py": "# ok\n"},
    )

    result = run(zip_path, "v1.2.3")
    assert result.returncode == 0, result.stdout + result.stderr
