import numpy as np
import pytest

from vulntrace.eval import cp5_stats as st


def test_set_metrics_hand_computed():
    m = st.set_metrics({"a", "b", "c"}, {"a", "d"})
    assert (m["hits"], m["precision"], m["recall"]) == (1, pytest.approx(1 / 3), 0.5)
    assert m["f1"] == pytest.approx(2 * (1 / 3) * 0.5 / (1 / 3 + 0.5))
    assert m["any_hit"] and not m["exact"] and not m["abstain"]
    assert st.set_metrics({"a"}, {"a"})["exact"]


def test_empty_prediction_is_an_abstention_with_undefined_precision():
    m = st.set_metrics(set(), {"a"})
    assert m["precision"] is None and m["abstain"] and m["recall"] == 0 and m["f1"] == 0 and not m["any_hit"]
    assert st.to_vector(m)[0] == 0.0     # precision0
    assert st.answered_precision([m, st.set_metrics({"a", "b"}, {"a"})]) == (0.5, 1)


def test_empty_gold_can_never_be_hit_and_is_not_an_error():
    m = st.set_metrics({"a"}, set())
    assert not m["any_hit"] and not m["exact"] and m["recall"] == 0 and m["precision"] == 0


def test_group_summary_is_the_case_mean_and_deterministic():
    clusters = [f"k{i // 2}" for i in range(20)]      # 10 clusters of 2
    vals = np.array([[float(i % 3 == 0)] for i in range(20)])
    a, b = st.Group(clusters).summary(vals)[0], st.Group(clusters).summary(vals)[0]
    assert a == b and a["mean"] == pytest.approx(vals.mean()) and a["n"] == 20 and a["n_clusters"] == 10
    assert a["ci_low"] <= a["mean"] <= a["ci_high"]


def test_resampling_whole_clusters_widens_the_interval_compared_with_independent_cases():
    rng = np.random.default_rng(1)
    base = rng.integers(0, 2, 20).astype(float)
    vals = np.repeat(base, 5).reshape(-1, 1)           # 20 clusters of 5 identical cases
    wide = st.Group([f"k{i // 5}" for i in range(100)]).summary(vals)[0]
    narrow = st.Group([f"c{i}" for i in range(100)]).summary(vals)[0]
    assert wide["ci_high"] - wide["ci_low"] > narrow["ci_high"] - narrow["ci_low"]


def test_paired_difference_uses_the_same_draws_and_detects_a_consistent_gain():
    clusters = [f"k{i}" for i in range(60)]
    b = np.array([[float(i % 2)] for i in range(60)])
    a = np.minimum(b + (np.arange(60).reshape(-1, 1) % 4 == 0), 1.0)   # a >= b everywhere, strictly on 15 cases
    g = st.Group(clusters)
    d = g.paired(a, b)[0]
    assert d["mean"] == pytest.approx(15 / 60) and d["ci_low"] > 0
    same = g.paired(b, b)[0]
    assert same["mean"] == 0 and same["ci_low"] == 0 and same["ci_high"] == 0
    flip = g.paired(b, a)[0]
    assert flip["ci_high"] < 0 and flip["mean"] == pytest.approx(-d["mean"])


def test_single_cluster_and_empty_groups_do_not_crash():
    one = st.Group(["k", "k", "k"]).summary(np.array([[1.0], [0.0], [1.0]]))[0]
    assert one["ci_low"] == one["ci_high"] == one["mean"]
    empty = st.Group([]).summary(np.zeros((0, 2)))
    assert empty[0]["n"] == 0 and empty[0]["mean"] != empty[0]["mean"]    # NaN
    assert st.Group([]).paired(np.zeros((0, 1)), np.zeros((0, 1)))[0]["n"] == 0


def test_rate_ci():
    r = st.rate_ci(st.Group([f"k{i}" for i in range(10)]), [True] * 3 + [False] * 7)
    assert r["mean"] == pytest.approx(0.3)
