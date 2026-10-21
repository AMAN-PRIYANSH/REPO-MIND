"""CP4 fix round FIX-5/FIX-6: empty or wrong evidence is refused before anything is written."""

import json

import pytest

from tests.integration.test_retrieval_harness import tiny_d4  # noqa: F401  (fixture)
from vulntrace.__main__ import main
from vulntrace.eval import evidence_gate as eg


def _list(statuses):
    return {"cases": [{"id": f"C{i}", "status": s} for i, s in enumerate(statuses)]}


def test_valid_evidence_passes_and_up_to_three_differences_are_tolerated():
    cl = _list(["AVAILABLE"] * 6)
    assert eg.check_evidence(cl, {f"C{i}": "AVAILABLE" for i in range(6)}, 10) == []
    three = {f"C{i}": ("TAG_NOT_FOUND" if i < 3 else "AVAILABLE") for i in range(6)}
    assert eg.check_evidence(cl, three, 10) == []


def test_zero_chunks_and_too_many_differences_are_refused():
    cl = _list(["AVAILABLE"] * 6)
    ok = {f"C{i}": "AVAILABLE" for i in range(6)}
    assert any("0 chunks" in p for p in eg.check_evidence(cl, ok, 0))
    four = {f"C{i}": ("EMPTY" if i < 4 else "AVAILABLE") for i in range(6)}
    problems = eg.check_evidence(cl, four, 10)
    assert len(problems) == 1 and "4 of 6 cases" in problems[0]
    with pytest.raises(eg.EvidenceGateError, match="refusing to run"):
        eg.require_valid_evidence(cl, four, 10)
    # a case with no evidence at all counts as a difference
    assert eg.check_evidence(cl, {}, 10, max_differences=3)


def test_the_first_colab_failure_pattern_is_refused():
    cl = _list(["AVAILABLE"] * 120)
    bad = {f"C{i}": "TAG_NOT_FOUND" for i in range(120)}
    problems = eg.check_evidence(cl, bad, 0)
    assert len(problems) == 2


def test_evidence_statuses_reads_a_data_dir_and_reports_missing(tmp_path):
    (tmp_path / "release_range").mkdir()
    (tmp_path / "release_range" / "C0.json").write_text(json.dumps({"status": "AVAILABLE", "candidates": [1, 2]}))
    (tmp_path / "release_range" / "C1.json").write_text("{not json")
    statuses, n = eg.evidence_statuses(_list(["AVAILABLE"] * 3), tmp_path)
    assert statuses == {"C0": "AVAILABLE", "C1": "MISSING", "C2": "MISSING"} and n == 2


def _empty_the_evidence(data):
    for p in (data / "release_range").glob("*.json"):
        rr = json.loads(p.read_text())
        rr.update(candidates=[], commits=[], status="TAG_NOT_FOUND")
        p.write_text(json.dumps(rr))


def test_eval_retrieval_and_index_build_refuse_empty_evidence_and_write_nothing(tiny_d4, tmp_path, monkeypatch):  # noqa: F811
    case_list, vcs, data = tiny_d4
    _empty_the_evidence(data)
    cl = tmp_path / "D4_cases.json"
    cl.write_text(json.dumps(case_list))
    from vulntrace.dataset import datasets

    monkeypatch.setattr(datasets, "load_all_cases", lambda cache=None: (list(vcs.values()), 0))
    out, emb = tmp_path / "res", tmp_path / "emb"
    common = ["--cases", str(cl), "--data-dir", str(data), "--embedding-cache", str(emb)]
    assert main(["eval", "retrieval", "--config", "bm25", "--variant", "code_only", *common, "--out", str(out)]) == 2
    assert not out.exists()
    assert main(["index", "build", "--set", "d4", "--embedder", "fake", "--variant", "code_only", *common]) == 2
    assert not emb.exists()


def test_eval_retrieval_still_runs_on_good_evidence(tiny_d4, tmp_path, monkeypatch):  # noqa: F811
    case_list, vcs, data = tiny_d4
    cl = tmp_path / "D4_cases.json"
    cl.write_text(json.dumps(case_list))
    from vulntrace.dataset import datasets

    monkeypatch.setattr(datasets, "load_all_cases", lambda cache=None: (list(vcs.values()), 0))
    assert main(["eval", "retrieval", "--config", "bm25", "--variant", "code_only", "--cases", str(cl),
                 "--data-dir", str(data), "--out", str(tmp_path / "res")]) == 0
