"""CP10 deliverable 1: target hygiene for Mode 1 (fake runners, no Go).

Stratum S (curated vulndb symbols for the module): the curated symbols decide (origin VULNDB), the
fix's changed functions are extra evidence. Stratum N (none): changed functions decide except the
context-only ones; a REACHABLE resting only on context-only targets is CANT_DETERMINE
(ONLY_CONTEXT_TARGETS_REACHABLE). LEGACY is the CP7/CP9 behaviour."""

import copy
import itertools
from pathlib import Path

import pytest

from tests.unit.cp7_support import LIB, MAIN_PKG, FakeMethod, advisory, fix_evidence, path, runners
from vulntrace.pipeline import aggregate, triage
from vulntrace.pipeline import symbols as sy
from vulntrace.schemas import validation_errors
from vulntrace.verdict import (ANALYSIS_FAILED, CANT_DETERMINE, NOT_REACHABLE, ONLY_CONTEXT_TARGETS_REACHABLE,
                               REACHABLE)

M = MAIN_PKG


def curated_advisory(symbols: list[str], module: str = LIB) -> dict:
    a = advisory(module=module)
    a["modules"] = [{"module": module, "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
                     "packages": [{"package": module, "core_symbols": list(symbols), "derived_symbols": ["Derived"]}]}]
    return a


def context_fix(cands: list[tuple[str, str, bool]]) -> dict:
    """FixEvidence whose candidate i is context-only when its flag is True (its hunk changes no line
    inside the candidate's range)."""
    fe = fix_evidence([(d, sym, "BOTH") for d, sym, _ in cands])
    for c, h, (_, _, ctx) in zip(fe["candidates"], fe["hunks"], cands):
        if ctx:
            h["old_start"] = h["new_start"] = 30          # the changed line (31) is outside 10-20
    return fe


def _run(adv, fe, vta, linker, policy=sy.POLICY_HYGIENE):
    req = triage.TriageRequest(case_id="GO-TEST-1", app=Path("/fake/app"), mode="fix",
                               advisory=adv, fix_evidence=fe, module_rel="", run_verifier=False, target_policy=policy)
    v = triage.run_triage(req, runners(vta, linker))
    assert validation_errors("verdict", v) == [], validation_errors("verdict", v)
    return v


def reach(*syms):
    """Fake method tables where `syms` are reachable from M and every other target is not."""
    vt = {(M, LIB, s): ("PATH_FOUND", {"paths": [path(M, {"package": LIB, "symbol": s}, [(f"{LIB}.{s}", "cmd/a/main.go", 4)])]})
          for s in syms}
    lk = {(M, LIB, s): ("PRESENT", {}) for s in syms}
    return FakeMethod("vta", vt), FakeMethod("linker", lk, default=("ABSENT", {}))


# --- symbol selection --------------------------------------------------------------------------------
def test_curated_symbols_come_from_the_report_symbols_not_derived():
    adv = curated_advisory(["Parse", "Conn.Read"])
    assert sy.curated_symbols(adv, LIB) == [{"package": LIB, "symbol": "Parse"}, {"package": LIB, "symbol": "Conn.Read"}]
    assert sy.curated_symbols(adv, "example.com/other") == []
    assert sy.stratum_of(adv, LIB) == sy.STRATUM_S and sy.stratum_of(advisory(), LIB) == sy.STRATUM_N


def test_stratum_s_curated_symbols_decide_and_changed_functions_are_extra():
    fe = fix_evidence([("", "Parse", "BOTH"), ("", "helper", "OLD")])
    t, nc, st = sy.hygiene_mode1_symbols(fe, curated_advisory(["Parse", "Other"]), LIB, "")
    assert st == sy.STRATUM_S and nc == []
    assert [(x["symbol"], x["origin"], x["decides_verdict"]) for x in t] == [
        ("Parse", sy.VULNDB, True), ("Other", sy.VULNDB, True), ("helper", sy.FIX_CHANGED, False)]
    assert t[2]["extra_reason"] == sy.EXTRA_FIX_CHANGED


def test_stratum_n_context_only_targets_do_not_decide():
    fe = context_fix([("", "Changed", False), ("", "Neighbour", True)])
    t, _, st = sy.hygiene_mode1_symbols(fe, advisory(), LIB, "")
    assert st == sy.STRATUM_N
    assert [(x["symbol"], x["context_only"], x["decides_verdict"]) for x in t] == [
        ("Changed", False, True), ("Neighbour", True, False)]
    assert t[1]["extra_reason"] == sy.EXTRA_CONTEXT_ONLY


def test_legacy_targets_are_the_cp7_mode1_targets():
    fe = context_fix([("", "Changed", False), ("", "Neighbour", True)])
    legacy, _ = sy.mode1_symbols(fe, LIB, "")
    assert all(x["decides_verdict"] and "extra_reason" not in x for x in legacy)


# --- verdicts ---------------------------------------------------------------------------------------
def test_stratum_s_reachable_needs_a_curated_symbol():
    fe = fix_evidence([("", "helper", "OLD")])
    v = _run(curated_advisory(["Parse"]), fe, *reach("helper"))
    assert v["verdict"] == NOT_REACHABLE                       # helper is reachable but only extra evidence
    assert v["target_policy"]["stratum"] == "S" and v["target_policy"]["deciding_targets"] == 1
    extra = [e for e in v["per_symbol"] if e["target"]["symbol"] == "helper"][0]
    assert extra["result"] == REACHABLE and extra["decides_verdict"] is False and extra["origin"] == sy.FIX_CHANGED
    assert _run(curated_advisory(["Parse"]), fe, *reach("helper"), policy=sy.POLICY_LEGACY)["verdict"] == REACHABLE


def test_stratum_s_curated_symbol_reachable():
    v = _run(curated_advisory(["Parse"]), fix_evidence([("", "helper", "OLD")]), *reach("Parse"))
    assert v["verdict"] == REACHABLE
    assert [e["origin"] for e in v["per_symbol"] if e["result"] == REACHABLE] == [sy.VULNDB]


def test_stratum_n_only_context_targets_reachable_is_cant_determine():
    fe = context_fix([("", "Changed", False), ("", "Neighbour", True)])
    v = _run(advisory(), fe, *reach("Neighbour"))
    assert (v["verdict"], v["reason_codes"]) == (CANT_DETERMINE, [ONLY_CONTEXT_TARGETS_REACHABLE])
    assert _run(advisory(), fe, *reach("Neighbour"), policy=sy.POLICY_LEGACY)["verdict"] == REACHABLE
    assert _run(advisory(), fe, *reach("Changed"))["verdict"] == REACHABLE
    assert _run(advisory(), fe, *reach())["verdict"] == NOT_REACHABLE


def test_stratum_n_context_target_error_never_becomes_not_reachable():
    fe = context_fix([("", "Changed", False), ("", "Neighbour", True)])
    vta = FakeMethod("vta", {(M, LIB, "Neighbour"): ("ERROR", {"code": "TARGET_NOT_FOUND"})})
    v = _run(advisory(), fe, vta, FakeMethod("linker", default=("ABSENT", {})))
    legacy = _run(advisory(), fe, vta, FakeMethod("linker", default=("ABSENT", {})), policy=sy.POLICY_LEGACY)
    assert legacy["verdict"] == CANT_DETERMINE and (v["verdict"], v["reason_codes"]) == (CANT_DETERMINE, [ANALYSIS_FAILED])


def test_legacy_output_has_no_cp10_fields():
    fe = context_fix([("", "Changed", False), ("", "Neighbour", True)])
    v = _run(curated_advisory(["Parse"]), fe, *reach("Neighbour"), policy=sy.POLICY_LEGACY)
    assert "target_policy" not in v
    assert all("extra_reason" not in e and e["origin"] == sy.FIX_CHANGED for e in v["per_symbol"])


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        _run(advisory(), fix_evidence([("", "Parse", "BOTH")]), *reach(), policy="NEW")


def test_mode2_and_given_targets_are_not_affected():
    req = triage.TriageRequest(case_id="x", app=Path("/fake/app"), mode="targets",
                               targets=[{"package": LIB, "symbol": "Parse"}], run_verifier=False)
    v = triage.run_triage(req, runners(*reach("Parse")))
    assert "target_policy" not in v and v["verdict"] == REACHABLE


# --- the stratum N guarantee, exhaustively over small entry sets ------------------------------------
RESULTS = [REACHABLE, NOT_REACHABLE, CANT_DETERMINE]


def _entry(result, context):
    e = {"target": {"package": LIB, "symbol": "f"}, "result": result,
         "reason_code": ANALYSIS_FAILED if result == CANT_DETERMINE else None, "decides_verdict": not context,
         "main_package": M}
    if context:
        e["extra_reason"] = sy.EXTRA_CONTEXT_ONLY
    return e


@pytest.mark.parametrize("n", [1, 2, 3])
def test_stratum_n_hygiene_only_turns_reachable_into_cant_determine(n):
    for results in itertools.product(RESULTS, repeat=n):
        for flags in itertools.product([False, True], repeat=n):
            for incomplete in (False, True):
                entries = [_entry(r, c) for r, c in zip(results, flags)]
                legacy = aggregate.case_result([dict(e, decides_verdict=True) for e in entries], (), incomplete)
                new = aggregate.hygiene_case_result(copy.deepcopy(entries), (), incomplete, "N")
                assert new == legacy or (legacy[0] == REACHABLE and new == (CANT_DETERMINE, [ONLY_CONTEXT_TARGETS_REACHABLE]))
                if new[0] == NOT_REACHABLE:
                    assert legacy[0] == NOT_REACHABLE


def test_hygiene_case_result_is_monotone_under_downgrades():
    """The verifier only weakens entries; the stratum N rule must then never strengthen the case."""
    for results in itertools.product(RESULTS, repeat=3):
        for flags in itertools.product([False, True], repeat=3):
            before = [_entry(r, c) for r, c in zip(results, flags)]
            vb, _ = aggregate.hygiene_case_result(before, (), False, "N")
            for i, r in enumerate(results):
                if r == CANT_DETERMINE:
                    continue
                after = copy.deepcopy(before)
                after[i] = _entry(CANT_DETERMINE, flags[i])
                va, _ = aggregate.hygiene_case_result(after, (), False, "N")
                assert aggregate.not_stronger(vb, va), (results, flags, i, vb, va)
