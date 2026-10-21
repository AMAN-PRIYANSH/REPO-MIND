"""Cluster bootstrap (CP3 finding 1), undated date bucket (finding 2) - CP4 tasks 0b/0c."""

import pytest

from vulntrace.dataset import datasets, metrics


def test_cluster_bootstrap_point_estimate_is_case_weighted_mean():
    r = metrics.cluster_bootstrap_ci([1, 1, 1, 0], ["a", "a", "a", "b"], seed=1)
    assert r["mean"] == pytest.approx(0.75)  # case mean, not cluster mean (0.5)
    assert r["n"] == 4 and r["n_clusters"] == 2


def test_cluster_bootstrap_resamples_clusters_not_cases():
    """Two clusters only: every resample draws (a,a), (a,b), (b,a) or (b,b), so the only
    possible resample means are 1.0, 0.75 and 0.0 - a case bootstrap would also produce
    0.25 and 0.5."""
    values, clusters = [1, 1, 1, 0], ["a", "a", "a", "b"]
    for seed in range(20):
        r = metrics.cluster_bootstrap_ci(values, clusters, seed=seed, n_resamples=200)
        assert r["ci_low"] in (0.0, 0.75, 1.0) and r["ci_high"] in (0.0, 0.75, 1.0)
        c = metrics.bootstrap_ci([float(v) for v in values], seed=seed, n_resamples=200)
        if c["ci_low"] not in (0.0, 0.75, 1.0):
            break
    else:
        raise AssertionError("case bootstrap never produced a value outside {0, .75, 1}; test is not discriminating")


def test_cluster_bootstrap_is_deterministic_and_order_independent():
    values = [0, 1, 1, 0, 1, 0, 1, 1]
    clusters = ["a", "a", "b", "c", "c", "d", "e", "e"]
    r1 = metrics.cluster_bootstrap_ci(values, clusters, seed=3)
    r2 = metrics.cluster_bootstrap_ci(values, clusters, seed=3)
    rev = metrics.cluster_bootstrap_ci(values[::-1], clusters[::-1], seed=3)
    assert r1 == r2 == rev


def test_cluster_bootstrap_widens_when_identical_cases_are_clustered():
    """Nine identical results in one cluster carry one observation's worth of evidence."""
    values = [1] * 9 + [0, 1, 0, 0, 1, 0, 0]
    singletons = [str(i) for i in range(len(values))]
    clustered = ["rc"] * 9 + [str(i) for i in range(7)]
    a = metrics.cluster_bootstrap_ci(values, singletons, seed=5)
    b = metrics.cluster_bootstrap_ci(values, clustered, seed=5)
    assert a["mean"] == b["mean"]
    assert (b["ci_high"] - b["ci_low"]) > (a["ci_high"] - a["ci_low"])


def test_cluster_bootstrap_with_singleton_clusters_matches_case_bootstrap_width_roughly():
    values = [i % 3 == 0 for i in range(60)]
    a = metrics.bootstrap_ci([float(v) for v in values], seed=11)
    b = metrics.cluster_bootstrap_ci([float(v) for v in values], [str(i) for i in range(60)], seed=11)
    assert a["mean"] == b["mean"]
    assert abs((a["ci_high"] - a["ci_low"]) - (b["ci_high"] - b["ci_low"])) < 0.08


def test_cluster_bootstrap_degenerate_cases_and_length_check():
    assert metrics.cluster_bootstrap_ci([], [], seed=1)["n"] == 0
    one = metrics.cluster_bootstrap_ci([0.5, 1.0], ["x", "x"], seed=1)
    assert one["ci_low"] == one["ci_high"] == one["mean"] == 0.75
    with pytest.raises(ValueError):
        metrics.cluster_bootstrap_ci([1.0], ["a", "b"], seed=1)


def test_date_bucket_has_an_undated_bucket():
    assert datasets.date_bucket(None) == "undated"
    assert datasets.date_bucket("") == "undated"
    assert datasets.date_bucket("2026-06-30") == "pre"
    assert datasets.date_bucket("2026-07-01") == "post"


def test_cluster_key_is_module_plus_versions():
    assert datasets.cluster_key("github.com/rclone/rclone", "1.74.4", "1.75.0") == datasets.RCLONE_CLUSTER


def test_score_rows_puts_undated_cases_in_their_own_bucket_and_uses_clusters():
    from vulntrace.eval.symbols_score import _score_rows

    case_list = [{"id": "A", "created": "2020-01-01"}, {"id": "B", "created": None},
                 {"id": "C", "created": "2026-09-01"}, {"id": "D", "created": "2026-09-02"}]
    gold = {k: {"core": {"F"}, "core_derived": {"F", "G"}} for k in "ABCD"}
    pred = {"A": {"F"}, "B": {"F"}, "C": set(), "D": {"F"}}
    out = _score_rows(case_list, pred, gold, seed=1, cutoff="2026-06-30",
                      cluster_by_id={"A": "x", "B": "y", "C": "z", "D": "z"})
    assert out["summary_core_pre_cutoff"]["n_cases"] == 1      # A only; B is no longer "pre"
    assert out["summary_core_undated"]["n_cases"] == 1         # B
    assert out["summary_core_post_cutoff"]["n_cases"] == 2
    assert out["cluster_count"] == 3
    assert out["summary_core"]["cluster_recall"]["n_clusters"] == 3
    assert [r["date_bucket"] for r in out["rows"]] == ["pre", "undated", "post", "post"]
