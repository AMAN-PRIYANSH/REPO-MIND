import pytest

from vulntrace.dataset.metrics import bootstrap_ci, per_case_scores, summarize


def test_exact_match():
    s = per_case_scores({"A", "B"}, {"A", "B"})
    assert s == {"predicted_count": 2, "gold_count": 2, "intersection": 2, "precision": 1.0, "recall": 1.0,
                "f1": 1.0, "exact_match": True, "any_hit": True, "abstained": False}


def test_partial_overlap_hand_computed():
    # predicted {A, B, C}, gold {A, D}: intersection {A}. precision 1/3, recall 1/2.
    s = per_case_scores({"A", "B", "C"}, {"A", "D"})
    assert s["precision"] == pytest.approx(1 / 3)
    assert s["recall"] == pytest.approx(1 / 2)
    assert s["f1"] == pytest.approx(2 * (1 / 3) * (1 / 2) / (1 / 3 + 1 / 2))
    assert not s["exact_match"] and s["any_hit"] and not s["abstained"]


def test_no_overlap_hand_computed():
    s = per_case_scores({"X"}, {"A"})
    assert s["precision"] == 0.0 and s["recall"] == 0.0 and s["f1"] == 0.0
    assert not s["any_hit"]


def test_abstention_has_no_precision_but_zero_recall():
    s = per_case_scores(set(), {"A"})
    assert s["predicted_count"] == 0
    assert s["precision"] is None
    assert s["recall"] == 0.0
    assert s["f1"] == 0.0
    assert s["abstained"]


def test_empty_gold_raises():
    with pytest.raises(ValueError):
        per_case_scores({"A"}, set())


def test_bootstrap_ci_degenerate_for_single_value():
    r = bootstrap_ci([0.5], seed=1)
    assert r == {"mean": 0.5, "ci_low": 0.5, "ci_high": 0.5, "n": 1}


def test_bootstrap_ci_empty():
    assert bootstrap_ci([], seed=1) == {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}


def test_bootstrap_ci_mean_matches_point_estimate():
    values = [0.0, 0.5, 1.0, 0.5]
    r = bootstrap_ci(values, seed=42)
    assert r["mean"] == pytest.approx(0.5)
    assert r["ci_low"] <= r["mean"] <= r["ci_high"]
    assert r["n"] == 4


def test_bootstrap_ci_is_deterministic_for_a_seed():
    values = [0.1, 0.9, 0.3, 0.7, 0.5, 0.2]
    a = bootstrap_ci(values, seed=7)
    b = bootstrap_ci(values, seed=7)
    assert a == b


def test_bootstrap_ci_constant_values_give_a_zero_width_interval():
    r = bootstrap_ci([0.5] * 10, seed=3)
    assert r["ci_low"] == r["ci_high"] == 0.5


def test_summarize_hand_computed():
    per_case = [
        per_case_scores({"A"}, {"A"}),          # exact match
        per_case_scores(set(), {"B"}),          # abstained
        per_case_scores({"C", "D"}, {"C"}),     # any-hit, not exact
    ]
    s = summarize(per_case, seed=1)
    assert s["n_cases"] == 3
    assert s["exact_match"] == {"count": 1, "rate": pytest.approx(1 / 3)}
    assert s["any_hit"] == {"count": 2, "rate": pytest.approx(2 / 3)}
    assert s["abstained"] == {"count": 1, "rate": pytest.approx(1 / 3)}
    assert s["precision_n_scored"] == 2  # the abstained case contributes no precision value
    assert s["recall"]["mean"] == pytest.approx((1.0 + 0.0 + 1.0) / 3)
