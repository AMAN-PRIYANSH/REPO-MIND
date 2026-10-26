"""CP7 contract: recorded pipeline outputs (one per verdict and per reason code) validate against
schemas/verdict.schema.json and keep the output invariants; CP2-era verdicts still validate.
Recorded with tests/contract/record_cp7_verdicts.py; no Go needed here."""

import json
from pathlib import Path

import pytest

from vulntrace.schemas import load_schema, validation_errors
from vulntrace.verdict import STATEMENT, build_verdict

DIR = Path(__file__).resolve().parent / "verdicts_cp7"
INDEX = json.loads((DIR / "index.json").read_text(encoding="utf-8"))


def load(name):
    return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(INDEX))
def test_recorded_verdict_is_valid_and_matches_index(name):
    v = load(name)
    assert validation_errors("verdict", v) == []
    assert (v["verdict"], v["reason_codes"], v["mode"]) == (INDEX[name]["verdict"], INDEX[name]["reason_codes"], INDEX[name]["mode"])
    assert v["statement"] == STATEMENT
    assert v["limitations"] and v["limitations"][0].startswith("Reachability only")
    assert v["toolchain"]["env"] == {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOPROXY": "off"}
    assert (v["verdict"] == "CANT_DETERMINE") == bool(v["reason_codes"])


@pytest.mark.parametrize("name", sorted(INDEX))
def test_reachable_entries_carry_a_verified_path(name):
    v = load(name)
    for e in v["per_symbol"]:
        if e["result"] == "REACHABLE":
            assert e["verified_path"] in e["paths"], "a REACHABLE entry keeps one of the method's own paths"
            assert e["methods"] == {"CALLGRAPH_VTA": "PATH_FOUND", "LINKER_PRESENCE": "PRESENT"}
    if v["verdict"] == "REACHABLE":
        assert v["verification"]["status"] == "PASSED"


def test_every_verdict_and_reason_code_is_recorded():
    schema = load_schema("verdict")
    codes = set(schema["$defs"]["reason_code"]["enum"])
    recorded = {c for x in INDEX.values() for c in x["reason_codes"]}
    assert codes <= recorded, f"no recording for {sorted(codes - recorded)}"
    assert {x["verdict"] for x in INDEX.values()} == {"REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE"}


def test_mode2_reachable_is_candidate_level_with_rank_and_score():
    v = load("reachable_mode2_candidate_level")
    assert v["mode"] == "RELEASE" and v["evidence_level"] == "CANDIDATE_LEVEL"
    r = [e for e in v["per_symbol"] if e["result"] == "REACHABLE"]
    assert r and all(isinstance(e["rank"], int) and isinstance(e["score"], float) for e in r)
    assert v["retrieval"]["top"] and v["policy"]["applied"] is False


def test_mode2_downgrade_keeps_the_raw_verdict():
    v = load("cd_mode2_not_reachable_downgraded")
    assert v["pre_policy_verdict"] == "NOT_REACHABLE" and v["policy"]["applied"] is True


def test_verifier_rejection_records_the_failed_checks():
    v = load("cd_verifier_rejected")
    e = v["per_symbol"][0]
    assert e["pre_verifier_result"] == "REACHABLE" and e["reason_code"] == "VERIFIER_REJECTED"
    # the recorder moved every call site one line down; in direct_call that line is still inside main,
    # so CALL_SITE can pass, and the exact-site EDGE_EXISTS check is what rejects the path
    assert {"EDGE_EXISTS", "REACHABLE_HAS_PATH"} <= {f["check"] for f in e["verifier_failures"]}
    assert v["verification"]["status"] == "FAILED" and v["verification"]["downgraded"] == 1


def test_mode1_reachable_is_changed_function_level():
    v = load("reachable_mode1")
    assert v["mode"] == "FIX" and v["evidence_level"] == "CHANGED_FUNCTION_LEVEL"
    assert v["mode_selection"] == {"requested": "AUTO", "chosen": "FIX", "reason": "FIX_COMMIT_KNOWN",
                                   "explanation": v["mode_selection"]["explanation"]}


def test_cp2_verdicts_still_validate():
    """The CP7 schema only adds optional properties and enum values."""
    mr = lambda m, r: {"target": {"package": "p", "symbol": "F"}, "result": r, "error": None}  # noqa: E731
    for vta, ln in (("PATH_FOUND", "PRESENT"), ("NO_PATH", "ABSENT"), ("NO_PATH", "PRESENT")):
        v = build_verdict("c", {"path": "fixtures/reachability", "module": "vtfixtures", "commit": None,
                                "main_package": "vtfixtures/cmd/x"}, [{"package": "p", "symbol": "F"}],
                          [mr("CALLGRAPH_VTA", vta)], [mr("LINKER_PRESENCE", ln)], created_at="2026-10-21T10:00:00Z")
        assert validation_errors("verdict", v) == []
