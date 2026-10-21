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
