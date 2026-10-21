"""D4 re-materialisation against a small local git repository (no network, CP4 task 0a)."""

import shutil

import pytest

from tests.integration.test_release_range import make_tagged_repo
from vulntrace.dataset import materialize
from vulntrace.dataset.release_range import build_release_range
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


def _case(case_id, vulnerable_at="1.0.0", fixed_in="1.0.1"):
    return {"id": case_id, "aliases": [], "summary": "s", "details": "", "created": "2026-01-01",
            "fix_commits": [{"host": "example.com", "owner": "o", "repo": "r", "sha": "a" * 40}],
            "modules": [{"module": "github.com/o/r", "vulnerable_at": vulnerable_at, "fixed_in": fixed_in,
                         "packages": [{"package": "github.com/o/r", "core_symbols": ["A"], "derived_symbols": []}]}]}


def test_materialize_builds_reuses_identical_ranges_resumes_and_reports_differences(tmp_path, helper):
    src = make_tagged_repo(tmp_path)
    cache = tmp_path / "cache"
    calls = []

    def build_range(case, module):
        calls.append(case["id"])
        fc = case["fix_commits"][0]
        return build_release_range(case["id"], module["module"], module["vulnerable_at"], module["fixed_in"],
                                   fc["host"], fc["owner"], fc["repo"], binary=helper, cache_root=cache,
                                   remote_url=str(src))

    cases = {"C-1": _case("C-1"), "C-2": _case("C-2"), "C-3": _case("C-3", fixed_in="9.9.9")}
    case_list = {"status_counts": {"AVAILABLE": 2, "TAG_NOT_FOUND": 1}, "cases": [
        {"id": "C-1", "status": "AVAILABLE", "candidate_count": 2, "commit_count": 3},
        {"id": "C-2", "status": "AVAILABLE", "candidate_count": 2, "commit_count": 3},
        # deliberately wrong expectation: must be reported, not hidden
        {"id": "C-3", "status": "AVAILABLE", "candidate_count": 2, "commit_count": 3},
    ]}
    data = tmp_path / "data"
    slept = []
    summary = materialize.materialize_d4(case_list, cases, helper, data_dir=data, cache_root=cache,
                                         build_range=build_range, sleep=slept.append)
    assert calls == ["C-1", "C-3"]  # C-2 shares C-1's range and is copied, not recomputed
    assert [r["action"] for r in summary["cases"]] == ["built", "reused", "built"]
    assert summary["status_counts"] == {"AVAILABLE": 2, "TAG_NOT_FOUND": 1}
    assert [d["id"] for d in summary["differences"]] == ["C-3"]
    assert "status AVAILABLE -> TAG_NOT_FOUND" in summary["differences"][0]["differences"]
    assert slept == [materialize.DEFAULT_DELAY_S]  # after C-1 only (C-3 is last; C-2 did not fetch)
    assert summary["cases"][0]["cluster_key"] == "github.com/o/r@1.0.0..1.0.1"

    rr2 = materialize._load(data / "release_range" / "C-2.json")
    validate("release_range", rr2)
    assert rr2["case_id"] == "C-2"
    code = materialize._load(data / "candidate_code" / "C-1.json")
    bodies = {c["file"]: c for c in code["candidates"].values()}
    # vulnerable-side (v1.0.0) bodies, not the fixed ones
    assert bodies["a.go"]["body"] == "func A() int { return 1 }"
    assert bodies["a.go"]["signature"] == "func A() int"
    assert bodies["a.go"]["package_name"] == "lib" and bodies["a.go"]["body_side"] == "OLD"

    calls.clear()
    again = materialize.materialize_d4(case_list, cases, helper, data_dir=data, cache_root=cache,
                                       build_range=build_range, sleep=slept.append)
    # FIX-2: C-3's stored result (TAG_NOT_FOUND) differs from the case list, so it is rebuilt.
    assert calls == ["C-3"]
    assert [r["action"] for r in again["cases"]] == ["skipped", "skipped", "built"]
    assert "couldn't find remote ref" in again["cases"][2]["git_error"]  # FIX-3: git's own message is kept


def test_doc_comment_and_signature_helpers():
    lines = ["package p", "", "// Foo does things.", "// Second line.", "func Foo(a int,", "\tb int) error {",
             "\treturn nil", "}"]
    assert materialize.doc_comment_above(lines, 5) == "// Foo does things.\n// Second line."
    assert materialize.doc_comment_above(lines, 3) == ""
    assert materialize.signature_of("\n".join(lines[4:])) == "func Foo(a int, b int) error"
