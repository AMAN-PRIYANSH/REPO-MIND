"""Symbol-identification metrics: precision/recall/F1 (macro), exact match, any-hit, and
95% percentile-bootstrap confidence intervals (CP3 deliverable 6, docs/evaluation/
EVALUATION_PLAN.md)."""

import random
from typing import Any

DEFAULT_RESAMPLES = 2000
DEFAULT_CI = 0.95


def per_case_scores(predicted: set, gold: set) -> dict[str, Any]:
    """precision/recall/F1 for one case. `gold` must not be empty (every D1/D4-eligible case
    has at least one core symbol); `predicted` may be empty (counted as abstention: 0
    precision contribution - undefined when there is nothing predicted, excluded from the
    precision average - and 0 recall)."""
    if not gold:
        raise ValueError("gold set must not be empty")
    inter = predicted & gold
    recall = len(inter) / len(gold)
    precision = (len(inter) / len(predicted)) if predicted else None
    p_for_f1 = precision if precision is not None else 0.0
    f1 = 0.0 if p_for_f1 + recall == 0 else 2 * p_for_f1 * recall / (p_for_f1 + recall)
    return {
        "predicted_count": len(predicted), "gold_count": len(gold), "intersection": len(inter),
        "precision": precision, "recall": recall, "f1": f1,
        "exact_match": predicted == gold, "any_hit": len(inter) > 0, "abstained": len(predicted) == 0,
    }


def bootstrap_ci(values: list[float], seed: int, n_resamples: int = DEFAULT_RESAMPLES,
                 ci: float = DEFAULT_CI) -> dict[str, Any]:
    """{mean, ci_low, ci_high, n} via the percentile bootstrap of the mean. Deterministic
    for a given seed (tested); `values` with fewer than 2 elements returns a degenerate
    interval equal to the point estimate rather than raising."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    point = sum(values) / n
    if n < 2:
        return {"mean": point, "ci_low": point, "ci_high": point, "n": n}
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int((1 - ci) / 2 * n_resamples)]
    hi = means[min(int((1 + ci) / 2 * n_resamples), n_resamples - 1)]
    return {"mean": point, "ci_low": lo, "ci_high": hi, "n": n}


def summarize(per_case: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    """Macro-averaged precision/recall/F1 (with bootstrap CIs), exact-match rate and
    any-hit rate, plus the raw counts every rate in EVALUATION_PLAN.md must carry."""
    n = len(per_case)
    precisions = [c["precision"] for c in per_case if c["precision"] is not None]
    recalls = [c["recall"] for c in per_case]
    f1s = [c["f1"] for c in per_case]
    exact = sum(1 for c in per_case if c["exact_match"])
    any_hit = sum(1 for c in per_case if c["any_hit"])
    abstained = sum(1 for c in per_case if c["abstained"])
    return {
        "n_cases": n,
        "precision": bootstrap_ci(precisions, seed), "precision_n_scored": len(precisions),
        "recall": bootstrap_ci(recalls, seed + 1),
        "f1": bootstrap_ci(f1s, seed + 2),
        "exact_match": {"count": exact, "rate": exact / n if n else 0.0},
        "any_hit": {"count": any_hit, "rate": any_hit / n if n else 0.0},
        "abstained": {"count": abstained, "rate": abstained / n if n else 0.0},
    }


def cluster_bootstrap_ci(values: list[float], clusters: list[str], seed: int, n_resamples: int = DEFAULT_RESAMPLES,
                         ci: float = DEFAULT_CI) -> dict[str, Any]:
    """{mean, ci_low, ci_high, n, n_clusters}: percentile bootstrap that resamples whole
    clusters with replacement (CP3 review finding 1: cases sharing one release range are not
    independent). Each resample's statistic is the case-weighted mean over every case in the
    drawn clusters, so the point estimate equals the plain case mean. With one cluster per
    case this is the ordinary case bootstrap. Deterministic for a given seed."""
    if len(values) != len(clusters):
        raise ValueError("values and clusters must have the same length")
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0, "n_clusters": 0}
    point = sum(values) / n
    groups: dict[str, list[float]] = {}
    for v, c in zip(values, clusters):
        groups.setdefault(c, []).append(v)
    keys = sorted(groups)  # fixed order: the result must not depend on input order
    sums = [sum(groups[k]) for k in keys]
    sizes = [len(groups[k]) for k in keys]
    g = len(keys)
    if g < 2:
        return {"mean": point, "ci_low": point, "ci_high": point, "n": n, "n_clusters": g}
    rng = random.Random(seed)
    means = []
    for _ in range(n_resamples):
        idx = [rng.randrange(g) for _ in range(g)]
        means.append(sum(sums[i] for i in idx) / sum(sizes[i] for i in idx))
    means.sort()
    lo = means[int((1 - ci) / 2 * n_resamples)]
    hi = means[min(int((1 + ci) / 2 * n_resamples), n_resamples - 1)]
    return {"mean": point, "ci_low": lo, "ci_high": hi, "n": n, "n_clusters": g}


def summarize_clustered(per_case: list[dict[str, Any]], clusters: list[str], seed: int) -> dict[str, Any]:
    """`summarize`, plus cluster-bootstrap intervals for precision, recall and F1 under
    `cluster_*` keys (the case-bootstrap ones are kept so the widening can be reported)."""
    out = summarize(per_case, seed)
    p_vals = [(c["precision"], k) for c, k in zip(per_case, clusters) if c["precision"] is not None]
    out["cluster_precision"] = cluster_bootstrap_ci([v for v, _ in p_vals], [k for _, k in p_vals], seed)
    out["cluster_recall"] = cluster_bootstrap_ci([c["recall"] for c in per_case], clusters, seed + 1)
    out["cluster_f1"] = cluster_bootstrap_ci([c["f1"] for c in per_case], clusters, seed + 2)
    return out
