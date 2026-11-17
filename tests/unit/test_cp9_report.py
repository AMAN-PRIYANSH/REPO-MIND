"""CP9 results renderer: the D3b headline is fixed (committed before any D3b result) and nothing
about D3b precision is shown before the adjudication is filled."""

from vulntrace.eval import feasibility_report as fr

FIXED = ("On the held-out set D3b ({apps} real Go applications, {cases} cases), the path-feasibility filter "
         "downgraded {down} of {reach_off} REACHABLE verdicts to CANT_DETERMINE; adjudicated REACHABLE path "
         "precision was {prec_off} without the filter and {prec_on} with it, and {misses} of {down_adj} "
         "downgraded cases were judged reachable by some path (the filter's misses).")


def test_headline_template_is_the_fixed_one():
    assert fr.HEADLINE == FIXED


def rows():
    def r(i, app, off, on, down):
        return {"id": f"c{i}", "app_repo": app, "verdict_off": off, "verdict_on": on, "downgraded_by_filter": down}
    return [r(1, "a", "REACHABLE", "REACHABLE", False), r(2, "a", "REACHABLE", "CANT_DETERMINE", True),
            r(3, "b", "REACHABLE", "CANT_DETERMINE", True), r(4, "c", "NOT_REACHABLE", "NOT_REACHABLE", False)]


def test_pending_until_every_case_is_filled():
    assert fr.headline(fr.d3b_scores(rows(), None)) == fr.HEADLINE_PENDING
    sheet = {"cases": [{"id": "c1", "filled": True}, {"id": "c2", "filled": False}]}
    assert fr.d3b_scores(rows(), sheet) is None


def test_scores_from_a_filled_sheet():
    sheet = {"cases": [
        {"id": "c1", "filled": True, "adjudication_off": "INFEASIBLE_PATH", "adjudication_on": "CORRECT", "truth": "REACHABLE"},
        {"id": "c2", "filled": True, "adjudication_off": "INFEASIBLE_PATH", "adjudication_on": None, "truth": "REACHABLE"},
        {"id": "c3", "filled": True, "adjudication_off": "CORRECT", "adjudication_on": None, "truth": "NOT_REACHABLE"},
        {"id": "c4", "filled": True, "adjudication_off": None, "adjudication_on": None, "truth": "NOT_REACHABLE"}]}
    s = fr.d3b_scores(rows(), sheet)
    assert (s["apps"], s["cases"], s["down"], s["reach_off"], s["misses"], s["down_adj"]) == (3, 4, 2, 3, 1, 2)
    assert s["prec_off"].startswith("1/3 = 0.33") and s["prec_on"].startswith("1/1 = 1.00")
    assert fr.headline(s).startswith("On the held-out set D3b (3 real Go applications, 4 cases)")
