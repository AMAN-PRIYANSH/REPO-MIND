"""CP9 contract: recorded helper responses with the feasibility filter and recorded verdicts
(tests/contract/record_cp9.py, real runs on fixtures/feasibility) validate against the schemas and
keep the CP9 invariants. No Go needed here."""

import json
from pathlib import Path

import pytest

from vulntrace.methods.callgraph import to_method_results
from vulntrace.methods.helper import parse_response
from vulntrace.schemas import validation_errors

DIR = Path(__file__).resolve().parent / "cp9"
RESP_INDEX = json.loads((DIR / "responses" / "index.json").read_text(encoding="utf-8"))
VERD_INDEX = json.loads((DIR / "verdicts" / "index.json").read_text(encoding="utf-8"))
PARSE = {"package": "vtfeas/vulnlib", "symbol": "Parse"}


def response(name):
    return (DIR / "responses" / f"{name}.json").read_text(encoding="utf-8")


def verdict(name):
    return json.loads((DIR / "verdicts" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(RESP_INDEX))
def test_recorded_response_validates_and_maps(name):
    resp = parse_response(response(name), "reach", RESP_INDEX[name]["exit_code"])
    r = resp["results"][0]
    want = RESP_INDEX[name]["status"]
    if want is None:
        assert "feasibility" not in response(name), "no filter requested, no feasibility field anywhere"
    else:
        f = r["feasibility"]
        assert f["status"] == want and f["max_examined_paths"] == 20
        assert resp["stats"]["feasibility"]["max_examined_paths"] == 20
        if want == "INFEASIBLE":
            assert all(ex["first_infeasible"]["reason"] for ex in f["examined"])
        if want == "UNDECIDED":
            assert f["undecided_reason"] == "STATE_LIMIT" and resp["stats"]["feasibility"]["state_limit_hit"]
    mr = to_method_results("CALLGRAPH_VTA", "vtfeas/cmd/x", [PARSE], resp, None, 1)[0]
    assert validation_errors("method_result", mr) == []
    assert ("feasibility" in mr["details"]) == (want is not None)


def test_recorded_requests_validate():
    for name in RESP_INDEX:
        p = DIR / "responses" / f"{name}.request.json"
        if p.exists():
            assert validation_errors("helper_request", json.loads(p.read_text(encoding="utf-8"))) == []


def test_schema_rejects_inconsistent_answers():
    resp = json.loads(response("reach_infeasible"))
    bad = json.loads(json.dumps(resp))
    bad["results"][0]["feasibility"]["evidence_path"] = bad["results"][0]["paths"][0]
    assert validation_errors("helper_response", bad), "INFEASIBLE with an evidence path must not validate"
    bad = json.loads(json.dumps(resp))
    bad["results"][0]["feasibility"]["examined"][0]["first_infeasible"] = None
    assert validation_errors("helper_response", bad), "INFEASIBLE needs an infeasible step on every examined path"
    bad = json.loads(json.dumps(resp))
    bad["results"][0]["feasibility"]["examined"][0]["first_infeasible"]["pattern"] = "F4"
    assert validation_errors("helper_response", bad), "only F1-F3 exist"


@pytest.mark.parametrize("name", sorted(VERD_INDEX))
def test_recorded_verdict_matches_index(name):
    v, want = verdict(name), VERD_INDEX[name]
    assert validation_errors("verdict", v) == []
    e = v["per_symbol"][0]
    assert (v["verdict"], v["reason_codes"], e["reason_code"]) == (want["verdict"], want["reason_codes"], want["entry_reason"])
    assert (e.get("feasibility") or {}).get("status") == want["filter_status"]
    if not want["filter_enabled"]:
        assert "feasibility" not in v and "pre_feasibility_result" not in e
        return
    assert v["feasibility"]["enabled"] and v["feasibility"]["max_examined_paths"] == 20
    assert e["pre_feasibility_result"] == "REACHABLE", "the filter only ever sees REACHABLE entries"
    if want["failed_check"]:
        assert want["failed_check"] in {f["check"] for f in e["verifier_failures"]}
    if v["verdict"] == "REACHABLE":
        f = e["feasibility"]
        if f["status"] == "FEASIBLE":
            assert e["verified_path"] == f["evidence_path"], "the reported path is the one that passed the filter"
        else:
            assert e["verified_path"] in e["paths"]
    if e["reason_code"] == "PATHS_INFEASIBLE":
        assert e["verified_path"] is None and v["feasibility"]["downgraded"] == 1
        assert v["feasibility"]["pre_filter_verdict"] == "REACHABLE"
        assert v["verification"]["checks_by_kind"]["INFEASIBLE_STEP"]["failed"] == 0


def test_every_filter_status_and_pattern_is_recorded():
    statuses = {x["filter_status"] for x in VERD_INDEX.values()}
    assert {"FEASIBLE", "INFEASIBLE", "UNDECIDED", None} <= statuses
    patterns = set()
    for name, x in VERD_INDEX.items():
        if x["entry_reason"] == "PATHS_INFEASIBLE":
            patterns |= {ex["first_infeasible"]["pattern"] for ex in verdict(name)["per_symbol"][0]["feasibility"]["examined"]}
    assert patterns == {"F1", "F2", "F3"}
