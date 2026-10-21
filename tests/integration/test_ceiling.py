"""Ceiling investigation (CP3 deliverable 7) against small local git repositories (no network)."""

import shutil
import subprocess

import pytest

from vulntrace.dataset.ceiling import (
    REASON_EXISTS_UNCHANGED,
    REASON_MATCHING_PROBLEM,
    REASON_NOT_FOUND_EITHER_VERSION,
    classify_missing_symbol,
    investigate_case,
    missing_core_symbols,
    run_investigation,
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="SKIPPED: git not found on PATH")


def _git(args, cwd):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, f"git {args} failed: {p.stderr}"
    return p.stdout


def _init_repo(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    _git(["init", "-q", "-b", "main"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "t"], src)
    return src


def _commit(src, message):
    _git(["add", "-A"], src)
    _git(["commit", "-q", "-m", message], src)
    return _git(["rev-parse", "HEAD"], src).strip()


def test_missing_core_symbols():
    case = {"modules": [{"packages": [{"core_symbols": ["A", "B"], "derived_symbols": []}]}]}
    rr = {"candidates": [{"symbol": "A"}]}
    assert missing_core_symbols(case, rr) == {"B"}


def test_classify_exists_unchanged(tmp_path):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package a\n\nfunc Caller() {}\n\nfunc Unchanged() int { return 1 }\n",
                              encoding="utf-8")
    sha1 = _commit(src, "init")
    (src / "a.go").write_text(
        "package a\n\nfunc Caller() { Unchanged() }\n\nfunc Unchanged() int { return 1 }\n", encoding="utf-8")
    sha2 = _commit(src, "touch caller only")
    assert classify_missing_symbol(src, sha1, sha2, "Unchanged") == REASON_EXISTS_UNCHANGED


def test_classify_not_found_either_version(tmp_path):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package a\n\nfunc A() {}\n", encoding="utf-8")
    sha1 = _commit(src, "init")
    (src / "a.go").write_text("package a\n\nfunc A() { _ = 1 }\n", encoding="utf-8")
    sha2 = _commit(src, "touch A")
    assert classify_missing_symbol(src, sha1, sha2, "NeverExisted") == REASON_NOT_FOUND_EITHER_VERSION


def test_classify_matching_problem_when_present_at_only_one_end(tmp_path):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package a\n\nfunc OldOnly() {}\n", encoding="utf-8")
    sha1 = _commit(src, "init")
    (src / "a.go").write_text("package a\n\nfunc NewOnly() {}\n", encoding="utf-8")
    sha2 = _commit(src, "swap")
    # Present only at sha1 (removed): a real change the pipeline should have caught as a
    # candidate; a symbol missing from candidates despite this is a real matching problem.
    assert classify_missing_symbol(src, sha1, sha2, "OldOnly") == REASON_MATCHING_PROBLEM
    assert classify_missing_symbol(src, sha1, sha2, "NewOnly") == REASON_MATCHING_PROBLEM


def test_investigate_case_classifies_every_missing_symbol(tmp_path):
    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package a\n\nfunc Caller() {}\n\nfunc Unchanged() int { return 1 }\n",
                              encoding="utf-8")
    sha1 = _commit(src, "init")
    (src / "a.go").write_text(
        "package a\n\nfunc Caller() { Unchanged() }\n\nfunc Unchanged() int { return 1 }\n", encoding="utf-8")
    sha2 = _commit(src, "touch caller only")
    case = {"modules": [{"packages": [{"core_symbols": ["Unchanged", "Ghost"], "derived_symbols": []}]}]}
    rr = {"status": "AVAILABLE", "from": {"commit": sha1}, "to": {"commit": sha2}, "candidates": []}
    result = investigate_case(case, rr, src)
    assert result == {"Unchanged": REASON_EXISTS_UNCHANGED, "Ghost": REASON_NOT_FOUND_EITHER_VERSION}


def test_investigate_case_with_no_missing_symbols_returns_empty():
    case = {"modules": [{"packages": [{"core_symbols": ["A"], "derived_symbols": []}]}]}
    rr = {"status": "AVAILABLE", "from": {"commit": "x"}, "to": {"commit": "y"}, "candidates": [{"symbol": "A"}]}
    assert investigate_case(case, rr, None) == {}


def test_run_investigation_aggregates_across_cases(tmp_path, monkeypatch):
    import vulntrace.dataset.git_fetch as git_fetch

    src = _init_repo(tmp_path)
    (src / "a.go").write_text("package a\n\nfunc Caller() {}\n\nfunc Unchanged() int { return 1 }\n",
                              encoding="utf-8")
    sha1 = _commit(src, "init")
    (src / "a.go").write_text(
        "package a\n\nfunc Caller() { Unchanged() }\n\nfunc Unchanged() int { return 1 }\n", encoding="utf-8")
    sha2 = _commit(src, "touch caller only")

    cache_root = tmp_path / "cache"
    monkeypatch.setattr(git_fetch, "repo_cache_dir", lambda host, owner, repo, cache_root=None: src)

    case = {"id": "GO-TEST-0001", "fix_commits": [{"host": "h", "owner": "o", "repo": "r", "sha": "x" * 40}],
           "modules": [{"packages": [{"core_symbols": ["Unchanged", "Ghost"], "derived_symbols": []}]}]}
    rr = {"status": "AVAILABLE", "from": {"commit": sha1}, "to": {"commit": sha2}, "candidates": []}

    result = run_investigation({"GO-TEST-0001": case}, {"GO-TEST-0001": rr}, cache_root)
    assert result["cases_checked"] == 1
    assert result["cases_with_missing_core_symbol"] == 1
    assert result["missing_symbol_counts_by_reason"][REASON_EXISTS_UNCHANGED] == 1
    assert result["missing_symbol_counts_by_reason"][REASON_NOT_FOUND_EITHER_VERSION] == 1
    assert len(result["examples"]) == 2
    assert {e["symbol"] for e in result["examples"]} == {"Unchanged", "Ghost"}
