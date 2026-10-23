"""The committed case lists are internally consistent and agree with the evidence the retrieval
runs actually used (CP5b task 0c: GO-2020-0006 had a stale PSEUDO_VERSION_UNRESOLVED record)."""

import json
from collections import Counter

from vulntrace.eval.evidence_gate import check_evidence
from vulntrace.paths import REPO_ROOT

DATASETS = REPO_ROOT / "docs" / "results" / "datasets"


def _load(name):
    return json.loads((DATASETS / name).read_text(encoding="utf-8"))


def test_status_counts_match_the_cases():
    for name in ("D1_cases.json", "D4_cases.json"):
        d = _load(name)
        assert d["status_counts"] == dict(sorted(Counter(c["status"] for c in d["cases"]).items())), name
        assert len(d["cases"]) == d["sample_count"], name


def test_go_2020_0006_is_available_as_every_environment_rebuilds_it():
    rec = next(c for c in _load("D4_cases.json")["cases"] if c["id"] == "GO-2020-0006")
    assert (rec["status"], rec["candidate_count"], rec["commit_count"]) == ("AVAILABLE", 1, 4)


def test_d4_list_agrees_with_the_evidence_the_cp4_runs_used():
    """docs/results/cp4/cases.json is built from rebuilt evidence: no case may differ from the list."""
    used = {c["id"]: c for c in json.loads((REPO_ROOT / "docs/results/cp4/cases.json").read_text())["cases"]}
    d4 = _load("D4_cases.json")
    diffs = [(c["id"], c["status"], used[c["id"]]["status"]) for c in d4["cases"]
             if c["id"] in used and used[c["id"]]["status"] != c["status"]]
    assert diffs == []


def test_the_gate_passes_with_zero_differences_for_the_committed_list():
    d4 = _load("D4_cases.json")
    actual = {c["id"]: c["status"] for c in d4["cases"]}
    assert check_evidence(d4, actual, total_chunks=1, max_differences=0) == []
