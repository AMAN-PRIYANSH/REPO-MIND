"""CP6 renderer maths on hand-computed examples: ranked-list metrics, paired differences, wording."""

from vulntrace.eval import agent_report as R


def test_list_metrics_hand_computed():
    assert R.list_metrics(["a", "b", "c"], {"b"}) == [0.0, 1.0, 0.5, 1.0]
    assert R.list_metrics(["b"], {"b"}) == [1.0, 1.0, 1.0, 1.0]
    assert R.list_metrics([], {"b"}) == [0.0, 0.0, 0.0, 0.0]               # abstention / invalid: a miss, unanswered
    assert R.list_metrics(["a", "c", "d", "b"], {"b"}) == [0.0, 0.0, 0.0, 1.0]   # only the first 3 count
    assert R.list_metrics(["a"], set()) == [0.0, 0.0, 0.0, 1.0]            # gold outside the candidates


def _cases(n):
    return [{"id": f"c{i}", "cluster_key": f"k{i}", "gold_ids": ["g"], "created": None, "n_candidates": 5,
             "gold_in_candidates": True, "a0_top3": []} for i in range(n)]


def test_paired_difference_and_reading():
    cases = _cases(40)
    lists = {"A0": [["x"]] * 40, "A2": [["g"]] * 40}
    d = R.paired(cases, lists, [True] * 40, "A2", "A0")
    assert d["mean"] == 1.0 and d["ci_low"] == 1.0 and d["n"] == 40
    lists = {"A0": [["g"]] * 20 + [["x"]] * 20, "A2": [["x"]] * 20 + [["g"]] * 20}
    d = R.paired(cases, lists, [True] * 40, "A2", "A0")
    assert d["mean"] == 0.0 and d["ci_low"] < 0 < d["ci_high"]
    assert R.verdict(d).startswith("no detectable difference")


def test_precision_at_1_counts_only_answered_cases():
    cases = _cases(4)
    assert R._prec1([["g"], ["x"], [], []], cases) == "0.500 (n=2)"
