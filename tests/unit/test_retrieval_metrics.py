"""Retrieval metric maths on hand-computed rankings, and the vectorised cluster bootstrap."""

import math

import numpy as np
import pytest

from vulntrace.eval import retrieval_metrics as rm


def test_gold_ranks_and_compact_row():
    ranking = ["a", "b", "c", "d", "e"]
    assert rm.gold_ranks(ranking, {"b", "e", "zz"}) == [2, 5]
    assert rm.ranking_row(ranking, {"b", "e"}) == {"first_rank": 2, "top_ranks": [2, 5]}
    assert rm.ranking_row(ranking, {"zz"}) == {"first_rank": None, "top_ranks": []}


def test_case_metrics_hand_computed():
    # gold at ranks 3 and 12 (two gold items)
    m = rm.case_metrics(3, [3, 12], 2)
    assert m["recall@1"] == 0 and m["recall@5"] == 1 and m["recall@10"] == 1 and m["recall@20"] == 1
    assert m["mrr"] == pytest.approx(1 / 3)
    # DCG@10 = 1/log2(4) = 0.5 ; IDCG = 1/log2(2) + 1/log2(3) = 1 + 0.630930 = 1.630930
    assert m["ndcg@10"] == pytest.approx(0.5 / (1 + 1 / math.log2(3)))
    assert m["ndcg@10"] == pytest.approx(0.306574, abs=1e-6)


def test_case_metrics_first_rank_beyond_20_and_misses():
    m = rm.case_metrics(37, [], 1)
    assert [m[f"recall@{k}"] for k in rm.KS] == [0, 0, 0, 0]
    assert m["mrr"] == pytest.approx(1 / 37) and m["ndcg@10"] == 0
    z = rm.case_metrics(None, [], 0)  # gold outside the candidate set: a miss everywhere
    assert all(v == 0 for v in z.values())


def test_perfect_ranking_has_ndcg_one_and_more_gold_than_k_is_capped():
    assert rm.case_metrics(1, [1, 2, 3], 3)["ndcg@10"] == pytest.approx(1.0)
    assert rm.ndcg_at(list(range(1, 11)), 15, 10) == pytest.approx(1.0)
    assert rm.ndcg_at([1], 0) == 0.0


def test_metric_matrix_column_order():
    mat = rm.metric_matrix([{"first_rank": 1, "top_ranks": [1]}, {"first_rank": None, "top_ranks": []}], [1, 1])
    assert mat.shape == (2, len(rm.METRICS))
    assert list(mat[0]) == [1, 1, 1, 1, 1, 1] and list(mat[1]) == [0, 0, 0, 0, 0, 0]


def test_cluster_resampler_point_estimate_determinism_and_cluster_resampling():
    clusters = ["a", "a", "a", "b"]
    values = np.array([[1.0], [1.0], [1.0], [0.0]])
    r1 = rm.ClusterResampler(clusters, seed=3, n_resamples=500)
    s = r1.summarize(values)[0]
    assert s["mean"] == pytest.approx(0.75) and s["n_clusters"] == 2 and s["n"] == 4
    means = r1.resample_means(values)[:, 0]
    assert set(np.round(means, 6)) <= {0.0, 0.75, 1.0}  # whole clusters only
    assert rm.ClusterResampler(clusters, seed=3, n_resamples=500).summarize(values) == r1.summarize(values)


def test_cluster_resampler_paired_draws_give_zero_width_difference_for_identical_configs():
    clusters = [f"c{i % 7}" for i in range(30)]
    rng = np.random.default_rng(0)
    a = rng.random((30, 1))
    r = rm.ClusterResampler(clusters, seed=9, n_resamples=300)
    diff = r.resample_means(a) - r.resample_means(a)
    assert np.all(diff == 0)


def test_cluster_resampler_single_cluster_is_degenerate():
    r = rm.ClusterResampler(["x", "x"], seed=1)
    s = r.summarize(np.array([[0.5], [1.0]]))[0]
    assert s["ci_low"] == s["ci_high"] == s["mean"] == 0.75
