"""Bounded git fetch against small local repositories (no network - CP3 deliverable 8)."""

import shutil
import subprocess

import pytest

from vulntrace.dataset.git_fetch import (
    GitFetchError,
    changed_files,
    deepen,
    fetch_commit,
    fetch_ref,
    is_shallow_boundary,
    file_content_at,
    object_exists,
    parent_sha,
    resolve_tag,
    run_git,
    unified_diff,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="SKIPPED: git not found on PATH")


def _git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"git {args} failed: {p.stderr}"
    return p.stdout


def make_source_repo(tmp_path):
    """A small local repository with two commits: a parent and a fix, each touching a Go
    file (and the fix also touching a test file and a vendored file)."""
    src = tmp_path / "source"
    src.mkdir()
    _git(["init", "-q", "-b", "main"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "t"], src)
    (src / "lib.go").write_text("package lib\n\nfunc Vuln(s string) string {\n\treturn s\n}\n", encoding="utf-8")
    (src / "lib_test.go").write_text("package lib\n\nfunc TestVuln(t *testing.T) {}\n", encoding="utf-8")
    (src / "vendor" / "x").mkdir(parents=True)
    (src / "vendor" / "x" / "x.go").write_text("package x\n\nfunc F() {}\n", encoding="utf-8")
    _git(["add", "-A"], src)
    _git(["commit", "-q", "-m", "parent"], src)
    parent = _git(["rev-parse", "HEAD"], src).strip()
    (src / "lib.go").write_text(
        "package lib\n\nfunc Vuln(s string) string {\n\treturn sanitize(s)\n}\n\nfunc sanitize(s string) string { return s }\n",
        encoding="utf-8",
    )
    (src / "lib_test.go").write_text("package lib\n\nfunc TestVuln(t *testing.T) { _ = Vuln(\"x\") }\n", encoding="utf-8")
    (src / "vendor" / "x" / "x.go").write_text("package x\n\nfunc F() { _ = 1 }\n", encoding="utf-8")
    (src / "README.md").write_text("docs\n", encoding="utf-8")
    _git(["add", "-A"], src)
    _git(["commit", "-q", "-m", "fix: sanitize input"], src)
    fix = _git(["rev-parse", "HEAD"], src).strip()
    _git(["tag", "v1.0.0", parent], src)
    _git(["tag", "v1.0.1", fix], src)
    return src, parent, fix


def test_fetch_commit_then_object_exists(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    cache_root = tmp_path / "cache"
    repo_dir = fetch_commit("example.com", "o", "r", fix, cache_root=cache_root, remote_url=str(src))
    assert object_exists(repo_dir, fix, subprocess.run)
    assert object_exists(repo_dir, parent, subprocess.run)  # depth=2 brought the parent too


def test_fetch_commit_is_idempotent_and_skips_refetch(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    cache_root = tmp_path / "cache"
    calls = []

    def counting_runner(args, **kw):
        calls.append(args)
        return subprocess.run(args, **kw)

    fetch_commit("example.com", "o", "r", fix, cache_root=cache_root, remote_url=str(src), runner=counting_runner)
    n_after_first = sum(1 for c in calls if c[:2] == ["git", "fetch"])
    fetch_commit("example.com", "o", "r", fix, cache_root=cache_root, remote_url=str(src), runner=counting_runner)
    n_after_second = sum(1 for c in calls if c[:2] == ["git", "fetch"])
    assert n_after_first == 1 and n_after_second == 1  # already present: no second network call


def test_fetch_commit_raises_on_unknown_sha(tmp_path):
    src, _, _ = make_source_repo(tmp_path)
    with pytest.raises(GitFetchError) as exc:
        fetch_commit("example.com", "o", "r", "f" * 40, cache_root=tmp_path / "cache", remote_url=str(src))
    assert exc.value.code == "FETCH_FAILED"


def test_fetch_commit_raises_on_unreachable_remote(tmp_path):
    with pytest.raises(GitFetchError) as exc:
        fetch_commit("example.com", "o", "r", "a" * 40, cache_root=tmp_path / "cache",
                     remote_url=str(tmp_path / "does-not-exist"))
    assert exc.value.code == "FETCH_FAILED"


def test_parent_sha(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir = fetch_commit("h", "o", "r", fix, cache_root=tmp_path / "cache", remote_url=str(src))
    assert parent_sha(repo_dir, fix, subprocess.run) == parent
    assert parent_sha(repo_dir, parent, subprocess.run) is None  # root commit


def test_file_content_at_added_and_missing(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir = fetch_commit("h", "o", "r", fix, cache_root=tmp_path / "cache", remote_url=str(src))
    assert "sanitize(s)" in file_content_at(repo_dir, fix, "lib.go", subprocess.run)
    assert file_content_at(repo_dir, fix, "nope.go", subprocess.run) is None


def test_changed_files_lists_status_and_path(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir = fetch_commit("h", "o", "r", fix, cache_root=tmp_path / "cache", remote_url=str(src))
    statuses = {path: status for status, path in changed_files(repo_dir, parent, fix, subprocess.run)}
    assert set(statuses) == {"lib.go", "lib_test.go", "vendor/x/x.go", "README.md"}
    assert statuses["lib.go"] == "M"
    assert statuses["README.md"] == "A"


def test_unified_diff_contains_hunk_header_and_changed_lines(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir = fetch_commit("h", "o", "r", fix, cache_root=tmp_path / "cache", remote_url=str(src))
    diff = unified_diff(repo_dir, parent, fix, "lib.go", subprocess.run)
    assert "@@" in diff and "+func sanitize" in diff


def test_fetch_ref_resolves_a_tag(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir, sha = fetch_ref("h", "o", "r", "v1.0.1", cache_root=tmp_path / "cache", remote_url=str(src))
    assert sha == fix


def test_fetch_ref_returns_none_for_a_missing_tag(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir, sha = fetch_ref("h", "o", "r", "v9.9.9", cache_root=tmp_path / "cache", remote_url=str(src))
    assert sha is None


def test_fetch_ref_result_is_usable_without_a_persistent_local_tag(tmp_path):
    """`fetch_ref` resolves the tag to a SHA via FETCH_HEAD; it does not need to leave behind
    a local tag ref named `v1.0.0` (git fetch of a bare ref does not create one), and the
    returned SHA is enough for every later git operation (diff, show, ...)."""
    src, parent, fix = make_source_repo(tmp_path)
    repo_dir, sha = fetch_ref("h", "o", "r", "v1.0.0", cache_root=tmp_path / "cache", remote_url=str(src))
    assert sha == parent
    assert object_exists(repo_dir, sha, subprocess.run)
    assert resolve_tag(repo_dir, sha, subprocess.run) == parent


def test_run_git_timeout_is_a_failed_result_not_an_exception(tmp_path):
    """Regression: a real D4 build crashed with an unhandled TimeoutExpired from a slow
    `git fetch --depth=501` on a large, active repository. run_git must turn a timeout into
    an ordinary failed CompletedProcess (returncode 124), exactly like every other git
    failure every caller here already handles - never propagate the exception and take
    down a whole dataset build over one slow case."""

    def slow_runner(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 1))

    p = run_git(slow_runner, ["git", "fetch"], tmp_path, timeout=1)
    assert p.returncode == 124
    assert "timed out" in p.stderr


def test_deepen_does_not_raise_on_timeout_but_fails_gracefully(tmp_path):
    src, parent, fix = make_source_repo(tmp_path)
    cache_root = tmp_path / "cache"
    fetch_commit("h", "o", "r", fix, cache_root=cache_root, remote_url=str(src))

    def slow_runner(args, **kwargs):
        if args[:2] == ["git", "fetch"]:
            raise subprocess.TimeoutExpired(args, kwargs.get("timeout", 1))
        return subprocess.run(args, **kwargs)

    with pytest.raises(GitFetchError) as exc:
        deepen("h", "o", "r", fix, 10, cache_root=cache_root, runner=slow_runner, remote_url=str(src))
    assert exc.value.code == "FETCH_FAILED"


def make_chain_repo(tmp_path, n=3):
    """A linear history of `n` commits; returns (source dir, [sha oldest .. newest])."""
    src = tmp_path / "chain"
    src.mkdir()
    _git(["init", "-q", "-b", "main"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "t"], src)
    shas = []
    for i in range(n):
        (src / "f.go").write_text(f"package f\n\nfunc F() int {{ return {i} }}\n", encoding="utf-8")
        _git(["add", "-A"], src)
        _git(["commit", "-q", "-m", f"c{i}"], src)
        shas.append(_git(["rev-parse", "HEAD"], src).strip())
    return src, shas


def test_fetch_commit_deepens_a_commit_that_is_only_a_shallow_boundary(tmp_path):
    """CP5b task 0a. Fetching a child at depth 2 leaves its parent present but parentless (it is the
    shallow boundary). Asking for that parent next used to return early, and parent_sha() was None
    ("NO_PARENT" for a commit that has one), so a case's result depended on which cases ran before it."""
    src, (root, mid, tip) = make_chain_repo(tmp_path)
    cache = tmp_path / "cache"
    repo_dir = fetch_commit("h", "o", "r", tip, cache_root=cache, remote_url=str(src))
    assert object_exists(repo_dir, mid, subprocess.run)
    assert parent_sha(repo_dir, mid, subprocess.run) is None  # the premise: mid is the boundary
    assert is_shallow_boundary(repo_dir, mid)
    repo_dir = fetch_commit("h", "o", "r", mid, cache_root=cache, remote_url=str(src))
    assert parent_sha(repo_dir, mid, subprocess.run) == root
    assert not is_shallow_boundary(repo_dir, mid)


def test_fetch_commit_result_does_not_depend_on_order(tmp_path):
    src, (root, mid, tip) = make_chain_repo(tmp_path)
    parents = []
    for order in ((tip, mid), (mid, tip)):
        cache = tmp_path / f"cache-{order[0][:6]}"
        got = {}
        for sha in order:
            repo_dir = fetch_commit("h", "o", "r", sha, cache_root=cache, remote_url=str(src))
            got[sha] = parent_sha(repo_dir, sha, subprocess.run)
        parents.append(got)
    assert parents[0] == parents[1] == {tip: mid, mid: root}


def test_fetch_commit_does_not_refetch_a_complete_commit(tmp_path):
    src, (root, mid, tip) = make_chain_repo(tmp_path)
    calls = []

    def counting(args, **kw):
        calls.append(args)
        return subprocess.run(args, **kw)

    cache = tmp_path / "cache"
    fetch_commit("h", "o", "r", tip, cache_root=cache, remote_url=str(src), runner=counting)
    fetch_commit("h", "o", "r", tip, cache_root=cache, remote_url=str(src), runner=counting)
    assert sum(1 for c in calls if c[:2] == ["git", "fetch"]) == 1
