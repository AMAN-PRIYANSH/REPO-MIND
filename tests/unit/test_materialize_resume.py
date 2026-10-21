"""CP4 fix round: FIX-2 (resume/reuse rule), FIX-3 (git errors are recorded and summarised),
FIX-1 (diagnose prints git stderr). No network, no Go, no real git."""

import subprocess

from vulntrace.dataset import materialize
from vulntrace.dataset.release_range import build_release_range


def _case(case_id, fixed_in="1.0.1"):
    return {"id": case_id, "aliases": [], "summary": "s", "details": "", "created": "2026-01-01",
            "fix_commits": [{"host": "example.com", "owner": "o", "repo": "r", "sha": "a" * 40}],
            "modules": [{"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": fixed_in,
                         "packages": [{"package": "github.com/o/r", "core_symbols": ["A"], "derived_symbols": []}]}]}


def _rr(case_id, status, git_error=None):
    rr = {"schema_version": "1.0", "case_id": case_id, "module": "github.com/o/r",
          "from": {"version": "1.0.0", "ref": None, "commit": None}, "to": {"version": "1.0.1", "ref": None, "commit": None},
          "candidates": [], "commits": [], "non_go_files_changed": [], "test_files_changed": 0, "status": status}
    if git_error:
        rr["git_error"] = git_error
    return rr


EXPECTED_EMPTY = {"status_counts": {"EMPTY": 1}, "cases": [{"id": "A", "status": "EMPTY", "candidate_count": 0,
                                                            "commit_count": 0}]}


def test_failed_result_is_rebuilt_and_a_good_one_is_skipped(tmp_path):
    results = iter([_rr("A", "TAG_NOT_FOUND", "fatal: boom"), _rr("A", "EMPTY")])
    calls = []

    def build(case, module):
        calls.append(case["id"])
        return next(results)

    kw = dict(data_dir=tmp_path, build_range=build, sleep=lambda _: None)
    first = materialize.materialize_d4(EXPECTED_EMPTY, {"A": _case("A")}, None, **kw)
    assert [r["action"] for r in first["cases"]] == ["built"] and first["differences"]
    # Files exist and look complete, but the stored status is wrong: it must be rebuilt, not skipped.
    assert not materialize.is_complete("A", tmp_path, EXPECTED_EMPTY["cases"][0])
    assert materialize.is_complete("A", tmp_path)  # the old rule (files only) would have said "done"
    second = materialize.materialize_d4(EXPECTED_EMPTY, {"A": _case("A")}, None, **kw)
    assert [r["action"] for r in second["cases"]] == ["built"] and not second["differences"]
    third = materialize.materialize_d4(EXPECTED_EMPTY, {"A": _case("A")}, None, **kw)
    assert [r["action"] for r in third["cases"]] == ["skipped"]
    assert calls == ["A", "A"]


def test_a_failed_result_is_never_copied_to_a_case_with_the_same_range(tmp_path):
    case_list = {"cases": [{"id": i, "status": "EMPTY", "candidate_count": 0, "commit_count": 0} for i in ("A", "B")]}
    outcomes = {"A": "TAG_NOT_FOUND", "B": "EMPTY"}
    calls = []

    def build(case, module):
        calls.append(case["id"])
        return _rr(case["id"], outcomes[case["id"]])

    s = materialize.materialize_d4(case_list, {"A": _case("A"), "B": _case("B")}, None, data_dir=tmp_path,
                                   build_range=build, sleep=lambda _: None)
    assert calls == ["A", "B"]  # B shares A's range but A failed, so B is computed, not copied
    assert [r["action"] for r in s["cases"]] == ["built", "built"]
    assert [d["id"] for d in s["differences"]] == ["A"]


def test_a_good_result_is_still_reused_for_an_identical_range(tmp_path):
    case_list = {"cases": [{"id": i, "status": "EMPTY", "candidate_count": 0, "commit_count": 0} for i in ("A", "B")]}
    calls = []

    def build(case, module):
        calls.append(case["id"])
        return _rr(case["id"], "EMPTY")

    s = materialize.materialize_d4(case_list, {"A": _case("A"), "B": _case("B")}, None, data_dir=tmp_path,
                                   build_range=build, sleep=lambda _: None)
    assert calls == ["A"] and [r["action"] for r in s["cases"]] == ["built", "reused"]


def test_d1_failed_result_is_rebuilt(tmp_path):
    outcomes = iter(["TAG_NOT_FOUND", "AVAILABLE"])

    def build(case):
        return {"case_id": case["id"], "status": next(outcomes), "candidates": []}

    case = {"id": "A", "fix_commits": [{"host": "h", "owner": "o", "repo": "r", "sha": "1" * 40}]}
    case_list = {"cases": [{"id": "A", "status": "AVAILABLE", "candidate_count": 0}]}
    kw = dict(data_dir=tmp_path, build_evidence=build, sleep=lambda _: None)
    assert materialize.materialize_d1(case_list, {"A": case}, None, **kw)["action_counts"] == {"built": 1}
    assert materialize.materialize_d1(case_list, {"A": case}, None, **kw)["action_counts"] == {"built": 1}
    assert materialize.materialize_d1(case_list, {"A": case}, None, **kw)["action_counts"] == {"skipped": 1}


class _FailingGit:
    """A runner whose `git fetch` fails with a real-looking message and everything else succeeds."""

    def __init__(self, stderr):
        self.stderr, self.calls = stderr, []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if args[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(args, 128, stdout="", stderr=self.stderr)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def test_git_error_line_is_recorded_in_the_evidence_not_lost_as_tag_not_found(tmp_path):
    runner = _FailingGit("fatal: detected dubious ownership in repository at '/x'\nhint: more text")
    rr = build_release_range("A", "github.com/o/r", "1.0.0", "1.0.1", "example.com", "o", "r",
                             cache_root=tmp_path / "cache", runner=runner)
    assert rr["status"] == "TAG_NOT_FOUND"
    assert rr["git_error"] == "fatal: detected dubious ownership in repository at '/x'"


def test_diagnose_prints_every_failed_git_call_with_its_stderr(tmp_path):
    lines = []
    runner = _FailingGit("fatal: couldn't find remote ref refs/tags/v1.0.0")
    res = materialize.diagnose_case(_case("A"), None, cache_root=tmp_path / "cache", runner=runner,
                                    print_line=lines.append, expected={"id": "A", "status": "AVAILABLE",
                                                                       "candidate_count": 1, "commit_count": 1})
    text = "\n".join(lines)
    assert res["status"] == "TAG_NOT_FOUND" and res["git_error"].startswith("fatal: couldn't find remote ref")
    assert "-> exit 128" in text and "stderr: fatal: couldn't find remote ref refs/tags/v1.0.0" in text
    assert "status AVAILABLE -> TAG_NOT_FOUND" in text


def test_top_git_errors_group_by_message_and_name_the_three_most_common():
    rows = ([{"id": f"a{i}", "git_error": f"fatal: couldn't find remote ref v1.{i}.0"} for i in range(3)]
            + [{"id": "b", "git_error": "fatal: unable to access 'https://x/y/': Could not resolve host"}] * 2
            + [{"id": "c", "git_error": "fatal: other"}, {"id": "d", "git_error": "fatal: another"},
               {"id": "e", "git_error": None}])
    top = materialize.top_git_errors(rows)
    assert [(t["message"], t["count"]) for t in top][:2] == [
        ("fatal: couldn't find remote ref <ref>", 3), ("fatal: unable to access '<x>': Could not resolve host", 2)]
    assert len(top) == 3 and top[0]["example_case"] == "a0"
