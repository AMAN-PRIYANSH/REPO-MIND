"""Reciprocal Rank Fusion (CP4 deliverable 5).

RRF(d) = sum over input rankings r containing d of 1 / (k + rank_r(d)), rank 1-based,
k = 60 (Cormack, Clarke and Buettcher 2009; not tuned here). An item absent from a ranking
contributes nothing for it. Ties in the fused score are broken by `ranking.tie_key`.
"""

from vulntrace.retrieval import ranking

DEFAULT_K = 60


def rrf_scores(rankings: list[list[str]], k: int = DEFAULT_K) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rankings:
        for pos, item in enumerate(r, start=1):
            out[item] = out.get(item, 0.0) + 1.0 / (k + pos)
    return out


def rrf(rankings: list[list[str]], group: str, k: int = DEFAULT_K, seed: int = ranking.DEFAULT_SEED) -> list[str]:
    scores = rrf_scores(rankings, k)
    items = list(scores)
    return ranking.rank(items, [scores[i] for i in items], group, seed)
