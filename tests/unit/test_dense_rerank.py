"""Index freshness (changed hash -> re-embed, unchanged -> skip), dense scoring through the
store, and reranking of the head only (CP4 D4, D5; testing strategy CP4 list)."""

import hashlib

import numpy as np

from vulntrace.models.fakes import FakeEmbedder, FakeReranker
from vulntrace.retrieval import dense, rerank
from vulntrace.retrieval.chunking import VARIANT_CODE_ONLY, Chunk
from vulntrace.retrieval.vectorstore import InMemoryVectorStore


def _sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def test_embedding_cache_skips_unchanged_and_reembeds_changed_text(tmp_path):
    e = FakeEmbedder()
    cache = dense.EmbeddingCache(tmp_path, e.model_id)
    texts = {_sha("a b"): "a b", _sha("c d"): "c d"}
    assert dense.embed_missing(e, cache, texts)["embedded"] == 2
    assert dense.embed_missing(e, cache, texts)["embedded"] == 0          # unchanged: skipped
    changed = {_sha("a b"): "a b", _sha("c d e"): "c d e"}
    stats = dense.embed_missing(e, cache, changed)
    assert stats["embedded"] == 1 and stats["cached"] == 1                # only the changed text
    assert e.calls == 3
    reopened = dense.EmbeddingCache(tmp_path, e.model_id)                 # persisted across runs
    assert len(reopened) == 3 and np.allclose(reopened.get(_sha("a b")), e.embed(["a b"])[0])
    other = dense.EmbeddingCache(tmp_path, "another-model")               # caches are per model
    assert len(other) == 0


def test_memory_only_cache_and_model_slug():
    cache = dense.EmbeddingCache(None, "org/model")
    cache.put_many(["k"], np.ones((1, 4), dtype=np.float32))
    assert "k" in cache and dense.model_slug("org/model v1") == "org__model__v1"


def _chunk(cid, body):
    return Chunk(chunk_id=f"R|{cid}", range_key="R", candidate_id=cid, module="m", version="1", package="m/p",
                 package_name="p", symbol=cid, file="f.go", side="BOTH", body_side="OLD", signature="", doc="",
                 body=body)


def test_index_and_dense_scores_rank_by_similarity():
    e = FakeEmbedder()
    cache = dense.EmbeddingCache(None, e.model_id)
    chunks = [_chunk("r1", "func ParseRequest(r *http.Request)"), _chunk("r2", "func WriteFile(path string)")]
    dense.embed_missing(e, cache, {c.text(VARIANT_CODE_ONLY).content_sha256: c.text(VARIANT_CODE_ONLY).text
                                   for c in chunks})
    store = InMemoryVectorStore()
    assert dense.index_chunks(store, cache, chunks, VARIANT_CODE_ONLY) == 2
    s = dense.dense_scores(store, e.embed_query("parse http request"), "R", VARIANT_CODE_ONLY, e.model_id, 2)
    assert set(s) == {"r1", "r2"} and s["r1"] > s["r2"]


def test_rerank_reorders_only_the_head():
    ranked = ["a", "b", "c", "d"]
    text = {"a": "nothing", "b": "http request", "c": "http", "d": "http request parse"}
    out = rerank.rerank(FakeReranker(), "parse http request", ranked, text, top_n=3)
    assert out == ["b", "c", "a", "d"]  # d is below the head and keeps its place
    assert rerank.rerank(FakeReranker(), "q", [], {}, top_n=3) == []
    assert rerank.DEFAULT_TOP_N == 50
