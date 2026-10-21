import json
from pathlib import Path

import pytest

from vulntrace.dataset.vulndb import (
    VulndbError,
    current_head,
    ensure_vulndb_snapshot,
    is_up_to_date,
    iter_report_paths,
    load_config,
    pinned_commit,
    reports_dir,
)

CONFIG = {"repo_url": "https://github.com/golang/vulndb", "commit": "a" * 40, "pinned_at": "2026-10-21"}


def test_real_config_file_is_well_formed():
    cfg = load_config()
    assert cfg["repo_url"] == "https://github.com/golang/vulndb"
    assert len(cfg["commit"]) == 40 and all(c in "0123456789abcdef" for c in cfg["commit"])
    assert "licence" in cfg and "CC-BY-4.0" in cfg["licence"]["data"]


def test_pinned_commit_and_repo_url():
    assert pinned_commit(CONFIG) == "a" * 40


class FakeGit:
    """Replays canned (returncode, stdout, stderr) results keyed by the git subcommand.

    `head` is the simulated current HEAD (None = not a git repo yet); a successful
    `git checkout` moves it to `head_after`, mirroring the real effect."""

    def __init__(self, scripted: dict[tuple, tuple], head: str | None = None, head_after: str | None = None):
        self.scripted = scripted
        self.head = head
        self.head_after_checkout = head_after
        self.calls: list[list[str]] = []

    def __call__(self, args, cwd, capture_output, text, timeout=60.0):
        self.calls.append(args)
        if args[:2] == ["git", "init"]:
            (Path(cwd) / ".git").mkdir(exist_ok=True)
        if args[:2] == ["git", "rev-parse"] and args[2:] == ["HEAD"]:
            if self.head is None:
                return _cp(1, "", "fatal: not a git repository")
            return _cp(0, self.head, "")
        result = self._match(args)
        if args[:2] == ["git", "checkout"] and result[0] == 0 and self.head_after_checkout is not None:
            self.head = self.head_after_checkout
        return _cp(*result)

    def _match(self, args) -> tuple:
        key = tuple(args)
        for pattern, result in self.scripted.items():
            if key[: len(pattern)] == pattern:
                return result
        return (0, "", "")


def _cp(rc, out, err):
    import subprocess

    return subprocess.CompletedProcess([], rc, out, err)


def test_current_head_is_none_when_not_a_git_dir(tmp_path):
    assert current_head(tmp_path, runner=FakeGit({})) is None


def test_is_up_to_date_compares_head_to_pin(tmp_path):
    (tmp_path / ".git").mkdir()
    assert is_up_to_date(tmp_path, CONFIG, runner=FakeGit({}, head=CONFIG["commit"] + "\n"))
    assert not is_up_to_date(tmp_path, CONFIG, runner=FakeGit({}, head="deadbeef" * 5))


def test_ensure_snapshot_clones_and_sparse_checks_out(tmp_path):
    cache = tmp_path / "vulndb-src"
    git = FakeGit({
        ("git", "init"): (0, "", ""),
        ("git", "remote"): (0, "", ""),
        ("git", "fetch"): (0, "", ""),
        ("git", "sparse-checkout"): (0, "", ""),
        ("git", "checkout"): (0, "", ""),
    }, head_after=CONFIG["commit"])
    (cache / "data" / "reports").mkdir(parents=True)  # simulate the checkout's effect
    got = ensure_vulndb_snapshot(cache, CONFIG, runner=git)
    assert got == cache
    assert ["git", "fetch", "--depth", "1", "origin", CONFIG["commit"]] in git.calls
    assert ["git", "sparse-checkout", "set", "data/reports"] in git.calls


def test_ensure_snapshot_is_a_no_op_when_already_at_the_pin(tmp_path):
    cache = tmp_path / "vulndb-src"
    (cache / ".git").mkdir(parents=True)
    (cache / "data" / "reports").mkdir(parents=True)
    git = FakeGit({}, head=CONFIG["commit"])
    ensure_vulndb_snapshot(cache, CONFIG, runner=git)
    assert not any(c[:2] == ["git", "fetch"] for c in git.calls)


def test_ensure_snapshot_raises_on_fetch_failure(tmp_path):
    cache = tmp_path / "vulndb-src"
    git = FakeGit({
        ("git", "init"): (0, "", ""), ("git", "remote"): (0, "", ""),
        ("git", "fetch"): (1, "", "fatal: could not fetch"),
    })
    with pytest.raises(VulndbError) as exc:
        ensure_vulndb_snapshot(cache, CONFIG, runner=git)
    assert exc.value.code == "FETCH_FAILED"


def test_ensure_snapshot_raises_on_pin_mismatch(tmp_path):
    """A checkout that lands on the wrong commit is a hard error, never a silent fallback."""
    cache = tmp_path / "vulndb-src"
    git = FakeGit({
        ("git", "init"): (0, "", ""), ("git", "remote"): (0, "", ""), ("git", "fetch"): (0, "", ""),
        ("git", "sparse-checkout"): (0, "", ""), ("git", "checkout"): (0, "", ""),
    }, head_after="wrong" * 8)
    (cache / "data" / "reports").mkdir(parents=True)
    with pytest.raises(VulndbError) as exc:
        ensure_vulndb_snapshot(cache, CONFIG, runner=git)
    assert exc.value.code == "PIN_MISMATCH"


def test_ensure_snapshot_raises_when_reports_dir_missing_after_checkout(tmp_path):
    cache = tmp_path / "vulndb-src"
    git = FakeGit({
        ("git", "init"): (0, "", ""), ("git", "remote"): (0, "", ""), ("git", "fetch"): (0, "", ""),
        ("git", "sparse-checkout"): (0, "", ""), ("git", "checkout"): (0, "", ""),
    }, head_after=CONFIG["commit"])
    with pytest.raises(VulndbError) as exc:
        ensure_vulndb_snapshot(cache, CONFIG, runner=git)
    assert exc.value.code == "EMPTY_SNAPSHOT"


def test_iter_report_paths_sorted(tmp_path):
    d = reports_dir(tmp_path)
    d.mkdir(parents=True)
    for name in ["GO-2026-0002.yaml", "GO-2020-0001.yaml", "GO-2026-0001.yaml"]:
        (d / name).write_text("id: x\n", encoding="utf-8")
    got = [p.name for p in iter_report_paths(tmp_path)]
    assert got == ["GO-2020-0001.yaml", "GO-2026-0001.yaml", "GO-2026-0002.yaml"]
