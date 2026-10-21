"""Cross-encoder reranking of the head of a ranking (CP4 deliverable 5).

The top `top_n` items (default 50, recorded in every result) are re-scored by the `Reranker`
and re-ordered; ties keep their previous order; everything below `top_n` keeps its place.
"""

from vulntrace.models.base import Reranker

DEFAULT_TOP_N = 50


def rerank(reranker: Reranker, query: str, ranked: list[str], text_of: dict[str, str],
           top_n: int = DEFAULT_TOP_N) -> list[str]:
    head, tail = ranked[:top_n], ranked[top_n:]
    if not head:
        return list(ranked)
    scores = reranker.score(query, [text_of[i] for i in head])
    order = sorted(range(len(head)), key=lambda i: (-scores[i], i))
    return [head[i] for i in order] + tail
