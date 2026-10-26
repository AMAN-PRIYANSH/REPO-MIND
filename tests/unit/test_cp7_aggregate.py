"""CP7 case aggregation, the Mode 2 policy and the downgrade-only guard."""

import copy
import itertools

import pytest

from vulntrace.pipeline import aggregate as ag
from vulntrace.verdict import CANT_DETERMINE as CD, NOT_REACHABLE as NR, REACHABLE as R

VALUES = (R, NR, CD)


def e(result, code=None, decides=True, sym="F", main="m"):
    if result == CD and code is None:
        code = "METHOD_DISAGREEMENT"
    return {"target": {"package": "p", "symbol": sym}, "main_package": main, "result": result,
            "reason_code": code if result == CD else None, "methods": {"CALLGRAPH_VTA": "NO_PATH", "LINKER_PRESENCE": "ABSENT"},
            "paths": [], "verified_path": None, "decides_verdict": decides}


def test_any_reachable_is_reachable():
    assert ag.case_result([e(NR), e(R, sym="G"), e(CD, sym="H")]) == (R, [])


def test_all_not_reachable_is_not_reachable():
    assert ag.case_result([e(NR), e(NR, sym="G")]) == (NR, [])


def test_incomplete_coverage_blocks_not_reachable_but_not_reachable_reachable():
    assert ag.case_result([e(NR)], incomplete=True) == (CD, ["INCOMPLETE_COVERAGE"])
    assert ag.case_result([e(R)], incomplete=True) == (R, [])


def test_mixed_gives_cant_determine_with_entry_codes():
    v, codes = ag.case_result([e(NR), e(CD, "ANALYSIS_FAILED", sym="G"), e(CD, "METHOD_DISAGREEMENT", sym="H")])
    assert v == CD and codes == ["ANALYSIS_FAILED", "METHOD_DISAGREEMENT"]


def test_blocking_codes_and_no_symbols():
    assert ag.case_result([], ["NO_FIX_EVIDENCE"]) == (CD, ["NO_FIX_EVIDENCE"])
    assert ag.case_result([]) == (CD, ["NO_TARGET_SYMBOLS"])


def test_lifted_symbols_never_decide():
    assert ag.case_result([e(NR), e(R, decides=False, sym="Lifted")]) == (NR, [])
    assert ag.case_result([e(R, decides=False)]) == (CD, ["NO_TARGET_SYMBOLS"])


def test_mode2_policy_only_touches_not_reachable():
    assert ag.apply_mode2_policy(NR, []) == (CD, ["MODE2_NOT_REACHABLE_DOWNGRADED"], True)
    assert ag.apply_mode2_policy(R, []) == (R, [], False)
    assert ag.apply_mode2_policy(CD, ["X"]) == (CD, ["X"], False)
    assert ag.apply_mode2_policy(NR, [], ag.MODE2_POLICY_KEEP) == (NR, [], False)
    with pytest.raises(ValueError):
        ag.apply_mode2_policy(R, [], "SOMETIMES")


def test_not_stronger_table():
    for b, a in itertools.product(VALUES, VALUES):
        assert ag.not_stronger(b, a) == (a == b or a == CD)


def _verdict(entries, verdict):
    return {"per_symbol": entries, "verdict": verdict}


def test_guard_allows_downgrades_and_rejects_everything_else():
    before = _verdict([e(R), e(NR, sym="G")], R)
    after = copy.deepcopy(before)
    after["per_symbol"][0].update(result=CD, reason_code="VERIFIER_REJECTED")
    after["verdict"] = CD
    ag.assert_downgrade_only(before, after)
    for mutate in (
        lambda a: a["per_symbol"][1].update(result=R),                                # NR -> R
        lambda a: a.update(verdict=NR),                                               # R -> NR
        lambda a: a["per_symbol"].append(e(R, sym="New")),                            # symbol added
        lambda a: a["per_symbol"].pop(),                                              # symbol removed
        lambda a: a["per_symbol"][0]["methods"].update(CALLGRAPH_VTA="PATH_FOUND"),   # method result changed
        lambda a: a["per_symbol"][0].update(paths=[{"entry": {}, "target": {}, "edges": []}]),  # path changed
        lambda a: a["per_symbol"][0].update(verified_path={"entry": {}, "target": {}, "edges": []}),  # invented path
        lambda a: a["per_symbol"][1].update(decides_verdict=False),                   # decision role changed
    ):
        bad = copy.deepcopy(before)
        mutate(bad)
        with pytest.raises(ag.DowngradeViolation):
            ag.assert_downgrade_only(before, bad)


def test_cant_determine_never_becomes_an_answer():
    before = _verdict([e(CD)], CD)
    for v in (R, NR):
        bad = copy.deepcopy(before)
        bad["per_symbol"][0].update(result=v, reason_code=None)
        bad["verdict"] = v
        with pytest.raises(ag.DowngradeViolation):
            ag.assert_downgrade_only(before, bad)


@pytest.mark.parametrize("incomplete", [False, True])
def test_case_result_is_monotone_under_entry_downgrades(incomplete):
    """Exhaustive over three entries: weakening any subset of entries never strengthens the case."""
    for results in itertools.product(VALUES, repeat=3):
        entries = [e(r, sym=f"S{i}") for i, r in enumerate(results)]
        before = ag.case_result(entries, incomplete=incomplete)[0]
        for mask in itertools.product((False, True), repeat=3):
            weakened = [e(CD, "VERIFIER_REJECTED", sym=x["target"]["symbol"]) if m else x for x, m in zip(entries, mask)]
            after = ag.case_result(weakened, incomplete=incomplete)[0]
            assert ag.not_stronger(before, after), (results, mask, before, after)
