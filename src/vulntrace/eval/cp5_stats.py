"""Metrics and paired cluster statistics for the CP5 selection experiments (E1, S1).

`set_metrics` scores one predicted set against one gold set (unlike CP3's `per_case_scores` it
accepts an empty gold set: such a case can never be hit). Case values go into a matrix; `Group`
resamples whole clusters with the same seeded draws for every method, so a difference between two
methods on the same cases has a paired cluster-bootstrap interval (the CP4 machinery,
`retrieval_metrics.ClusterResampler`).
"""

from typing import Any, Iterable

import numpy as np

from vulntrace.eval.retrieval_metrics import ClusterResampler

# columns of a case-value matrix
COLUMNS = ("precision0", "recall", "f1", "exact", "any_hit", "abstain")
SEED = 20261022


def set_metrics(pred: Iterable, gold: Iterable) -> dict[str, Any]:
    pred, gold = set(pred), set(gold)
    inter = pred & gold
    precision = len(inter) / len(pred) if pred else None
    recall = len(inter) / len(gold) if gold else 0.0
    p0 = precision or 0.0
    f1 = 0.0 if p0 + recall == 0 else 2 * p0 * recall / (p0 + recall)
    return {"predicted": len(pred), "gold": len(gold), "hits": len(inter), "precision": precision, "recall": recall,
            "f1": f1, "exact": bool(gold) and pred == gold, "any_hit": bool(inter), "abstain": not pred}


def to_vector(m: dict[str, Any]) -> list[float]:
    """precision0 treats 'nothing predicted' as precision 0 (so it can be averaged and paired)."""
    return [float(m["precision"] or 0.0), float(m["recall"]), float(m["f1"]), float(m["exact"]), float(m["any_hit"]),
            float(m["abstain"])]


def matrix(metric_dicts: list[dict[str, Any]]) -> np.ndarray:
    return np.array([to_vector(m) for m in metric_dicts], dtype=np.float64).reshape(len(metric_dicts), len(COLUMNS))


def answered_precision(metric_dicts: list[dict[str, Any]]) -> tuple[float, int]:
    """(mean precision over cases that predicted something, how many such cases)."""
    ps = [m["precision"] for m in metric_dicts if m["precision"] is not None]
    return (float(np.mean(ps)) if ps else float("nan")), len(ps)


class Group:
    """One set of cases with fixed seeded cluster draws."""

    def __init__(self, clusters: list[str], seed: int = SEED):
        self.rs = ClusterResampler(clusters, seed=seed)
        self.n = len(clusters)

    @property
    def n_clusters(self) -> int:
        return self.rs.n_clusters

    def summary(self, values: np.ndarray) -> list[dict[str, float]]:
        if not self.n:
            nan = float("nan")
            return [{"mean": nan, "ci_low": nan, "ci_high": nan, "n": 0, "n_clusters": 0} for _ in range(values.shape[1])]
        return self.rs.summarize(values)

    def paired(self, a: np.ndarray, b: np.ndarray) -> list[dict[str, float]]:
        """a - b per column, with a paired cluster-bootstrap interval."""
        if not self.n:
            nan = float("nan")
            return [{"mean": nan, "ci_low": nan, "ci_high": nan, "n": 0} for _ in range(a.shape[1])]
        point = a.mean(axis=0) - b.mean(axis=0)
        ra, rb = self.rs.resample_means(a), self.rs.resample_means(b)
        out = []
        for j in range(a.shape[1]):
            if ra is None:
                lo = hi = float(point[j])
            else:
                lo, hi = (float(x) for x in np.quantile(ra[:, j] - rb[:, j], [0.025, 0.975]))
            out.append({"mean": float(point[j]), "ci_low": lo, "ci_high": hi, "n": self.n})
        return out


def rate_ci(group: Group, flags: list[bool]) -> dict[str, float]:
    return group.summary(np.array(flags, dtype=np.float64).reshape(-1, 1))[0]
