"""D4 ceiling measurement on synthetic data (no Go, no network)."""

import math

from vulntrace.eval import lift_ceiling as lc
from vulntrace.eval import lift_prep as lp


def rr(candidates, status="AVAILABLE"):
    return {"status": status, "candidates": [
        {"candidate_id": cid, "package_dir": pd, "symbol": sym, "side": side} for cid, pd, sym, side in candidates]}


def case(core):
    return {"id": "X", "modules": [{"module": "m", "packages": [{"package": "m", "core_symbols": core, "derived_symbols": []}]}]}


def test_ceiling_case_is_name_level_and_needs_no_core_symbol_among_candidates():
    r = rr([("r1", "", "A", "BOTH"), ("r2", "", "T.B", "OLD")])
    assert lc.ceiling_case(case(["Z"]), r) is True
    assert lc.ceiling_case(case(["Z", "T.B"]), r) is False       # one core symbol is a candidate: not a ceiling case


def test_candidate_nodes_skip_new_only_and_out_of_module_candidates():
    r = rr([("r1", "", "A", "BOTH"), ("r2", "sub", "B", "OLD"), ("r3", "", "C", "NEW"), ("r4", "other", "D", "OLD")])
    assert lc.candidate_nodes(r, "ex.com/m", "") == {("ex.com/m", "A"): "r1", ("ex.com/m/sub", "B"): "r2", ("ex.com/m/other", "D"): "r4"}
    assert lc.candidate_nodes(r, "ex.com/m/sub", "sub") == {("ex.com/m/sub", "B"): "r2"}


def edge(pkg, sym, hop):
    return {"hop": hop, "other": {"package": pkg, "symbol": sym}, "caller": "x", "callee": "y",
            "call_site": {"file": "f.go", "line": 1}, "kind": "STATIC"}


def test_distances_take_the_smallest_hop_per_candidate_and_direction():
    nodes = {("m", "A"): "r1", ("m", "B"): "r2"}
    recs = {"callers": [{"edges": [edge("m", "A", 2), edge("m", "A", 1), edge("m", "other", 1)]}],
            "callees": [{"edges": [edge("m", "B", 2)]}]}
    assert lc.distances(recs, nodes) == {"callers": {"r1": 1}, "callees": {"r2": 2}}


def art_with(distances, status=lp.READY, errors=None, result="FOUND"):
    res = {"error": errors, "result": result, "edges": []}
    return {"prep": {"status": status, "reason": "why", "module_rel": "", "synthesized_go_mod": False},
            "neighbors": {"callers": [res], "callees": [res]}, "distances": {"m::Z": distances}}


def test_classify_hops_and_candidates_within():
    c = lc.classify(art_with({"callers": {"r1": 2}, "callees": {"r2": 1, "r3": 2}}))
    assert c["loaded"] and c["core_found"] and c["min_hops"] == 1
    assert c["min_hops_by_direction"] == {"callers": 2, "callees": 1}
    assert c["candidates_within"] == {"1": 1, "2": 3}
    none = lc.classify(art_with({"callers": {}, "callees": {}}))
    assert none["min_hops"] is None and none["candidates_within"] == {"1": 0, "2": 0}


def test_classify_failures_keep_their_reason():
    assert lc.classify(art_with({}, status=lp.NO_MODULE))["detail"] == "why"
    c = lc.classify(art_with({}, errors={"code": "LOAD_FAILED", "message": "boom"}, result="ERROR"))
    assert c["loaded"] is False and c["detail"].startswith("LOAD_FAILED: boom")
    c = lc.classify(art_with({}, errors={"code": "TARGET_NOT_FOUND", "message": "x"}, result="ERROR"))
    assert c["loaded"] is True and c["core_found"] is False


def row(min_hops, size="<=10", loaded=True, found=True, prep="READY"):
    return {"id": "x", "prep": prep, "loaded": loaded, "core_found": found, "synthesized_go_mod": False,
            "min_hops": min_hops, "min_hops_by_direction": {"callers": min_hops, "callees": None}, "size_bucket": size,
            "candidates_within": {"1": 1 if min_hops == 1 else 0, "2": 3 if min_hops else 0}, "failure": None if loaded and found else "LOAD_FAILED"}


def test_summarize_names_the_denominator_of_every_rate():
    rows = [row(1), row(2, ">100"), row(None), row(None, loaded=False, found=False)]
    s = lc.summarize(rows, n_all=10, n_nonavailable=2)
    assert s["ceiling_cases"] == 4 and s["loaded_with_core_found"] == 3
    assert s["within_1"] == {"count": 1, "of": 3, "rate": 1 / 3} and s["within_2"]["count"] == 2
    assert s["within_2_of_all_ceiling_cases"] == {"count": 2, "of": 4, "rate": 0.5}
    assert s["by_size"][">100"]["within_2"]["count"] == 1 and s["by_size"]["<=10"]["n"] == 2
    assert s["failure_counts"] == {"LOAD_FAILED": 1}
    assert s["by_direction"]["callees"]["within_2"]["count"] == 0
    empty = lc.summarize([], 1, 0)
    assert math.isnan(empty["within_1"]["rate"]) and empty["within_1"]["of"] == 0
