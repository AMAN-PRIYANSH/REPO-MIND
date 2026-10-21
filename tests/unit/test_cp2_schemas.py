import copy

import pytest

from vulntrace.schemas import validate, validation_errors

pytest.importorskip("jsonschema")

STATEMENT = "Reachability only. This verdict does not assess exploitability."

VERDICT = {
    "schema_version": "1.0",
    "case_id": "direct_call",
    "target_app": {"path": "fixtures/reachability", "module": "vtfixtures", "commit": None,
                   "main_package": "vtfixtures/cmd/direct_call"},
    "verdict": "CANT_DETERMINE",
    "reason_codes": ["METHOD_DISAGREEMENT"],
    "per_symbol": [{
        "target": {"package": "vtfixtures/vulnlib", "symbol": "Parse"},
        "result": "CANT_DETERMINE", "reason_code": "METHOD_DISAGREEMENT",
        "methods": {"CALLGRAPH_VTA": "NO_PATH", "LINKER_PRESENCE": "PRESENT"},
        "verified_path": None,
    }],
    "verification": {"status": "NOT_RUN", "checks_run": 0, "failures": []},
    "statement": STATEMENT,
    "provenance": {"pipeline_version": "0.2.0", "helper_contract": "1.0", "vulndb_commit": None,
                   "created_at": "2026-10-21T10:00:00Z"},
}

NAIVE_RESULT = {
    "schema_version": "1.0", "method": "CALLGRAPH_NAIVE",
    "target": {"package": "p", "symbol": "F"}, "main_package": "p/cmd/a",
    "result": "NO_PATH", "details": {}, "error": None, "duration_ms": 3,
}


def test_example_verdict_validates():
    validate("verdict", VERDICT)


@pytest.mark.parametrize("mutate", [
    lambda v: v.update(statement="Reachable."),
    lambda v: v.pop("statement"),
    lambda v: v.update(reason_codes=[]),                                # CANT_DETERMINE needs a reason
    lambda v: v.update(verdict="REACHABLE"),                            # decided verdict with reasons
    lambda v: v["per_symbol"][0].update(reason_code=None),              # symbol CANT_DETERMINE needs a reason
    lambda v: v["per_symbol"][0].update(result="NOT_REACHABLE"),        # decided symbol with a reason
    lambda v: v["per_symbol"][0]["methods"].update(CALLGRAPH_VTA="PRESENT"),
    lambda v: v.update(reason_codes=["EXPLOITABLE"]),
    lambda v: v["verification"].update(status="SKIPPED"),
])
def test_bad_verdicts_are_rejected(mutate):
    v = copy.deepcopy(VERDICT)
    mutate(v)
    assert validation_errors("verdict", v)


def test_naive_method_result_validates_and_uses_callgraph_results():
    validate("method_result", NAIVE_RESULT)
    bad = dict(NAIVE_RESULT, result="PRESENT")
    assert validation_errors("method_result", bad)


def test_cp1_linker_and_vta_results_still_validate():
    linker = dict(NAIVE_RESULT, method="LINKER_PRESENCE", result="ABSENT")
    vta = dict(NAIVE_RESULT, method="CALLGRAPH_VTA", result="PATH_FOUND")
    validate("method_result", linker)
    validate("method_result", vta)


def test_request_schema_requires_mode_fields():
    ok = {"contract_version": "1.0", "mode": "reach", "module_dir": "m", "main_packages": ["./cmd/a"],
          "targets": [{"package": "p", "symbol": "F"}]}
    validate("helper_request", ok)
    for key in ("module_dir", "main_packages", "targets"):
        bad = {k: v for k, v in ok.items() if k != key}
        assert validation_errors("helper_request", bad), key
    assert validation_errors("helper_request", dict(ok, mode="lift"))
    assert validation_errors("helper_request", dict(ok, contract_version="2.0"))
    assert validation_errors("helper_request", {"contract_version": "1.0", "mode": "funcs"})
