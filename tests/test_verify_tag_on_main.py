"""Covers scripts/verify-tag-on-main.sh, the guard that stops a tag on an
unmerged branch from publishing a release. Builds real git repos rather than
mocking git, because the whole point of the guard is git's own ancestry
semantics under a narrow, tag-checkout fetch refspec - a mock would just
restate the implementation."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify-tag-on-main.sh"
GIT = shutil.which("git")

GIT_ENV_EXTRA = {
    # Isolate from the developer machine's global git config (signing,
    # hooks, unrelated user identity) so this runs identically anywhere.
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def git(*args, cwd, env=None, check=True):
    full_env = {**os.environ, **GIT_ENV_EXTRA, **(env or {})}
    return subprocess.run(  # noqa: S603
        [GIT, *args],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
        check=check,
    )


def run(args, cwd):
    return subprocess.run(  # noqa: S603
        [shutil.which("bash"), str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def rev_parse(cwd, ref):
    return git("rev-parse", ref, cwd=cwd).stdout.strip()


@pytest.fixture
def remote_and_clone(tmp_path):
    """A bare 'remote' with main history A-B-C, an unmerged 'feature' branch
    D forked *behind* main's tip (off A), and an unmerged 'ahead' branch E
    forked *from* main's tip (off C) - the realistic shape of an unmerged
    branch, and the one that pins ancestry direction (see finding 2 in
    reports/2026-08-12-review-release-guard-extraction.md: a fixture that
    only forks behind the tip cannot tell --is-ancestor's argument order
    apart). Plus a normal (non-shallow) clone with disabled signing/hooks."""
    remote = tmp_path / "remote.git"
    git("init", "--bare", "-q", str(remote), cwd=tmp_path)

    work = tmp_path / "work"
    git("clone", "-q", str(remote), str(work), cwd=tmp_path)
    git("config", "commit.gpgsign", "false", cwd=work)
    git("config", "core.hooksPath", "/dev/null", cwd=work)

    (work / "f.txt").write_text("a\n")
    git("add", "f.txt", cwd=work)
    git("commit", "-q", "-m", "A", cwd=work)
    sha_a = rev_parse(work, "HEAD")

    (work / "f.txt").write_text("a\nb\n")
    git("commit", "-q", "-am", "B", cwd=work)

    (work / "f.txt").write_text("a\nb\nc\n")
    git("commit", "-q", "-am", "C", cwd=work)
    sha_c = rev_parse(work, "HEAD")

    git("push", "-q", "origin", "HEAD:main", cwd=work)

    git("checkout", "-q", "-b", "feature", sha_a, cwd=work)
    (work / "feature.txt").write_text("d\n")
    git("add", "feature.txt", cwd=work)
    git("commit", "-q", "-m", "D", cwd=work)
    sha_d = rev_parse(work, "HEAD")
    git("push", "-q", "origin", "feature:feature", cwd=work)

    git("checkout", "-q", "-b", "ahead", sha_c, cwd=work)
    (work / "ahead.txt").write_text("e\n")
    git("add", "ahead.txt", cwd=work)
    git("commit", "-q", "-m", "E", cwd=work)
    sha_e = rev_parse(work, "HEAD")
    git("push", "-q", "origin", "ahead:ahead", cwd=work)

    git("checkout", "-q", "main", cwd=work)

    return {
        "remote": remote,
        "work": work,
        "sha_a": sha_a,
        "sha_c": sha_c,
        "sha_d": sha_d,
        "sha_e": sha_e,
    }


def test_commit_on_main_passes(remote_and_clone):
    r = remote_and_clone
    result = run(
        [r["sha_c"], "v1.0.0", f"file://{r['remote']}", "main"], cwd=r["work"]
    )
    assert result.returncode == 0, result.stderr
    assert "is on main" in result.stdout


def test_commit_on_unmerged_branch_fails(remote_and_clone):
    r = remote_and_clone
    result = run(
        [r["sha_d"], "v1.0.0", f"file://{r['remote']}", "main"], cwd=r["work"]
    )
    assert result.returncode == 1
    assert "::error::v1.0.0" in result.stdout
    assert "not on main" in result.stdout


def test_commit_ahead_of_main_on_an_unmerged_branch_fails(remote_and_clone):
    """Pins the ancestry *direction*: a branch cut from main's tip (the
    realistic shape of an in-flight feature branch) is a descendant of main,
    not an ancestor of it. Swapping the --is-ancestor arguments makes both
    directions report the same verdict for a branch that forks behind the
    tip (sha_d, above) but not for one that forks from it - so this is the
    fixture that actually distinguishes the two argument orders."""
    r = remote_and_clone
    result = run(
        [r["sha_e"], "v1.0.0", f"file://{r['remote']}", "main"], cwd=r["work"]
    )
    assert result.returncode == 1
    assert "::error::v1.0.0" in result.stdout
    assert "not on main" in result.stdout


def test_missing_sha_is_a_usage_error(remote_and_clone):
    result = run([], cwd=remote_and_clone["work"])
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_annotation_falls_back_to_the_sha_without_a_tag_label(remote_and_clone):
    r = remote_and_clone
    result = run([r["sha_d"], "", f"file://{r['remote']}", "main"], cwd=r["work"])
    assert result.returncode == 1
    assert f"::error::{r['sha_d']} is not on main" in result.stdout


def test_shallow_clone_does_not_falsely_report_on_main(tmp_path, remote_and_clone):
    """fetch-depth: 0 exists in the workflow specifically so this check has
    real history to walk. Re-fetching a ref the shallow clone already has
    (main, cloned at depth 1) is a no-op that does not deepen it, so an
    older-but-genuinely-on-main commit (sha_a, main's root) has no local
    object at all. `git merge-base --is-ancestor` then errors rather than
    answering - and the script must propagate that as a failure, never as
    a false "yes". The safe direction is a wrongly-blocked release (loud,
    fixable by re-running with full history), never a wrongly-published one."""
    r = remote_and_clone
    shallow = tmp_path / "shallow"
    git(
        "clone",
        "-q",
        "--depth",
        "1",
        "--branch",
        "main",
        f"file://{r['remote']}",
        str(shallow),
        cwd=tmp_path,
    )
    git("config", "commit.gpgsign", "false", cwd=shallow)

    result = run(
        [r["sha_a"], "v1.0.0", f"file://{r['remote']}", "main"], cwd=shallow
    )
    assert result.returncode == 1  # fails closed - never silently "on main"
    assert "::error::" in result.stdout
