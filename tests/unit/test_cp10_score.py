"""CP10 deliverables 4-5: govulncheck scoring by stratum, verdict-level scores, the fixed headline,
sheet generation and validation (synthetic rows, no Go, no network)."""

import copy

from vulntrace.cp10 import report as rp
from vulntrace.cp10 import run as rn
from vulntrace.cp10 import score as sc
from vulntrace.cp10 import sheet as sh


def g(verdict, level):
    return {"verdict": verdict, "level": level, "symbols": [], "trace": None, "error": None}


def test_govulncheck_claim_depends_on_the_stratum():
    pkg = g("NOT_REACHABLE", "PACKAGE")
    assert rn.govulncheck_view(pkg, "S")["claim"] == "NOT_REACHABLE"
    assert rn.govulncheck_view(pkg, "N")["claim"] == "REACHABLE"
    assert rn.govulncheck_view(g("NOT_REACHABLE", "MODULE"), "N")["claim"] == "REACHABLE"
    assert rn.govulncheck_view(g("REACHABLE", "SYMBOL"), "S")["claim"] == "REACHABLE"
    na = rn.govulncheck_view(g("NOT_AFFECTED", "NONE"), "N")
    assert na["claim"] == "NOT_REACHABLE" and na["not_affected"] is True
    assert rn.govulncheck_view(g("ERROR", None), "S")["claim"] is None
    assert rn.govulncheck_view(None, "S") is None


def row(cid, stratum, hyg, leg, gclaim, app="github.com/a/app", evl="STATIC_PATH", hr=None, lr=None):
    r = {"id": cid, "app_repo": app, "app_tag": "v1", "advisory": "GO-X-" + cid, "module": "m", "stratum": stratum,
         "hygiene": {"verdict": hyg, "reason_codes": hr or ([] if hyg != "CANT_DETERMINE" else ["ANALYSIS_FAILED"]),
                     "evidence_level": evl if hyg == "REACHABLE" else "NO_ROUTE_SHOWN"},
         "legacy": {"verdict": leg, "reason_codes": lr or ([] if leg != "CANT_DETERMINE" else ["ANALYSIS_FAILED"])},
         "govulncheck": {"claim": gclaim, "level": "SYMBOL" if gclaim == "REACHABLE" else "PACKAGE"}}
    r["hygiene_changed"] = (hyg, r["hygiene"]["reason_codes"]) != (leg, r["legacy"]["reason_codes"])
    r["hygiene_made_not_reachable"] = hyg == "NOT_REACHABLE" and leg != "NOT_REACHABLE"
    return r


ROWS = [row("s1", "S", "REACHABLE", "REACHABLE", "REACHABLE"),
        row("s2", "S", "NOT_REACHABLE", "REACHABLE", "NOT_REACHABLE"),      # hygiene-induced NOT_REACHABLE in S
        row("s3", "S", "REACHABLE", "REACHABLE", "NOT_REACHABLE", evl="HAS_DYNAMIC_STEPS"),
        row("n1", "N", "NOT_REACHABLE", "NOT_REACHABLE", "REACHABLE", app="github.com/b/app"),
        row("n2", "N", "CANT_DETERMINE", "REACHABLE", "REACHABLE", app="github.com/b/app",
            hr=["ONLY_CONTEXT_TARGETS_REACHABLE"]),
        row("n3", "N", "REACHABLE", "REACHABLE", "REACHABLE", app="github.com/b/app")]
TRUTH = {"s1": "REACHABLE", "s2": "NOT_REACHABLE", "s3": "UNKNOWN", "n1": "REACHABLE", "n2": "NOT_REACHABLE",
         "n3": "REACHABLE"}


def test_tool_scores_and_false_not_reachable():
    s = sc.score_set(ROWS, TRUTH)
    h = s["ALL"]["tools"]["hygiene"]
    assert (h["reachable_precision"]["k"], h["reachable_precision"]["n"]) == (2, 2)    # s3 has UNKNOWN truth
    assert h["reachable_unknown_truth"] == 1
    assert h["false_not_reachable"] == {"count": 1, "ids": ["n1"], "truth_reachable_cases": 3,
                                        "rate": h["false_not_reachable"]["rate"]}
    assert h["cant_determine_ids"] == ["n2"]
    leg = s["ALL"]["tools"]["legacy"]
    assert (leg["reachable_precision"]["k"], leg["reachable_precision"]["n"]) == (2, 4)   # s1, n3 of s1, s2, n2, n3
    gv = s["ALL"]["tools"]["govulncheck"]
    assert (gv["reachable_precision"]["k"], gv["reachable_precision"]["n"]) == (3, 4)
    assert gv["false_not_reachable"]["count"] == 0
    assert s["S"]["unknown_truth"] == 1 and s["N"]["cases"] == 3


def test_paired_comparison_records_who_was_right():
    p = sc.score_set(ROWS, TRUTH)["ALL"]["paired"]["hygiene"]
    assert p["both_answered"] == 5 and p["agree"] == 3
    right = {d["id"]: d["right"] for d in p["disagree"]}
    assert right == {"s3": "unknown", "n1": "govulncheck"}
    assert [x["id"] for x in p["one_abstained"]] == ["n2"]


def test_hygiene_changes_list_every_induced_not_reachable_with_truth():
    ch = {c["id"]: c for c in sc.score_set(ROWS, TRUTH)["S"]["hygiene_changes"]}
    assert ch["s2"]["made_not_reachable"] is True and ch["s2"]["truth"] == "NOT_REACHABLE"
    assert ch["s2"]["hygiene_right"] is True and ch["s2"]["legacy_right"] is False


def test_path_precision_split_by_evidence_level():
    sheet = {r["id"]: {"path_judgement": j} for r, j in zip(ROWS, ["CORRECT", None, "INFEASIBLE_PATH", None, None,
                                                                    "INFEASIBLE_PATH"])}
    pp = sc.score_set(ROWS, TRUTH, sheet)["ALL"]["path_precision"]
    assert (pp["STATIC_PATH"]["precision"]["k"], pp["STATIC_PATH"]["precision"]["n"]) == (1, 2)
    assert (pp["HAS_DYNAMIC_STEPS"]["precision"]["k"], pp["HAS_DYNAMIC_STEPS"]["precision"]["n"]) == (0, 1)


def _doc():
    rows = [{**copy.deepcopy(r), "govulncheck_legacy_run": r["govulncheck"]} for r in ROWS]
    return {"rows": rows, "summary": rn.summary(rows)}


def _sheet(filled=True):
    items = [{"id": r["id"], "set": "d3c", "kind": "D3c case", "path_judgement_asked": r["hygiene"]["verdict"] == "REACHABLE"}
             for r in ROWS]
    s = sh.sheet_json(items)
    if filled:
        for c in s["cases"]:
            c.update(truth=TRUTH[c["id"]], by="test", filled=True, confidence="HIGH")
            if c["path_judgement_asked"]:
                c["path_judgement"] = "INFEASIBLE_PATH"
    return s


def test_validate_rejects_an_unfilled_or_incomplete_sheet():
    doc = _doc()
    assert sc.validate(_sheet(), doc) == []
    assert any("not filled" in e for e in sc.validate(_sheet(filled=False), doc))
    bad = _sheet()
    bad["cases"][0]["truth"] = "MAYBE"
    assert any("truth" in e for e in sc.validate(bad, doc))
    bad = _sheet()
    bad["cases"].pop()
    assert any("missing" in e for e in sc.validate(bad, doc))


def test_headline_is_the_fixed_template():
    doc = _doc()
    pending = rp.render(doc, None, _sheet(filled=False))
    assert rp.HEADLINE_PENDING in pending
    text = rp.render(doc, None, _sheet())
    head = rp.headline(sc.score_set(doc["rows"], TRUTH, {c["id"]: c for c in _sheet()["cases"]}), doc)
    assert head in text and head.startswith("On the held-out set D3c (2 real Go applications, 6 cases: 3 whose")
    assert "gave 1 false NOT_REACHABLE" in head and "1 of 6 cases have UNKNOWN truth" in head
    assert any(head.endswith(d) for d in rp.DIFFERENCE.values())
    assert rp.GOVULN_STATEMENT in text and "IN-SAMPLE" in text
    assert "## False NOT_REACHABLE (reported first)" in text
    assert text.index("False NOT_REACHABLE") < text.index("Verdict-level scores")


def test_case_row_marks_hygiene_changes():
    case = {"id": "c", "app_repo": "github.com/a/app", "app_tag": "v1", "advisory": "GO-1", "module": "m", "stratum": "S"}
    hyg = {"verdict": "NOT_REACHABLE", "reason_codes": [], "per_symbol": [], "mode": "FIX",
           "path_evidence": {"evidence_level": "NO_ROUTE_SHOWN"}, "target_policy": {"stratum": "S"}}
    leg = {"verdict": "REACHABLE", "reason_codes": [], "per_symbol": []}
    r = rn.case_row(case, None, {"govulncheck": g("REACHABLE", "SYMBOL")}, {"govulncheck": g("REACHABLE", "SYMBOL")}, hyg, leg)
    assert r["hygiene_changed"] and r["hygiene_made_not_reachable"] and r["govulncheck"]["claim"] == "REACHABLE"
    assert r == rn.case_row(case, None, {"govulncheck": g("REACHABLE", "SYMBOL")},
                            {"govulncheck": g("REACHABLE", "SYMBOL")}, hyg, leg)


def test_sheet_items_ask_for_the_route_only_on_reachable():
    items = sh.d3c_items({"rows": ROWS}, {}, {})
    asked = {i["id"]: i["path_judgement_asked"] for i in items}
    assert asked == {"s1": True, "s2": False, "s3": True, "n1": False, "n2": False, "n3": True}
    js = sh.sheet_json(items)
    assert all(c["truth"] is None and c["filled"] is False for c in js["cases"])
    assert all(("path_judgement" in c) == c["path_judgement_asked"] for c in js["cases"])


def test_truth_only_items_follow_the_rule():
    doc = {"rows": [row("d3a", "S", "REACHABLE", "REACHABLE", "REACHABLE"),
                    row("d3b", "S", "NOT_REACHABLE", "NOT_REACHABLE", "NOT_REACHABLE")]}
    d3 = sh.truth_only_items("d3", doc, {}, {"d3a": "REACHABLE", "d3b": "NOT_REACHABLE"}, {})
    d3b = sh.truth_only_items("d3b", doc, {}, {"d3a": "REACHABLE", "d3b": "NOT_REACHABLE"}, {})
    assert [i["id"] for i in d3] == ["d3a"] and [i["id"] for i in d3b] == ["d3b"]
    assert all(not i["path_judgement_asked"] for i in d3 + d3b)


def test_decision_targets_are_curated_symbols_in_stratum_s():
    vcase = {"modules": [{"module": "m", "packages": [{"package": "m/p", "core_symbols": ["F", "T.M"]}]}]}
    v = {"symbols": [{"package": "m/p", "symbol": "changed", "decides_verdict": True, "origin": "RANKED_CANDIDATE"}]}
    assert sh.decision_targets(v, vcase, "m", "S") == ["m/p.F", "m/p.T.M"]
    assert sh.decision_targets(v, vcase, "m", "N") == ["m/p.changed"]


def test_reproduction_compares_after_cp10_keys_are_removed_and_paths_sanitised(tmp_path, monkeypatch):
    import json

    path = {"entry": {"package": "m", "symbol": "main"}, "target": {"package": "l", "symbol": "F"},
            "edges": [{"caller": "m.main", "callee": "l.F", "kind": "DYNAMIC",
                       "call_site": {"file": "$GOMODCACHE/l@v1/f.go", "line": 3}}]}
    committed = {"verdict": "REACHABLE", "reason_codes": [], "verification": {"status": "PASSED"},
                 "per_symbol": [{"main_package": "m", "target": {"package": "l", "symbol": "F"}, "result": "REACHABLE",
                                 "reason_code": None, "methods": {}, "verified_path": path}]}
    (tmp_path / "c1.json").write_text(json.dumps(committed), encoding="utf-8")
    monkeypatch.setattr(rn, "committed_cp9_verdicts", lambda s: tmp_path)
    monkeypatch.setattr(rn, "REPO_ROOT", tmp_path.parent)
    mine = copy.deepcopy(committed)
    mine["per_symbol"][0]["verified_path"]["edges"][0].update(dynamic_kind="INTERFACE_METHOD")
    mine["per_symbol"][0]["shown_path"] = {"x": 1}
    mine["path_evidence"] = {"evidence_level": "HAS_DYNAMIC_STEPS"}
    local = copy.deepcopy(mine)
    local["per_symbol"][0]["verified_path"]["edges"][0]["call_site"]["file"] = "/root/gomod/l@v1/f.go"
    assert rn.reproduce_cp9("d3", {"c1": mine})["all_identical"] is True
    unsanitised = rn.reproduce_cp9("d3", {"c1": local})
    assert unsanitised["all_identical"] is False                     # the bug the sanitise step fixes
    fixed = rn.reproduce_cp9("d3", {"c1": local}, sanitise=lambda v: json.loads(
        json.dumps(v).replace("/root/gomod", "$GOMODCACHE")))
    assert fixed["all_identical"] is True
    changed = copy.deepcopy(mine)
    changed["per_symbol"][0]["result"] = "CANT_DETERMINE"
    assert rn.reproduce_cp9("d3", {"c1": changed})["different"]
