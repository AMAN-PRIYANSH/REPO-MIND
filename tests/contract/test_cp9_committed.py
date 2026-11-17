"""CP9: the committed results under docs/results/cp9/ agree with each other and with the schema, and
keep the CP9 promises (downgrade-only; filter-off reproduces CP7/CP7b; D3 labelled in-sample; D3b sheet
covers every case REACHABLE in either run and has blank answer fields until the supervisor fills them)."""

import json

import pytest

from vulntrace.eval.feasibility_real import read_verdicts
from vulntrace.paths import REPO_ROOT
from vulntrace.schemas import validation_errors

CP9 = REPO_ROOT / "docs" / "results" / "cp9"
STRENGTH = {"REACHABLE": 1, "NOT_REACHABLE": 1, "CANT_DETERMINE": 0}


def load(rel):
    return json.loads((CP9 / rel).read_text(encoding="utf-8"))


def test_fixture_results():
    fx = load("fixtures.json")
    assert fx["cp7_reproduction"]["identical"] is True
    assert fx["cp7_fixtures_with_filter"]["false_downgrades"] == []
    c = fx["cp9_fixtures"]
    assert c["false_downgrades"] == [] and c["not_as_expected"] == []
    assert c["by_kind"]["INFEASIBLE"]["downgraded"] == c["by_kind"]["INFEASIBLE"]["cases"]
    for p in ("F1", "F2", "F3"):
        pp = c["per_pattern"][p]
        assert pp["infeasible_cases"] >= 2 and pp["lookalikes"] >= 2, "at least two of each per pattern (CP9 deliverable 3)"


@pytest.mark.parametrize("name", ["d3", "d3b"])
def test_real_sets(name):
    doc = load(f"{name}/{name}_feasibility.json")
    off, on = read_verdicts(CP9 / name / "verdicts_off"), read_verdicts(CP9 / name / "verdicts_on")
    assert len(doc["rows"]) == len(off) == len(on)
    for r in doc["rows"]:
        a, b = off[r["id"]], on[r["id"]]
        assert validation_errors("verdict", a) == [] and validation_errors("verdict", b) == []
        assert (a["verdict"], b["verdict"]) == (r["verdict_off"], r["verdict_on"])
        assert "feasibility" not in a and b["feasibility"]["enabled"] is True
        assert b["verdict"] == a["verdict"] or b["verdict"] == "CANT_DETERMINE", "downgrade-only"
        assert b["feasibility"]["max_examined_paths"] == doc["feasibility_settings"]["max_examined_paths"] == 20
    assert doc["toolchain"]["off"]["helper"] == doc["toolchain"]["on"]["helper"] == ["go1.26.10"]
    if name == "d3":
        assert doc["label"].startswith("IN-SAMPLE")
        assert doc["cp7b_reproduction"]["all_identical"] is True


def test_d3b_selection_and_sheet():
    cases = load("d3b/d3_cases.json")["cases"]
    excluded = set(json.loads((REPO_ROOT / "docs" / "evaluation" / "d3b_candidates.json").read_text())["excluded_d3_apps"])
    assert not {c["app_repo"] for c in cases} & excluded
    rows = load("d3b/d3b_feasibility.json")["rows"]
    sheet = load("d3b/adjudication/adjudication.json")
    want = {r["id"] for r in rows if "REACHABLE" in (r["verdict_off"], r["verdict_on"])}
    assert {c["id"] for c in sheet["cases"]} == want
