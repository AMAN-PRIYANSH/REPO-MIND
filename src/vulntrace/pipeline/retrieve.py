"""Mode 2 candidate ranking with the fixed retriever (CP5 task 0c): `hybrid:bge-small` over
`code+commits` chunks, k = 10, no reranker. CP6 binding decision: no agent; the retriever's
top-k is the candidate list.

The query is built only from the advisory's summary and details (`retrieval.query`). The
embedding model is a free open model loaded locally. By default it is loaded offline
(`HF_HUB_OFFLINE=1`): if it is not installed or not cached, the ranking falls back to the fixed
retriever's own `secondary_config` (`bm25`, statistically indistinguishable from hybrid in CP4),
and the fallback and its reason are recorded in the verdict. Nothing here calls an LLM.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vulntrace.retrieval import bm25 as bm25_mod
from vulntrace.retrieval import chunking, dense, fixed, fusion, ranking
from vulntrace.retrieval.query import build_query, query_input_from_case
from vulntrace.retrieval.tokenize import code_tokens

FALLBACK_EMBEDDER_UNAVAILABLE = "EMBEDDER_UNAVAILABLE"


@dataclass
class Ranking:
    config_requested: str
    config_used: str
    variant: str
    k: int
    ranked: list[tuple[str, float]]               # (candidate id, score), best first, every candidate
    fallback: str | None = None
    fallback_reason: str | None = None
    query_chars: int = 0
    embedder: dict[str, Any] = field(default_factory=dict)

    def summary(self, top: int | None = None) -> dict[str, Any]:
        top = self.k if top is None else top
        return {"config_requested": self.config_requested, "config_used": self.config_used,
                "variant": self.variant, "k": self.k, "fallback": self.fallback,
                "fallback_reason": self.fallback_reason, "query_chars": self.query_chars,
                "candidates_total": len(self.ranked), "embedder": self.embedder or None,
                "top": [{"rank": i + 1, "candidate_id": cid, "score": round(s, 6)}
                        for i, (cid, s) in enumerate(self.ranked[:top])]}


def _bm25(chunks: list[chunking.Chunk], query: str, variant: str, group: str) -> tuple[list[str], dict[str, float]]:
    ids = [c.candidate_id for c in chunks]
    scores = bm25_mod.BM25([code_tokens(c.text(variant).text) for c in chunks]).scores(code_tokens(query))
    return ranking.rank(ids, scores, group), dict(zip(ids, scores))


def _dense(chunks: list[chunking.Chunk], query: str, variant: str, group: str, embedder,
           cache_root: Path | None) -> tuple[list[str], dict[str, float]]:
    cache = dense.EmbeddingCache(cache_root, embedder.model_id)
    texts = {c.text(variant).content_sha256: c.text(variant).text for c in chunks}
    dense.embed_missing(embedder, cache, texts)
    q = np.asarray(embedder.embed_query(query), dtype=np.float32)
    ids = [c.candidate_id for c in chunks]
    scores = [float(np.dot(cache.get(c.text(variant).content_sha256), q)) for c in chunks]
    return ranking.rank(ids, scores, group), dict(zip(ids, scores))


def make_embedder_offline(alias: str, allow_download: bool, device: str | None = None):
    """The registry's embedder, loaded without network unless `allow_download`."""
    from vulntrace.models.registry import make_embedder

    if not allow_download:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return make_embedder(alias, device=device)


def rank_candidates(case: dict[str, Any], release_range: dict[str, Any], candidate_code: dict[str, Any],
                    fix_owner: str, fix_repo: str, *, config: str = "fixed", k: int | None = None,
                    embedder=None, embedding_cache: Path | None = None, allow_download: bool = False,
                    device: str | None = None) -> Ranking:
    """Rank every candidate of the range for the advisory. `config` is `fixed` (the fixed
    retriever), `bm25`, or `hybrid:<embedder alias>`. `embedder` overrides model loading (tests)."""
    fx = fixed.load()
    requested = fx.config if config == "fixed" else config
    variant = fx.variant
    k = k or fx.default_k
    query = build_query(query_input_from_case(case))
    group = case["id"]
    chunks = chunking.build_chunks(group, release_range, candidate_code, fix_owner, fix_repo)
    out = Ranking(config_requested=requested, config_used=requested, variant=variant, k=k, ranked=[],
                  query_chars=len(query))
    if not chunks:
        return out
    bm_rank, bm_scores = _bm25(chunks, query, variant, group)
    if requested == "bm25":
        out.ranked = [(cid, bm_scores[cid]) for cid in bm_rank]
        return out
    kind, _, alias = requested.partition(":")
    if kind != "hybrid" or not alias:
        raise ValueError(f"unsupported Mode 2 retriever {requested!r} (fixed, bm25 or hybrid:<embedder>)")
    try:
        emb = embedder if embedder is not None else make_embedder_offline(alias, allow_download, device)
        dn_rank, _ = _dense(chunks, query, variant, group, emb, embedding_cache)
        out.embedder = {"alias": alias, "model_id": emb.model_id}
    except Exception as exc:  # any failure to load or run the model: recorded fallback, never a crash
        fallback = fx.secondary_config or "bm25"
        out.config_used, out.fallback = fallback, FALLBACK_EMBEDDER_UNAVAILABLE
        out.fallback_reason = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}"
        out.ranked = [(cid, bm_scores[cid]) for cid in bm_rank]
        return out
    fused = fusion.rrf_scores([bm_rank, dn_rank])
    order = fusion.rrf([bm_rank, dn_rank], group)
    out.ranked = [(cid, fused[cid]) for cid in order]
    return out
