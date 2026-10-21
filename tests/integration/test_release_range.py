"""ReleaseRange extraction against small local git repositories (no network, CP3 deliverable 4)."""

import shutil
import subprocess

import pytest

from vulntrace.dataset.release_range import (
    STATUS_AVAILABLE,
    STATUS_EMPTY,
    STATUS_PSEUDO_VERSION_UNRESOLVED,
    STATUS_TAG_NOT_FOUND,
    STATUS_TRUNCATED,
    build_release_range,
)
from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.schemas import validate

pytestmark = pytest.mark.skipif(shutil.which("go") is None or shutil.which("git") is None,
                                reason="SKIPPED: Go toolchain or git not found on PATH")


@pytest.fixture(scope="module")
def helper():
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


def _git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"git {args} failed: {p.stderr}"
    return p.stdout


def _init_repo(tmp_path, name="source"):
    src = tmp_path / name
    src.mkdir()
    _git(["init", "-q", "-b", "main"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "t"], src)
    return src


def _commit(src, message):
    _git(["add", "-A"], src)
    _git(["commit", "-q", "-m", message], src)
    return _git(["rev-parse", "HEAD"], src).strip()


def make_tagged_repo(tmp_path):
    """v1.0.0 (vulnerable) -> three intermediate commits -> v1.0.1 (fixed). A and B live in
    separate files so each commit's file-level touches_candidates attribution is precise."""
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 1 }\n", encoding="utf-8")
    (src / "b.go").write_text("package lib\n\nfunc B() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.0"], src)
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 2 }\n", encoding="utf-8")
    _commit(src, "touch A")
    (src / "README.md").write_text("docs\n", encoding="utf-8")
    _commit(src, "docs")
    (src / "b.go").write_text("package lib\n\nfunc B() int { return 3 }\n", encoding="utf-8")
    _commit(src, "touch B")
    _git(["tag", "v1.0.1"], src)
    return src


def test_available_range_with_candidates_and_commit_attribution(tmp_path, helper):
    src = make_tagged_repo(tmp_path)
    rr = build_release_range("CASE-1", "github.com/o/r", "1.0.0", "1.0.1", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_AVAILABLE
    assert rr["from"]["ref"] == "v1.0.0" and rr["to"]["ref"] == "v1.0.1"
    symbols = {c["symbol"]: c for c in rr["candidates"]}
    assert set(symbols) == {"A", "B"}
    assert all(c["side"] == "BOTH" for c in symbols.values())
    assert len(rr["commits"]) == 3  # "touch A", "docs", "touch B"
    by_subject = {c["subject"]: c for c in rr["commits"]}
    a_id = symbols["A"]["candidate_id"]
    b_id = symbols["B"]["candidate_id"]
    assert by_subject["touch A"]["touches_candidates"] == [a_id]
    assert by_subject["docs"]["touches_candidates"] == []
    assert by_subject["touch B"]["touches_candidates"] == [b_id]


def test_commit_body_is_captured_for_bid_baseline(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.0"], src)
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 2 }\n", encoding="utf-8")
    _git(["add", "-A"], src)
    _git(["commit", "-q", "-m", "fix audience bypass\n\nFixes CVE-2020-26160\nGHSA-w73w-5m7g-f7qc"], src)
    _git(["tag", "v1.0.1"], src)

    rr = build_release_range("CASE-BODY", "github.com/o/r", "1.0.0", "1.0.1", "example.com", "o", "r",
                             binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert len(rr["commits"]) == 1
    assert rr["commits"][0]["subject"] == "fix audience bypass"
    assert "CVE-2020-26160" in rr["commits"][0]["body"]
    assert "GHSA-w73w-5m7g-f7qc" in rr["commits"][0]["body"]


def test_submodule_tag_prefix(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "sub" / "lib.go").parent.mkdir(parents=True)
    (src / "sub" / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "sub/v1.0.0"], src)
    (src / "sub" / "lib.go").write_text("package lib\n\nfunc F() int { return 2 }\n", encoding="utf-8")
    _commit(src, "fix")
    _git(["tag", "sub/v1.0.1"], src)

    rr = build_release_range("CASE-2", "github.com/o/r/sub", "1.0.0", "1.0.1", "example.com", "o", "r",
                             binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_AVAILABLE
    assert rr["from"]["ref"] == "sub/v1.0.0"


def test_major_version_branch_convention_tag(tmp_path, helper):
    """module path has a /v3 suffix, but the tag is at the repo root (the common "branch"
    convention), not under a v3/ prefix - candidate_tags must try the root form first."""
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v3.0.0"], src)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 2 }\n", encoding="utf-8")
    _commit(src, "fix")
    _git(["tag", "v3.0.1"], src)

    rr = build_release_range("CASE-3", "github.com/o/r/v3", "3.0.0", "3.0.1", "example.com", "o", "r",
                             binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_AVAILABLE and rr["from"]["ref"] == "v3.0.0"


def test_pseudo_version_resolves_through_embedded_commit(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    old_sha = _commit(src, "init")
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 2 }\n", encoding="utf-8")
    _commit(src, "fix")
    _git(["tag", "v1.0.1"], src)
    pseudo = f"0.0.0-20200101000000-{old_sha[:12]}"

    rr = build_release_range("CASE-4", "github.com/o/r", pseudo, "1.0.1", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_AVAILABLE
    assert rr["from"]["commit"] == old_sha


def test_pseudo_version_with_unresolvable_commit_is_unresolved(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.1"], src)
    pseudo = "0.0.0-20200101000000-" + "f" * 12

    rr = build_release_range("CASE-5", "github.com/o/r", pseudo, "1.0.1", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_PSEUDO_VERSION_UNRESOLVED


def test_missing_tag_is_tag_not_found(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.0"], src)

    rr = build_release_range("CASE-6", "github.com/o/r", "1.0.0", "9.9.9", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_TAG_NOT_FOUND
    assert rr["candidates"] == []


def test_empty_range_with_no_go_changes(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    (src / "README.md").write_text("old\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.0"], src)
    (src / "README.md").write_text("new\n", encoding="utf-8")
    _commit(src, "docs only")
    _git(["tag", "v1.0.1"], src)

    rr = build_release_range("CASE-7", "github.com/o/r", "1.0.0", "1.0.1", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src))
    validate("release_range", rr)
    assert rr["status"] == STATUS_EMPTY
    assert rr["non_go_files_changed"] == ["README.md"]


def test_commit_cap_marks_the_range_truncated(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 0 }\n", encoding="utf-8")
    _commit(src, "init")
    _git(["tag", "v1.0.0"], src)
    for i in range(1, 6):
        (src / "lib.go").write_text(f"package lib\n\nfunc F() int {{ return {i} }}\n", encoding="utf-8")
        _commit(src, f"bump {i}")
    _git(["tag", "v1.0.1"], src)

    rr = build_release_range("CASE-8", "github.com/o/r", "1.0.0", "1.0.1", "example.com", "o", "r", binary=helper,
                             cache_root=tmp_path / "cache", remote_url=str(src), commit_cap=3)
    validate("release_range", rr)
    assert rr["status"] == STATUS_TRUNCATED
    assert len(rr["commits"]) == 3  # capped, not silently dropped to 0
    # The candidate (function F, changed) is still reported even though truncated: it comes
    # from a single two-tree diff, not from the history walk.
    assert len(rr["candidates"]) == 1 and rr["candidates"][0]["symbol"] == "F"
