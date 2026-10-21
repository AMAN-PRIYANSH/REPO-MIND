"""D1 re-materialisation bookkeeping with an injected evidence builder (no network, no Go)."""

from vulntrace.dataset import materialize


def _case(case_id, sha):
    return {"id": case_id, "fix_commits": [{"host": "github.com", "owner": "o", "repo": "r", "sha": sha}]}


def test_materialize_d1_builds_once_skips_on_resume_and_lists_differences(tmp_path):
    calls = []

    def build(case):
        calls.append(case["id"])
        return {"case_id": case["id"], "status": "AVAILABLE", "candidates": [{"symbol": "F"}]}

    cases = {"A": _case("A", "1" * 40), "B": _case("B", "1" * 40)}
    case_list = {"status_counts": {"AVAILABLE": 2}, "cases": [
        {"id": "B", "status": "EMPTY", "candidate_count": 0},
        {"id": "A", "status": "AVAILABLE", "candidate_count": 1}]}
    s = materialize.materialize_d1(case_list, cases, None, data_dir=tmp_path, build_evidence=build,
                                   sleep=lambda _: None)
    assert calls == ["A", "B"]  # id order, never the case list's order
    assert s["action_counts"] == {"built": 2}
    assert s["differences"] == [{"id": "B", "differences": ["status EMPTY -> AVAILABLE",
                                                            "candidate_count 0 -> 1"]}]
    assert {r["cluster_key"] for r in s["cases"]} == {"o/r@" + "1" * 40}
    s2 = materialize.materialize_d1(case_list, cases, None, data_dir=tmp_path, build_evidence=build,
                                    sleep=lambda _: None)
    assert calls == ["A", "B"] and s2["action_counts"] == {"skipped": 2}
