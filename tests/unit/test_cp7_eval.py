"""CP7 evaluation helpers and the results renderer (no Go, no network)."""

import json

from tests.unit.cp7_support import GOOD_PATH, FakeMethod
from vulntrace.eval import triage_eval as te
from vulntrace.eval import triage_report as tr


def test_wilson():
    w = te.wilson(0, 0)
    assert w["n"] == 0 and w["rate"] == 0.0
    w = te.wilson(5, 10)
    assert w["rate"] == 0.5 and 0.23 < w["ci_low"] < 0.24 and 0.76 < w["ci_high"] < 0.77
    assert te.wilson(0, 30)["ci_high"] > 0.1      # zero events in 30 still leave a wide upper bound


def _fx(false_nr=0):
    rows = [{"mode": "RELEASE", "truth": "REACHABLE", "pre_policy_verdict": "REACHABLE"}]
    rows += [{"mode": "RELEASE", "truth": "REACHABLE", "pre_policy_verdict": "NOT_REACHABLE"}] * false_nr
    return rows


def _d4(n_nr, unsupported=0, contradicted=0):
    rows = []
    for i in range(n_nr):
        rows.append({"id": f"c{i}", "cluster_key": f"k{i}", "pre_policy_verdict": "NOT_REACHABLE",
                     "gold_analysed": i >= unsupported,
                     "reference": {"verdict": "REACHABLE" if i < contradicted else "NOT_REACHABLE"}})
    return rows


def test_policy_rule():
    assert te.decide_mode2_policy(_fx(), None)["decision"] == "DOWNGRADE"
    assert te.decide_mode2_policy(_fx(), _d4(5))["decision"] == "DOWNGRADE"              # too few
    assert te.decide_mode2_policy(_fx(), _d4(200))["decision"] == "KEEP"                 # 0/200: upper bound < 0.05
    assert te.decide_mode2_policy(_fx(), _d4(200, unsupported=20))["decision"] == "DOWNGRADE"
    assert te.decide_mode2_policy(_fx(), _d4(200, contradicted=1))["decision"] == "DOWNGRADE"
    assert te.decide_mode2_policy(_fx(false_nr=1), _d4(200))["decision"] == "DOWNGRADE"
    assert "Wilson" in te.decide_mode2_policy(_fx(), None)["rule"]


def test_memo_method_asks_once_with_extras():
    fake = FakeMethod("vta")
    memo = te.MemoMethod(fake, extras=[{"package": "p", "symbol": "Extra"}])
    a = memo("/app", "m", [{"package": "p", "symbol": "F"}])
    b = memo("/app", "m", [{"package": "p", "symbol": "Extra"}, {"package": "p", "symbol": "F"}])
    assert len(fake.calls) == 1 and fake.calls[0][1] == [{"package": "p", "symbol": "F"}, {"package": "p", "symbol": "Extra"}]
    assert [r["target"]["symbol"] for r in a] == ["F"] and [r["target"]["symbol"] for r in b] == ["Extra", "F"]
    memo("/app", "other-main", [{"package": "p", "symbol": "F"}])
    assert len(fake.calls) == 2


def test_corruptions_change_the_path():
    two = json.loads(json.dumps(GOOD_PATH))
    two["edges"].append(dict(two["edges"][0], caller=two["edges"][0]["callee"], callee="x.Y"))
    out = te.corrupt_paths(two)
    assert set(out) == {"WRONG_LINE", "EDGE_NOT_IN_GRAPH", "BROKEN_CHAIN"}
    assert all(p != two for p in out.values())


def test_confusion_and_seconds():
    rows = [{"truth": "REACHABLE", "verdict": "REACHABLE"}, {"truth": "REACHABLE", "verdict": "NOT_REACHABLE"},
            {"truth": "NOT_REACHABLE", "verdict": "CANT_DETERMINE"}, {"truth": "NOT_REACHABLE", "verdict": "REACHABLE"}]
    c = te.confusion(rows)
    assert (c["false_not_reachable"], c["false_reachable"], c["cant_determine"]) == (1, 1, 1)
    assert c["accuracy"]["k"] == 1 and c["coverage"]["k"] == 3 and c["reachable_precision"]["n"] == 2
    assert te.seconds_summary([1.0, None, 3.0])["p50"] in (1.0, 3.0) and te.seconds_summary([])["n"] == 0


def test_example_verdict_strips_local_paths(tmp_path):
    from vulntrace.paths import REPO_ROOT

    out = te.example_verdict({"a": f"{REPO_ROOT}/data/x", "b": [str(tmp_path)]})
    assert "<local>" in out["a"] and str(REPO_ROOT) not in json.dumps(out)


def test_headline_is_fixed():
    """Fixed before any CP7 result existed (CP6 review note 5); changing it needs a disclosed reason."""
    assert tr.HEADLINE == (
        "CP7 runs the whole triage pipeline (two reachability methods, the rule table, the evidence verifier "
        "and the Mode 2 policy) on the 22 synthetic fixtures in three modes, where the truth is known, and on "
        "D1/D4 real modules analysed as their own application, where it is not: the fixture tables measure "
        "accuracy, the D1/D4 tables only measure verdict distributions, coverage and why the system abstains.")


def test_renderer_handles_missing_files(tmp_path):
    text = tr.render_cp7_doc(tmp_path, "docs/results/cp7")
    assert tr.HEADLINE in text and "Not run" in text and "Decision: DOWNGRADE" in text
