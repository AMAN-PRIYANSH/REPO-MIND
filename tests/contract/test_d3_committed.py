"""CP7b: the committed D3 files are consistent with each other, valid against the verdict schema,
and free of local paths. Skips (with a reason) until the D3 run has been committed."""

import json
import re

import pytest

from vulntrace.d3 import score as sc
from vulntrace.d3 import sheet as sh
from vulntrace.paths import REPO_ROOT
from vulntrace.schemas import validation_errors

CP7B = REPO_ROOT / "docs" / "results" / "cp7b"
LOCAL = re.compile(r"/tmp/|/root/|/home/[^/\"]+/|[A-Za-z]:\\\\Users\\\\")


def _read(name):
    p = CP7B / name
    if not p.is_file():
        pytest.skip(f"{p.relative_to(REPO_ROOT)} is not committed yet")
    return json.loads(p.read_text(encoding="utf-8"))


def test_case_list_matches_selection():
    sel, cases = _read("d3_selection.json"), _read("d3_cases.json")
    kept = [c for c in sel["candidates"] if c["status"] == "KEPT"]
    assert len(kept) == cases["apps"] <= 5
    assert {c["repo"] for c in kept} == {c["app_repo"] for c in cases["cases"]}
    assert len(cases["cases"]) == cases["case_count"] == sum(len(k["cases"]) for k in kept)
    for c in cases["cases"]:
        assert re.fullmatch(r"[0-9a-f]{40}", c["app_commit"]) and c["app_url"] == "https://" + c["app_repo"]
    assert sel["run"]["repo_dirty"] is False


def test_triage_rows_cover_every_case_and_verdicts_validate():
    cases, doc = _read("d3_cases.json"), _read("d3_triage.json")
    assert [r["id"] for r in doc["rows"]] == [c["id"] for c in cases["cases"]]
    assert "partial_run" not in doc
    for r in doc["rows"]:
        if r.get("verdict") is None:
            continue
        p = CP7B / "verdicts" / f"{r['id']}.json"
        v = json.loads(p.read_text(encoding="utf-8"))
        assert validation_errors("verdict", v) == [], p
        assert v["verdict"] == r["verdict"] and v["case_id"] == r["id"]
        assert v["toolchain"]["env"]["GOTOOLCHAIN"] == "local" and v["toolchain"]["env"]["CGO_ENABLED"] == "0"


def test_no_local_paths_in_committed_d3_files():
    if not CP7B.is_dir():
        pytest.skip("no cp7b results yet")
    for p in CP7B.rglob("*"):
        if p.is_file():
            hits = LOCAL.findall(p.read_text(encoding="utf-8"))
            assert not hits, f"{p}: {hits[:3]}"


def test_adjudication_sheet_matches_triage_and_uses_allowed_values():
    doc = _read("d3_triage.json")
    sheet = _read("adjudication/adjudication.json")
    assert sheet["sample_rule"] == sh.SAMPLE_RULE
    sample = sh.sample(doc["rows"])
    assert {c["id"] for c in sheet["cases"] if c["adjudicate"]} == set(sample)
    # every problem except "not adjudicated yet" would stop scoring
    problems = [e for e in sc.validate(sheet, doc) if "in the sample but not adjudicated" not in e]
    assert problems == []
    for r in doc["rows"]:
        assert (CP7B / "adjudication" / sh.app_file_name(r["app_repo"])).is_file()
