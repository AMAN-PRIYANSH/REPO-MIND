"""FixEvidence extraction against small local git repositories (no network, CP3 deliverable 3)."""

import shutil
import subprocess

import pytest

from vulntrace.dataset.fix_evidence import build_fix_evidence
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


def _fc(sha):
    return {"host": "example.com", "owner": "o", "repo": "r", "sha": sha}


def test_modified_function_is_a_both_side_candidate(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc Vuln(s string) string {\n\treturn s\n}\n", encoding="utf-8")
    _commit(src, "init")
    (src / "lib.go").write_text(
        "package lib\n\nfunc Vuln(s string) string {\n\treturn sanitize(s)\n}\n\nfunc sanitize(s string) string { return s }\n",
        encoding="utf-8",
    )
    fix = _commit(src, "fix")

    ev = build_fix_evidence("CASE-1", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "AVAILABLE"
    assert ev["commits"] == [{"sha": fix, "parent_sha": ev["commits"][0]["parent_sha"]}]
    by_symbol = {c["symbol"]: c for c in ev["candidates"]}
    assert by_symbol["Vuln"]["side"] == "BOTH"
    assert by_symbol["sanitize"]["side"] == "NEW"
    assert ev["unfetchable_commits"] == []


def test_test_file_changes_are_counted_but_not_candidates(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    (src / "lib_test.go").write_text("package lib\n\nfunc TestF(t *testing.T) {}\n", encoding="utf-8")
    _commit(src, "init")
    (src / "lib_test.go").write_text("package lib\n\nfunc TestF(t *testing.T) { _ = F() }\n", encoding="utf-8")
    fix = _commit(src, "touch test only")

    ev = build_fix_evidence("CASE-2", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "EMPTY"
    assert ev["candidates"] == []
    assert ev["test_files_changed"] == 1


def test_vendor_changes_excluded_entirely(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    (src / "vendor" / "x").mkdir(parents=True)
    (src / "vendor" / "x" / "x.go").write_text("package x\n\nfunc G() {}\n", encoding="utf-8")
    _commit(src, "init")
    (src / "vendor" / "x" / "x.go").write_text("package x\n\nfunc G() { _ = 1 }\n", encoding="utf-8")
    fix = _commit(src, "touch vendor only")

    ev = build_fix_evidence("CASE-3", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "EMPTY"
    assert ev["non_go_files_changed"] == []  # vendor Go files are not "non-Go" either


def test_non_go_file_changes_are_counted(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    (src / "README.md").write_text("old\n", encoding="utf-8")
    _commit(src, "init")
    (src / "README.md").write_text("new\n", encoding="utf-8")
    fix = _commit(src, "docs only")

    ev = build_fix_evidence("CASE-4", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "EMPTY"
    assert ev["non_go_files_changed"] == ["README.md"]


def test_unfetchable_commit_gives_unavailable_and_is_recorded(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")

    ev = build_fix_evidence("CASE-5", [_fc("f" * 40)], binary=helper, cache_root=tmp_path / "cache",
                            remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "UNAVAILABLE"
    assert ev["commits"] == []
    assert len(ev["unfetchable_commits"]) == 1
    assert ev["unfetchable_commits"][0]["sha"] == "f" * 40


def test_multiple_fix_commits_are_merged_with_globally_unique_ids(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 1 }\n", encoding="utf-8")
    (src / "b.go").write_text("package lib\n\nfunc B() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    (src / "a.go").write_text("package lib\n\nfunc A() int { return 2 }\n", encoding="utf-8")
    fix1 = _commit(src, "fix a")
    (src / "b.go").write_text("package lib\n\nfunc B() int { return 2 }\n", encoding="utf-8")
    fix2 = _commit(src, "fix b")

    ev = build_fix_evidence("CASE-6", [_fc(fix1), _fc(fix2)], binary=helper, cache_root=tmp_path / "cache",
                            remote_url=str(src))
    validate("fix_evidence", ev)
    assert ev["status"] == "AVAILABLE"
    assert {c["sha"] for c in ev["commits"]} == {fix1, fix2}
    assert [c["candidate_id"] for c in ev["candidates"]] == ["c1", "c2"]
    assert [h["hunk_id"] for h in ev["hunks"]] == ["h1", "h2"]
    assert {c["symbol"] for c in ev["candidates"]} == {"A", "B"}


def test_deleted_function_is_old_side(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc A() int { return 1 }\n\nfunc B() int { return 2 }\n",
                                encoding="utf-8")
    _commit(src, "init")
    (src / "lib.go").write_text("package lib\n\nfunc A() int { return 1 }\n", encoding="utf-8")
    fix = _commit(src, "remove B")

    ev = build_fix_evidence("CASE-7", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    validate("fix_evidence", ev)
    by_symbol = {c["symbol"]: c for c in ev["candidates"]}
    assert by_symbol["B"]["side"] == "OLD"
    assert by_symbol["B"]["new_range"] is None


def test_estimated_tokens_is_hunk_text_length_over_four(tmp_path, helper):
    src = _init_repo(tmp_path)
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 1 }\n", encoding="utf-8")
    _commit(src, "init")
    (src / "lib.go").write_text("package lib\n\nfunc F() int { return 2 }\n", encoding="utf-8")
    fix = _commit(src, "fix")

    ev = build_fix_evidence("CASE-8", [_fc(fix)], binary=helper, cache_root=tmp_path / "cache", remote_url=str(src))
    assert ev["estimated_tokens"] == sum(len(h["text"]) for h in ev["hunks"]) // 4
