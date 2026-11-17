"""CP9 D3b sheets: which cases, what is pre-filled by code, escaping, validation."""

import copy

from tests.unit.cp7_support import MAIN_PKG, TARGET, path
from vulntrace.eval import feasibility_sheet as fsh

P = path(MAIN_PKG, TARGET, [("example.com/lib.Parse", "cmd/a/main.go", 4)])
Q = path(MAIN_PKG, TARGET, [("example.com/app/cmd/a.mid", "cmd/a/main.go", 5), ("example.com/lib.Parse", "cmd/a/main.go", 9)])


def verdict(result, vp=None, feas=None, pre=None):
    e = {"target": dict(TARGET), "result": result, "verified_path": vp, "main_package": MAIN_PKG, "decides_verdict": True}
    if feas is not None:
        e["feasibility"] = feas
    if pre:
        e["pre_feasibility_result"] = pre
    return {"per_symbol": [e]}


def row(i, off, on, down=False):
    return {"id": f"c{i}", "app_repo": "github.com/o/app", "app_tag": "v1.0.0", "app_commit": "abc", "advisory": "GO-1",
            "module": "example.com/lib", "version_selected": "v1", "mode": "FIX", "verdict_off": off, "verdict_on": on,
            "reason_codes_on": [] if on != "CANT_DETERMINE" else ["PATHS_INFEASIBLE"], "downgraded_by_filter": down,
            "filter_statuses": {}}


def test_cases_and_prefill():
    rows = [row(1, "REACHABLE", "REACHABLE"), row(2, "REACHABLE", "REACHABLE"), row(3, "REACHABLE", "CANT_DETERMINE", True),
            row(4, "NOT_REACHABLE", "NOT_REACHABLE")]
    off = {"c1": verdict("REACHABLE", P), "c2": verdict("REACHABLE", P), "c3": verdict("REACHABLE", P)}
    on = {"c1": verdict("REACHABLE", P), "c2": verdict("REACHABLE", Q), "c3": verdict("CANT_DETERMINE")}
    cases = {c["id"]: c for c in fsh.sheet_cases(rows, off, on)}
    assert set(cases) == {"c1", "c2", "c3"}, "every case REACHABLE in either run, nothing else"
    assert cases["c1"]["adjudication_on"] == "SAME_AS_OFF" and "prefilled" in cases["c1"]
    assert cases["c2"]["adjudication_on"] is None and cases["c3"]["adjudication_on"] is None
    assert all(c["adjudication_off"] is None and c["truth"] is None and not c["filled"] for c in cases.values())


def test_markdown_escapes_and_shows_steps():
    st = {"pattern": "F2", "edge_index": 0, "edge": P["edges"][0], "context_edges": [],
          "reason": "the call at x runs only if `port == 0` | <script>"}
    on = verdict("CANT_DETERMINE", feas={"status": "INFEASIBLE", "examined": [{"length": 1, "first_infeasible": st}]},
                 pre="REACHABLE")
    text = fsh.case_markdown(row(3, "REACHABLE", "CANT_DETERMINE", True), verdict("REACHABLE", P), on, {}, None, "s|<b>")
    assert "Infeasible steps reported by the filter" in text and "pattern F2" in text
    assert "<script>" not in text and "<b>" not in text
    assert "| steps_correct | |" in text and "| adjudication_on | |" not in text


def test_validate():
    c = {"id": "c1", "verdict_on": "REACHABLE", "downgraded_by_filter": False, "filled": True,
         "adjudication_off": "INFEASIBLE_PATH", "adjudication_on": "SAME_AS_OFF", "truth": "REACHABLE", "by": "supervisor"}
    assert fsh.validate({"cases": [c]}) == []
    bad = copy.deepcopy(c)
    bad["truth"] = None
    assert fsh.validate({"cases": [bad]})
    d = dict(c, verdict_on="CANT_DETERMINE", downgraded_by_filter=True, steps_correct=None)
    assert fsh.validate({"cases": [d]}), "a downgraded case needs steps_correct"
