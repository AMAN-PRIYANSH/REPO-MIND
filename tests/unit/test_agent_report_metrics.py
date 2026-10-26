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


# --- headline wording (changed after the real run: a win over a mostly-abstaining A1 is not a win over retrieval) ---
def _pm(a0, a2, a1, n=40):
    cases = _cases(n)
    return {"cases": cases, "lists": {"A0": [a0] * n, "A2": [a2] * n, "A1": [a1] * n}, "head_mask": [True] * n}


def test_lead_does_not_call_a_win_over_a_weak_a1_a_win_over_retrieval():
    # A0 right, agent right, A1 abstains: the agent beats A1 only because A1 never answered.
    lead = R._lead({"m": _pm(["g"], ["g"], [])})
    assert "does not beat retrieval (A0)" in lead
    assert "beats the one-shot LLM (A1) in: A2 vs A1 (m)" in lead and "A1 answered 0% of cases for `m`" in lead
    assert "not a win over retrieval" in lead


def test_lead_names_a_win_over_a0_and_a_loss_to_a0():
    assert "An agent arm beats retrieval (A0) on any-hit@1: A2 (m)" in R._lead({"m": _pm(["x"], ["g"], ["x"])})
    lead = R._lead({"m": _pm(["g"], ["x"], ["g"])})
    assert "worse than A0 on any-hit@1 for: A2 (m)" in lead and "does not beat retrieval" in lead


def test_lead_warns_that_any_hit_3_is_not_like_for_like():
    assert "Agent answers list 1.0 IDs on average where A0 always lists 3" in R._lead({"m": _pm(["g", "a", "b"], ["g"], ["g"])})


def test_agreement_table_counts_gain_loss_and_lost_answers():
    def row(a0, ans, gold="g"):
        return {"stop_reason": "SUBMITTED" if ans else "LOOP_DETECTED", "answer": ans, "a0_top3": a0, "gold_ids": [gold]}
    rows = [row(["g"], ["g"]),             # same top-1
            row(["x"], ["g"]),             # changed, gain
            row(["g"], ["x"]),             # changed, loss
            row(["x"], ["y"]),             # changed, both wrong
            row(["g"], [])]                # no answer although A0 was right
    rows.append({**row(["g"], []), "stop_reason": "NOT_RUN"})   # not counted
    text = "\n".join(R.agreement_table({("A2", "m"): {"rows": rows}}))
    assert "| `m` | A2 | 4 of 5 | 1.00 | 4 / 0 / 0 | 1 | 3 | 1 | 1 | 1 |" in text
