import itertools

import pytest

from vulntrace.schemas import validate
from vulntrace.verdict import (
    ANALYSIS_FAILED, CANT_DETERMINE, LINKER_RESULTS, METHOD_DISAGREEMENT, NO_TARGET_SYMBOLS, NOT_REACHABLE,
    REACHABLE, STATEMENT, VERIFIER_REJECTED, VERIFIER_STATES, VTA_RESULTS, build_verdict, case_verdict,
    symbol_verdict,
)

# The rule table from docs/architecture/SYSTEM_ARCHITECTURE.md, row by row.
# verifier: "PASSED" / "FAILED" where the table uses it, "n/a" where it does not.
RULE_TABLE = [
    ("PATH_FOUND", "PRESENT", "PASSED", REACHABLE, None),
    ("PATH_FOUND", "PRESENT", "FAILED", CANT_DETERMINE, VERIFIER_REJECTED),
    ("NO_PATH", "ABSENT", "n/a", NOT_REACHABLE, None),
    ("NO_PATH", "PRESENT", "n/a", CANT_DETERMINE, METHOD_DISAGREEMENT),
    ("PATH_FOUND", "ABSENT", "n/a", CANT_DETERMINE, METHOD_DISAGREEMENT),
    ("ERROR", "any", "n/a", CANT_DETERMINE, ANALYSIS_FAILED),
    ("any", "ERROR", "n/a", CANT_DETERMINE, ANALYSIS_FAILED),
]


def expand(row):
    vta, linker, verifier = row[:3]
    vtas = VTA_RESULTS if vta == "any" else (vta,)
    linkers = LINKER_RESULTS if linker == "any" else (linker,)
    verifiers = VERIFIER_STATES if verifier == "n/a" else (verifier,)
    return itertools.product(vtas, linkers, verifiers)


@pytest.mark.parametrize("row", RULE_TABLE, ids=[f"{r[0]}+{r[1]}+{r[2]}" for r in RULE_TABLE])
def test_every_row_of_the_rule_table(row):
    for vta, linker, verifier in expand(row):
        assert symbol_verdict(vta, linker, verifier) == (row[3], row[4]), (vta, linker, verifier)


def test_rule_table_covers_every_combination_consistently():
    covered = {}
    for row in RULE_TABLE:
        for combo in expand(row):
            covered.setdefault(combo, set()).add((row[3], row[4]))
    combos = set(itertools.product(VTA_RESULTS, LINKER_RESULTS, VERIFIER_STATES))
    # PATH_FOUND+PRESENT with the verifier not run is the CP2 state (verifier column not applicable).
    combos.discard(("PATH_FOUND", "PRESENT", None))
    assert combos <= set(covered)
    assert all(len(v) == 1 for v in covered.values()), "two rows disagree on one combination"


def test_verifier_not_run_is_treated_as_not_yet_applicable():
    assert symbol_verdict("PATH_FOUND", "PRESENT", None) == (REACHABLE, None)


def test_unknown_values_are_rejected():
    with pytest.raises(ValueError):
        symbol_verdict("PRESENT", "PATH_FOUND")
    with pytest.raises(ValueError):
        symbol_verdict("NO_PATH", "ABSENT", "SKIPPED")


@pytest.mark.parametrize("symbols,expected", [
    ([], (CANT_DETERMINE, [NO_TARGET_SYMBOLS])),
    ([(REACHABLE, None)], (REACHABLE, [])),
    ([(NOT_REACHABLE, None)], (NOT_REACHABLE, [])),
    ([(NOT_REACHABLE, None), (REACHABLE, None)], (REACHABLE, [])),
    ([(CANT_DETERMINE, ANALYSIS_FAILED), (REACHABLE, None)], (REACHABLE, [])),
    ([(NOT_REACHABLE, None), (NOT_REACHABLE, None)], (NOT_REACHABLE, [])),
    ([(NOT_REACHABLE, None), (CANT_DETERMINE, METHOD_DISAGREEMENT)], (CANT_DETERMINE, [METHOD_DISAGREEMENT])),
    ([(CANT_DETERMINE, METHOD_DISAGREEMENT), (CANT_DETERMINE, ANALYSIS_FAILED), (CANT_DETERMINE, ANALYSIS_FAILED)],
     (CANT_DETERMINE, [ANALYSIS_FAILED, METHOD_DISAGREEMENT])),
])
def test_case_level_aggregation(symbols, expected):
    assert case_verdict(symbols) == expected


def mr(method, symbol, result, code=None):
    return {"method": method, "target": {"package": "p", "symbol": symbol}, "result": result,
            "error": {"code": code, "message": ""} if code else None}


APP = {"path": "fixtures/reachability", "module": "vtfixtures", "commit": None, "main_package": "vtfixtures/cmd/x"}


def test_build_verdict_validates_and_records_methods():
    targets = [{"package": "p", "symbol": "A"}, {"package": "p", "symbol": "B"}]
    v = build_verdict("x", APP, targets,
                      [mr("CALLGRAPH_VTA", "A", "NO_PATH"), mr("CALLGRAPH_VTA", "B", "ERROR", "TARGET_NOT_FOUND")],
                      [mr("LINKER_PRESENCE", "A", "PRESENT"), mr("LINKER_PRESENCE", "B", "ABSENT")],
                      created_at="2026-10-21T00:00:00Z")
    validate("verdict", v)
    assert v["verdict"] == CANT_DETERMINE and v["reason_codes"] == [ANALYSIS_FAILED, METHOD_DISAGREEMENT]
    assert v["statement"] == STATEMENT
    assert v["verification"] == {"status": "NOT_RUN", "checks_run": 0, "failures": []}
    assert v["per_symbol"][1]["method_errors"] == {"CALLGRAPH_VTA": "TARGET_NOT_FOUND"}
    assert all(s["verified_path"] is None for s in v["per_symbol"])


def test_build_verdict_no_targets_and_decided_verdicts_validate():
    v = build_verdict("x", APP, [], [], [], created_at="2026-10-21T00:00:00Z")
    validate("verdict", v)
    assert (v["verdict"], v["reason_codes"]) == (CANT_DETERMINE, [NO_TARGET_SYMBOLS])
    t = [{"package": "p", "symbol": "A"}]
    for vta, linker, verdict in (("PATH_FOUND", "PRESENT", REACHABLE), ("NO_PATH", "ABSENT", NOT_REACHABLE)):
        v = build_verdict("x", APP, t, [mr("CALLGRAPH_VTA", "A", vta)], [mr("LINKER_PRESENCE", "A", linker)])
        validate("verdict", v)
        assert v["verdict"] == verdict and v["reason_codes"] == []


def test_build_verdict_requires_both_methods_per_target():
    with pytest.raises(ValueError):
        build_verdict("x", APP, [{"package": "p", "symbol": "A"}], [mr("CALLGRAPH_VTA", "A", "NO_PATH")], [])
