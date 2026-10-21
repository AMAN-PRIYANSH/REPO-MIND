"""Retrieval metrics (docs/evaluation/EVALUATION_PLAN.md, "Retrieval (D4)") and the cluster
bootstrap used for them.

Gold = candidates whose symbol is a curated core symbol (name-level match, as in CP3).
- Recall@k: 1 if any gold candidate is in the top k, else 0 (the plan's definition; this is a
  hit rate, not the fraction of gold found).
- MRR: 1 / rank of the first gold candidate (full ranking, no cutoff); 0 if none.
- nDCG@10: binary relevance, DCG = sum over gold in the top 10 of 1/log2(rank + 1), divided by
  the ideal DCG for min(#gold, 10) gold items.
A case with no gold among its candidates scores 0 on everything; it is excluded from
denominator (a) "gold inside the candidate set" and counted as a miss in denominator (b) "all
scored cases".

The bootstrap resamples clusters (identical release ranges) with replacement; every metric of
every configuration is resampled with the same seeded cluster draws, so differences between two
configurations can be bootstrapped as paired differences.
"""

import math
from typing import Any

import numpy as np

KS = (1, 5, 10, 20)
METRICS = ("recall@1", "recall@5", "recall@10", "recall@20", "mrr", "ndcg@10")
TOP_RANKS_KEPT = 20
DEFAULT_RESAMPLES = 2000


def gold_ranks(ranking: list[str], gold: set[str]) -> list[int]:
    """1-based ranks of every gold item present in `ranking`, ascending."""
    return [i for i, item in enumerate(ranking, start=1) if item in gold]


def ndcg_at(ranks: list[int], n_gold: int, k: int = 10) -> float:
    if n_gold <= 0:
        return 0.0
    dcg = sum(1.0 / math.log2(r + 1) for r in ranks if r <= k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(n_gold, k) + 1))
    return dcg / idcg


def case_metrics(first_rank: int | None, top_ranks: list[int], n_gold: int) -> dict[str, float]:
    out = {f"recall@{k}": float(first_rank is not None and first_rank <= k) for k in KS}
    out["mrr"] = 1.0 / first_rank if first_rank else 0.0
    out["ndcg@10"] = ndcg_at(top_ranks, n_gold, 10)
    return out


def ranking_row(ranking: list[str], gold: set[str]) -> dict[str, Any]:
    """The compact per-case record a run stores: enough to recompute every metric."""
    ranks = gold_ranks(ranking, gold)
    return {"first_rank": ranks[0] if ranks else None, "top_ranks": [r for r in ranks if r <= TOP_RANKS_KEPT]}


def metric_matrix(rows: list[dict[str, Any]], n_gold: list[int]) -> np.ndarray:
    """(n_cases, len(METRICS)) array from compact rows."""
    out = np.zeros((len(rows), len(METRICS)), dtype=np.float64)
    for i, (r, g) in enumerate(zip(rows, n_gold)):
        m = case_metrics(r["first_rank"], r["top_ranks"], g)
        out[i] = [m[k] for k in METRICS]
    return out


class ClusterResampler:
    """Seeded cluster draws for one set of cases, reused across metrics and configurations."""

    def __init__(self, clusters: list[str], seed: int, n_resamples: int = DEFAULT_RESAMPLES):
        self.keys = sorted(set(clusters))
        pos = {k: i for i, k in enumerate(self.keys)}
        self.member = np.array([pos[c] for c in clusters], dtype=np.int64)
        self.n = len(clusters)
        g = len(self.keys)
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, g, size=(n_resamples, g)) if g >= 2 else None
        sizes = np.bincount(self.member, minlength=g).astype(np.float64)
        self.sizes = sizes

    @property
    def n_clusters(self) -> int:
        return len(self.keys)

    def _cluster_sums(self, values: np.ndarray) -> np.ndarray:
        g = len(self.keys)
        v = values.reshape(self.n, -1)
        sums = np.zeros((g, v.shape[1]))
        np.add.at(sums, self.member, v)
        return sums

    def resample_means(self, values: np.ndarray) -> np.ndarray | None:
        """(n_resamples, n_metrics) case-weighted means, or None with fewer than 2 clusters."""
        if self.idx is None:
            return None
        sums = self._cluster_sums(values)
        return sums[self.idx].sum(axis=1) / self.sizes[self.idx].sum(axis=1)[:, None]

    def summarize(self, values: np.ndarray, ci: float = 0.95) -> list[dict[str, float]]:
        v = values.reshape(self.n, -1)
        point = v.mean(axis=0) if self.n else np.zeros(v.shape[1])
        res = self.resample_means(v)
        out = []
        for j in range(v.shape[1]):
            if res is None:
                lo = hi = float(point[j])
            else:
                lo, hi = (float(x) for x in np.quantile(res[:, j], [(1 - ci) / 2, (1 + ci) / 2]))
            out.append({"mean": float(point[j]), "ci_low": lo, "ci_high": hi, "n": self.n,
                        "n_clusters": self.n_clusters})
        return out
