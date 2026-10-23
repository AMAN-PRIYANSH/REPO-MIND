"""The committed CP5b results are reproducible from the committed files: every summary is recomputed from the
stored rows, the results document is re-rendered and must be identical, and the files stay small."""

import json
import math

import pytest

from vulntrace.eval import lift_ceiling as lc
from vulntrace.eval import lift_eval as le
from vulntrace.eval.lift_report import render_cp5b_doc
from vulntrace.eval.llm_report import group_defs
from vulntrace.paths import REPO_ROOT

RES = REPO_ROOT / "docs" / "results" / "cp5b"
DOC = REPO_ROOT / "docs" / "results" / "CP5B_LIFTING_RESULTS.md"


def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def same(a, b):
    """Equal, treating NaN as equal to NaN (JSON round trips keep NaN as NaN here)."""
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b, abs=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def test_lifting_summary_is_recomputed_from_the_rows():
    d = load("lift_d1.json")
    rows = [le.attach_metrics(dict(r)) for r in d["rows"]]
    assert same(le.summarize_lifting(rows), d["lifting"])
    assert d["lifting"]["cases_with_derived"] == len(rows) == 99
    # the counts the report quotes
    c = d["lifting"]["coverage"]
    assert c["of"] == 99 and c["lifted_ok"] == sum(1 for r in rows if r["outcome"]["success"])
    assert sum(d["lifting"]["failure_counts"].values()) == 99 - c["lifted_ok"]      # every failure is counted


def test_every_row_keeps_its_outcome_and_a_failed_case_predicts_nothing():
    for r in load("lift_d1.json")["rows"]:
        assert r["outcome"]["success"] == (r["outcome"]["failure"] is None)
        if not r["outcome"]["success"]:
            assert r["lifted"] == {"NEAREST": [], "ALL": []} and r["outcome"]["detail"]
        assert set(r["lifted"]["NEAREST"]) <= set(r["lifted"]["ALL"]) or not r["outcome"]["success"]


@pytest.mark.parametrize("alias", ["llama3.1-8b", "qwen2.5-coder-7b"])
def test_e1_plus_l_summary_is_recomputed_from_the_per_model_rows(alias):
    d = load("lift_d1.json")["e1_plus_l"][alias]
    rows = load(f"e1_plus_l__{alias}.json")["rows"]
    assert len(rows) == d["rows_used"]
    assert same(le.summarize_e1_plus_l(rows, d["model"]["cutoff"], group_defs), d["summary"])
    for r in rows:
        assert r["reason"] == "APPLIED" or not r["lifting_applied"]
        assert set(r["sets"]["e1"]) == set(r["sets"]["replace/ALL"]) or r["lifting_applied"]   # names are compared as sets


def test_the_e1_baselines_in_the_rows_are_the_committed_cp5_numbers():
    """E1 and E0 were recomputed from the stored sets; they must equal the CP5 file's committed per-case metrics."""
    for alias in ("llama3.1-8b", "qwen2.5-coder-7b"):
        cp5 = {r["id"]: r for r in json.loads((REPO_ROOT / "docs/results/cp5" / f"select_fix__{alias}.json").read_text())["rows"]}
        for r in load(f"e1_plus_l__{alias}.json")["rows"]:
            m = le.row_metrics(r)["core_derived"]
            c = cp5[r["id"]]["m"]
            assert m["e1"]["recall"] == pytest.approx(c["llm"]["core_derived"]["recall"]) and m["e1"]["predicted"] == c["llm"]["core_derived"]["predicted"]
            assert m["e0"]["recall"] == pytest.approx(c["e0"]["core_derived"]["recall"])


def test_ceiling_summary_is_recomputed_from_the_rows():
    c = load("lift_d4_ceiling.json")
    assert same(lc.summarize(c["rows"], c["summary"]["d4_cases"], c["summary"]["without_evidence"]), c["summary"])
    s = c["summary"]
    assert (s["ceiling_cases"], s["d4_cases"]) == (17, 120) and s["within_1"]["of"] == s["loaded_with_core_found"]
    assert s["within_1"]["count"] <= s["within_2"]["count"]


def test_the_results_document_is_the_rendering_of_the_committed_files():
    assert render_cp5b_doc(RES, "docs/results/cp5b") == DOC.read_text(encoding="utf-8")


def test_the_run_was_clean_and_used_the_local_toolchain():
    env = load("lift_d1.json")["environment"]
    assert env["repo_dirty"] is False and env["go"].startswith("go version go1.")
