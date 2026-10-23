"""Scoring of the lifting evaluation on synthetic per-case artifacts (no Go, no network)."""

import math

import pytest

from vulntrace.eval import lift_eval as le
from vulntrace.eval import lift_prep as lp


def rec(pkg, sym, status, nearest=(), all_=None, error=None):
    all_ = nearest if all_ is None else all_
    ent = lambda names: [{"package": pkg, "symbol": n, "depth": 1, "dynamic": False, "path": {}} for n in names]  # noqa: E731
    return {"target": {"package": pkg, "symbol": sym}, "status": status, "error": error,
            "rules": {"NEAREST": {"entries": ent(nearest), "depth_limit_reached": False},
                      "ALL": {"entries": ent(all_), "depth_limit_reached": False}}}


def art(case_id, seeds, records, prep=None):
    prep = prep or {"status": lp.READY, "reason": None, "module_rel": "", "synthesized_go_mod": False}
    return {"case_id": case_id, "seconds": 1.0, "modules": [{"module": "m", "prep": prep, "seeds": seeds, "records": records}]}


def seed(sym, origin="CORE", pkg="m"):
    return {"package": pkg, "symbol": sym, "origin": origin}


def case(cid, core, derived, commits=("a",)):
    return {"id": cid, "created": "2024-01-01", "fix_commits": [{"host": "h", "owner": "o", "repo": "r", "sha": c} for c in commits],
            "modules": [{"module": "m", "packages": [{"package": "m", "core_symbols": core, "derived_symbols": derived}]}]}


def test_import_path_for():
    f = le.import_path_for
    assert f("ex.com/m", "", "") == "ex.com/m"
    assert f("ex.com/m", "", "a/b") == "ex.com/m/a/b"
    assert f("ex.com/m/v2", "v2", "v2/x") == "ex.com/m/v2/x"
    assert f("ex.com/m/sub", "sub", "other") is None            # outside the module
    assert f("ex.com/m/sub", "sub", "sub") == "ex.com/m/sub"


def test_selected_seeds_map_candidates_into_the_module_and_skip_the_rest():
    ev = {"candidates": [{"candidate_id": "c1", "package_dir": "pkg", "symbol": "F"},
                         {"candidate_id": "c2", "package_dir": "elsewhere", "symbol": "G"},
                         {"candidate_id": "c3", "package_dir": "", "symbol": "T.M"}]}
    got = le.selected_seeds(ev, ["c1", "c2", "c3", "c9"], "ex.com/m", "", "E1:x")
    assert got == [{"package": "ex.com/m/pkg", "symbol": "F", "origin": "E1:x"},
                   {"package": "ex.com/m/elsewhere", "symbol": "G", "origin": "E1:x"},
                   {"package": "ex.com/m", "symbol": "T.M", "origin": "E1:x"}]
    sub = le.selected_seeds(ev, ["c1", "c3"], "ex.com/m/pkg", "pkg", "E1:x")
    assert sub == [{"package": "ex.com/m/pkg", "symbol": "F", "origin": "E1:x"}]


def test_dedupe_keeps_the_first_origin():
    s = le.dedupe([seed("A"), seed("A", "E1:x"), seed("B")])
    assert [(x["symbol"], x["origin"]) for x in s] == [("A", "CORE"), ("B", "CORE")]


def test_case_outcome_success_and_each_failure_category():
    ok = art("c", [seed("p")], [rec("m", "p", "LIFTED", ["P"])])
    assert le.case_outcome(ok)["success"] is True
    self_ = art("c", [seed("P")], [rec("m", "P", "ALREADY_EXPORTED", ["P"])])
    assert le.case_outcome(self_)["success"] is True
    root = art("c", [seed("p")], [rec("m", "p", "ROOT_ONLY")])
    o = le.case_outcome(root)
    assert (o["success"], o["failure"], o["module_loaded"]) == (False, le.F_ROOT_ONLY, True)
    load = art("c", [seed("p")], [rec("m", "p", "ERROR", error={"code": "LOAD_FAILED", "message": "boom"})])
    o = le.case_outcome(load)
    assert (o["failure"], o["module_loaded"]) == (le.F_LOAD, False) and "LOAD_FAILED: boom" in o["detail"]
    timeout = art("c", [seed("p")], [rec("m", "p", "ERROR", error={"code": "TIMEOUT", "message": "slow"})])
    assert le.case_outcome(timeout)["failure"] == le.F_TIMEOUT
    notfound = art("c", [seed("p")], [rec("m", "p", "ERROR", error={"code": "TARGET_NOT_FOUND", "message": "x"})])
    assert le.case_outcome(notfound)["failure"] == le.F_SEED_ERROR
    for status, failure in ((lp.NO_SOURCE, le.F_NO_SOURCE), (lp.NO_MODULE, le.F_NO_MODULE), (lp.PREP_FAILED, le.F_PREP)):
        a = art("c", [], [], prep={"status": status, "reason": "why", "module_rel": None})
        o = le.case_outcome(a)
        assert (o["success"], o["failure"], o["detail"]) == (False, failure, "why")


def test_lifted_set_uses_only_the_requested_origin():
    a = art("c", [seed("p"), seed("q", "E1:llama")],
            [rec("m", "p", "LIFTED", ["P"], ["P", "Top"]), rec("m", "q", "LIFTED", ["Q"]), rec("m", "x", "ROOT_ONLY")])
    assert le.lifted_set(a, "NEAREST", "CORE") == {"P"}
    assert le.lifted_set(a, "ALL", "CORE") == {"P", "Top"}
    assert le.lifted_set(a, "NEAREST", "E1:llama") == {"Q"}
    assert le.lifted_set(a, "ALL", "CORE", exclude={"Top"}) == {"P"}


def test_score_cases_keeps_failed_cases_and_scores_two_views():
    cases = {"A": case("A", ["a"], ["Ax", "Ay"]), "B": case("B", ["b"], ["Bx"]), "C": case("C", ["c"], []),
             "D": case("D", ["d"], ["Dx"])}
    arts = {
        "A": art("A", [seed("a")], [rec("m", "a", "LIFTED", ["Ax"], ["Ax", "Ay", "Top"])]),
        "B": art("B", [seed("b")], [rec("m", "b", "ALREADY_EXPORTED", ["b"])]),       # lifts to itself: nothing new
        "D": art("D", [], [], prep={"status": lp.NO_MODULE, "reason": "no go.mod", "module_rel": None}),
    }
    entries = [{"id": i, "status": "AVAILABLE"} for i in "ABCD"]
    rows = le.score_cases(cases, entries, arts)
    assert [r["id"] for r in rows] == ["A", "B", "D"]                  # C has no derived symbols: out of the population
    a, b, d = rows
    m = a["metrics"]["NEAREST"]["literal"]
    assert (m["precision"], m["recall"]) == (1.0, 0.5)
    m = a["metrics"]["ALL"]["literal"]
    assert m["hits"] == 2 and m["predicted"] == 3 and m["recall"] == 1.0 and m["precision"] == pytest.approx(2 / 3)
    assert b["metrics"]["NEAREST"]["literal"]["precision"] == 0.0 and b["metrics"]["NEAREST"]["literal"]["predicted"] == 1
    assert b["metrics"]["NEAREST"]["new_only"]["predicted"] == 0 and b["metrics"]["NEAREST"]["new_only"]["precision"] is None
    assert d["outcome"]["failure"] == le.F_NO_MODULE and d["metrics"]["ALL"]["literal"]["recall"] == 0.0   # counted, recall 0


def test_summary_coverage_counts_and_failure_reasons():
    cases = {i: case(i, [i.lower()], [i + "x"]) for i in "ABCD"}
    arts = {"A": art("A", [seed("a")], [rec("m", "a", "LIFTED", ["Ax"])]),
            "B": art("B", [seed("b")], [rec("m", "b", "ROOT_ONLY")]),
            "C": art("C", [], [], prep={"status": lp.PREP_FAILED, "reason": "go.mod requires go >= 1.99", "module_rel": ""})}
    rows = le.score_cases(cases, [{"id": i, "status": "AVAILABLE"} for i in "ABCD"], arts)
    s = le.summarize_lifting(rows)
    assert s["cases_with_derived"] == 4 and s["lifted_ok"] == 1 and s["module_loaded"] == 2
    assert s["coverage"] == {"lifted_ok": 1, "of": 4, "rate": 0.25}
    assert s["failure_counts"] == {"NOT_RUN": 1, "PREP_FAILED": 1, "ROOT_ONLY": 1}
    assert s["failure_detail"]["PREP_FAILED"][0]["detail"] == "go.mod requires go >= 1.99"
    near = s["rules"]["NEAREST"]["literal"]
    assert near["on_lifted"]["n"] == 1 and near["on_lifted"]["recall"]["mean"] == 1.0
    assert near["all_attempted"]["n"] == 4 and near["all_attempted"]["recall"]["mean"] == 0.25    # failures count as recall 0
    assert math.isnan(s["rules"]["ALL"]["lifted_set_size"]["mean"]) is False


def test_all_minus_nearest_is_paired_over_lifted_cases():
    cases = {"A": case("A", ["a"], ["Ax", "Top"]), "B": case("B", ["b"], ["Bx"])}
    arts = {"A": art("A", [seed("a")], [rec("m", "a", "LIFTED", ["Ax"], ["Ax", "Top"])]),
            "B": art("B", [seed("b")], [rec("m", "b", "LIFTED", ["Bx"])])}
    s = le.summarize_lifting(le.score_cases(cases, [{"id": i, "status": "AVAILABLE"} for i in "AB"], arts))
    d = s["all_minus_nearest"]
    assert d["n"] == 2 and d["recall"]["mean"] == pytest.approx(0.25)


def test_e1_plus_l_sets_replace_add_and_failed_lifts():
    a = art("c", [seed("p", "E1:x"), seed("q", "E1:x"), seed("r", "E1:x")],
            [rec("m", "p", "LIFTED", ["P"], ["P", "Top"]), rec("m", "q", "ROOT_ONLY"), rec("m", "r", "ALREADY_EXPORTED", ["r"])])
    sel = [("m", "p"), ("m", "q"), ("m", "r")]
    got = le.e1_plus_l_sets(a, "x", sel)
    assert got["replace/NEAREST"] == {"P", "q", "r"}              # p replaced; q stays (origin ROOT_ONLY); r lifts to itself
    assert got["replace/ALL"] == {"P", "Top", "q", "r"}
    assert got["add/NEAREST"] == {"p", "P", "q", "r"}
    assert got["add/ALL"] == {"p", "P", "Top", "q", "r"}
    nothing = le.e1_plus_l_sets(None, "x", sel)
    assert nothing["replace/ALL"] == {"p", "q", "r"} == nothing["add/NEAREST"]   # no artefact: identical to E1


def _e1_doc(rows):
    return {"model": {"alias": "x", "cutoff": None}, "rows": rows}


def _e1_row(cid, selected, n_cand, case_, ev, status="VALID"):
    names = [c["symbol"] for c in ev["candidates"] if c["candidate_id"] in selected]
    from vulntrace.dataset import baselines
    from vulntrace.eval import cp5_stats as st
    core, der = baselines.core_symbols(case_), baselines.core_and_derived_symbols(case_)
    e0 = baselines.e0_predict(ev)
    return {"id": cid, "cluster_key": cid, "created": "2024-01-01", "n_candidates": n_cand,
            "llm": {"status": status, "selected": selected},
            "m": {"llm": {"core": st.set_metrics(names, core), "core_derived": st.set_metrics(names, der)},
                  "e0": {"core": st.set_metrics(e0, core), "core_derived": st.set_metrics(e0, der)}}}


def test_e1_plus_l_rows_reproduce_the_committed_e1_and_skip_what_cannot_be_mapped():
    c1, c2, c3 = case("A", ["p"], ["P"]), case("B", ["z"], []), case("C", ["k"], [])
    ev = lambda cid, syms: {"status": "AVAILABLE", "case_id": cid, "candidates": [  # noqa: E731
        {"candidate_id": f"c{i + 1}", "package_dir": "", "symbol": s} for i, s in enumerate(syms)]}
    evidence = {"A": ev("A", ["p", "o"]), "B": ev("B", ["z"]), "C": ev("C", ["k", "k2"])}
    doc = _e1_doc([_e1_row("A", ["c1"], 2, c1, evidence["A"]), _e1_row("B", ["c1"], 5, c2, evidence["B"]),   # 5 != 1 candidates
                   _e1_row("C", [], 2, c3, evidence["C"], status="VALID")])
    arts = {"A": art("A", [seed("p", "E1:x", pkg="m")], [rec("m", "p", "LIFTED", ["P"])])}
    rows, skipped = le.e1_plus_l_rows(["A", "B", "C"], {"A": c1, "B": c2, "C": c3}, evidence, doc, arts)
    assert skipped == {"evidence_changed_since_cp5": 1}
    by = {r["id"]: r for r in rows}
    assert set(by) == {"A", "C"} and by["A"]["lifting_applied"] is True and by["A"]["changed"] is True
    assert by["A"]["sets"]["e1"] == ["p"] and by["A"]["sets"]["replace/NEAREST"] == ["P"]
    assert by["C"]["lifting_applied"] is False and by["C"]["sets"]["replace/ALL"] == by["C"]["sets"]["e1"] == []
    assert (by["A"]["reason"], by["C"]["reason"]) == ("APPLIED", "NO_SELECTION")
    m = le.row_metrics(by["A"])["core_derived"]
    assert m["replace/NEAREST"]["recall"] == 0.5 and m["e1"]["recall"] == 0.5 and m["add/NEAREST"]["recall"] == 1.0


def test_summarize_e1_plus_l_pairs_every_variant_with_e1_and_e0():
    from vulntrace.eval.llm_report import group_defs

    c = case("A", ["p"], ["P"])
    ev = {"status": "AVAILABLE", "case_id": "A", "candidates": [{"candidate_id": "c1", "package_dir": "", "symbol": "p"},
                                                                 {"candidate_id": "c2", "package_dir": "", "symbol": "o"}]}
    rows = []
    for i in range(3):
        cid = f"A{i}"
        cc = {**c, "id": cid}
        e = {**ev, "case_id": cid}
        r = _e1_row(cid, ["c1"], 2, cc, e)
        r["cluster_key"] = cid
        a = art(cid, [seed("p", "E1:x")], [rec("m", "p", "LIFTED", ["P"])])
        out, _ = le.e1_plus_l_rows([cid], {cid: cc}, {cid: e}, _e1_doc([r]), {cid: a})
        rows += out
    s = le.summarize_e1_plus_l(rows, None, group_defs)
    allg = s["all"]
    assert allg["n"] == 3 and allg["lifting_applied"] == 3 and allg["selection_changed"] == 3
    assert allg["reasons"] == {"APPLIED": 3}
    d = allg["core_derived"]["paired_vs_e1"]["add/NEAREST"]["recall"]
    assert d["mean"] == pytest.approx(0.5) and d["n"] == 3
    assert set(allg["core_derived"]["paired_vs_e0"]) == {"replace/NEAREST", "replace/ALL", "add/NEAREST", "add/ALL"}
    assert "applied_only" in allg["core_derived"]


def test_worked_examples_pick_by_id_order_not_by_outcome():
    cases = {i: case(i, [i.lower()], [i + "x"]) for i in "ABC"}
    arts = {"A": art("A", [seed("a")], [rec("m", "a", "LIFTED", ["Ax"])]),
            "B": art("B", [seed("b")], [rec("m", "b", "LIFTED", ["Other"])]),
            "C": art("C", [seed("c")], [rec("m", "c", "LIFTED", ["Cx"])])}
    rows = le.score_cases(cases, [{"id": i, "status": "AVAILABLE"} for i in "ABC"], arts)
    ex = le.worked_examples(rows, limit=1)
    assert [e["id"] for e in ex["exact"]] == ["A"] and [e["id"] for e in ex["different"]] == ["B"]


def test_ensure_parent_refetches_and_reports_a_fetch_error_as_one_line(tmp_path, monkeypatch):
    from vulntrace.dataset import git_fetch

    fc = {"host": "h", "owner": "o", "repo": "r", "sha": "a" * 40}
    calls = []
    monkeypatch.setattr(git_fetch, "parent_sha", lambda repo_dir, sha, runner=None: "b" * 40)
    repo, parent, err = le.ensure_parent(fc, tmp_path, fetch=lambda *a, **k: calls.append((a, k)))
    assert parent == "b" * 40 and err is None and len(calls) == 1 and calls[0][0][3] == "a" * 40   # fetched again, not trusted

    def failing(*a, **k):
        raise git_fetch.GitFetchError("FETCH_FAILED", "fatal: could not read\nmore detail")

    _, parent, err = le.ensure_parent(fc, tmp_path, fetch=failing)
    assert parent is None and err == "FETCH_FAILED: fatal: could not read"
    monkeypatch.setattr(git_fetch, "parent_sha", lambda repo_dir, sha, runner=None: None)
    _, parent, err = le.ensure_parent(fc, tmp_path, fetch=lambda *a, **k: None)
    assert parent is None and "no parent" in err


def test_all_load_failed_needs_every_record_to_fail_to_load():
    bad = rec("m", "p", "ERROR", error={"code": "LOAD_FAILED", "message": "err: go: inconsistent vendoring in /x"})
    nf = rec("m", "q", "ERROR", error={"code": "TARGET_NOT_FOUND", "message": "x"})
    assert le._all_load_failed([bad, bad]) is True
    assert le._all_load_failed([bad, nf]) is False
    assert le._all_load_failed([]) is False
    assert le._all_load_failed([rec("m", "p", "LIFTED", ["P"])]) is False


def test_a_failed_case_is_reported_by_its_furthest_progress():
    """GO-2024-3005 had a module that loaded (seeds not found) and a sibling with no go.mod; the sibling must not win."""
    loaded = {"module": "m", "prep": {"status": lp.READY, "reason": None, "module_rel": ""}, "seeds": [seed("p")],
              "records": [rec("m", "p", "ERROR", error={"code": "PACKAGE_NOT_LOADED", "message": "x"})]}
    nomod = {"module": "n", "prep": {"status": lp.NO_MODULE, "reason": "no go.mod", "module_rel": None}, "seeds": [], "records": []}
    o = le.case_outcome({"modules": [nomod, loaded]})
    assert (o["success"], o["failure"], o["module_loaded"]) == (False, le.F_SEED_ERROR, True)
    root = {**loaded, "records": [rec("m", "p", "ROOT_ONLY")]}
    assert le.case_outcome({"modules": [nomod, root]})["failure"] == le.F_ROOT_ONLY
    broken = {"module": "b", "prep": {"status": lp.READY, "reason": None, "module_rel": ""}, "seeds": [seed("p")],
              "records": [rec("m", "p", "ERROR", error={"code": "BAD_RESPONSE", "message": "exit -9"})]}
    o = le.case_outcome({"modules": [nomod, broken]})
    assert o["failure"] == le.F_LOAD and "exit -9" in o["detail"]
    ok = le.case_outcome({"modules": [nomod, {**loaded, "records": [rec("m", "p", "LIFTED", ["P"])]}]})
    assert ok["success"] and ok["failure"] is None


def test_attach_metrics_reproduces_score_cases_and_slim_rows_drop_only_the_metrics():
    cases = {"A": case("A", ["a"], ["Ax", "Ay"])}
    arts = {"A": art("A", [seed("a")], [rec("m", "a", "LIFTED", ["Ax"], ["Ax", "Top"])])}
    rows = le.score_cases(cases, [{"id": "A", "status": "AVAILABLE"}], arts)
    slim = le.slim_rows(rows)
    assert "metrics" not in slim[0] and set(rows[0]) - set(slim[0]) == {"metrics"}
    assert le.attach_metrics(dict(slim[0]))["metrics"] == rows[0]["metrics"]


def test_applied_reason_buckets():
    f = le._applied_reason
    ready = {"status": lp.READY, "reason": None, "module_rel": ""}
    ok = rec("m", "p", "LIFTED", ["P"])
    boom = rec("m", "p", "ERROR", error={"code": "LOAD_FAILED", "message": "x"})
    root = rec("m", "p", "ROOT_ONLY")
    assert f(None, [], [], False) == "NO_SELECTION"
    assert f(None, ["p"], [], False) == "NO_MODULE"
    assert f(art("c", [], [], prep={"status": lp.PREP_FAILED, "reason": "x", "module_rel": ""}), ["p"], [], False) == "NO_MODULE"
    assert f(art("c", [seed("p", "E1:x")], [boom], prep=ready), ["p"], [("m", "p")], False) == "LOAD_FAILED"
    assert f(art("c", [seed("q")], [root], prep=ready), ["p"], [], False) == "SELECTED_OUTSIDE_MODULE"
    assert f(art("c", [seed("p", "E1:x")], [root], prep=ready), ["p"], [("m", "p")], False) == "NOTHING_LIFTED"
    assert f(art("c", [seed("p", "E1:x")], [ok], prep=ready), ["p"], [("m", "p")], True) == "APPLIED"
