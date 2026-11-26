"""CP10: the committed result files keep what the report claims (no Go, no network)."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "docs" / "results" / "cp10"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_every_committed_file_is_under_512_kib():
    for p in R.rglob("*"):
        if p.is_file():
            assert p.stat().st_size <= 512 * 1024, p


def test_legacy_targets_reproduce_cp7_and_cp9():
    assert load(R / "fixtures.json")["cp7_reproduction"]["identical"] is True
    for s, n in (("d3", 14), ("d3b", 11)):
        rep = load(R / s / f"{s}_verdicts.json")["cp9_reproduction"]
        assert rep["all_identical"] is True and rep["compared"] == n and len(rep["identical"]) == n


@pytest.mark.parametrize("s", ["d3", "d3b", "d3c"])
def test_hygiene_never_creates_not_reachable_in_stratum_n(s):
    doc = load(R / s / f"{s}_verdicts.json")
    assert doc["summary"]["N"]["hygiene_made_not_reachable"] == [] if "N" in doc["summary"] else True
    for r in doc["rows"]:
        if r["stratum"] == "N" and r["hygiene"]["verdict"] == "NOT_REACHABLE":
            assert r["legacy"]["verdict"] == "NOT_REACHABLE", r["id"]
        assert not (r.get("partial_run"))
    assert not doc.get("partial_run")


def test_d3c_is_the_selection_and_excludes_earlier_apps():
    cases = load(R / "d3c" / "d3c_cases.json")
    sel = load(R / "d3c" / "d3c_selection.json")
    doc = load(R / "d3c" / "d3c_verdicts.json")
    assert [r["id"] for r in doc["rows"]] == [c["id"] for c in cases["cases"]]
    assert sel["seed"] == 20261126 and sel["rules"] == "docs/evaluation/D3C_SELECTION_RULES.md"
    earlier = {c["app_repo"] for f in ("cp7b/d3_cases.json", "cp9/d3b/d3_cases.json")
               for c in load(ROOT / "docs" / "results" / f)["cases"]}
    assert not earlier & {c["app_repo"] for c in cases["cases"]}
    assert sel["totals"] == {"S": sum(c["stratum"] == "S" for c in cases["cases"]),
                             "N": sum(c["stratum"] == "N" for c in cases["cases"])}
    assert doc["toolchain"]["hygiene"]["helper"] == ["go1.26.10"]


def test_sheet_has_every_d3c_case_and_the_truth_only_items():
    sheet = load(R / "adjudication" / "adjudication.json")
    d3c = load(R / "d3c" / "d3c_verdicts.json")
    items = {(c["set"], c["id"]) for c in sheet["cases"]}
    assert {("d3c", r["id"]) for r in d3c["rows"]} <= items
    cp7b = {r["id"]: r["verdict"] for r in load(ROOT / "docs/results/cp7b/d3_triage.json")["rows"]}
    cp9 = {r["id"]: r["verdict_on"] for r in load(ROOT / "docs/results/cp9/d3b/d3b_feasibility.json")["rows"]}
    assert {i for s, i in items if s == "d3"} == {i for i, v in cp7b.items() if v == "REACHABLE"}
    assert {i for s, i in items if s == "d3b"} == {i for i, v in cp9.items() if v != "REACHABLE"}
    for c in sheet["cases"]:
        assert c["path_judgement_asked"] == (c["set"] == "d3c" and c["verdict_hygiene"] == "REACHABLE")
        assert c["decision_targets"], c["id"]
