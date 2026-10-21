"""Interface checks every Embedder / Reranker must pass: run by the contract tests on the
fakes and by the Colab notebook on the real models, so both obey the same rules."""

import numpy as np

from vulntrace.models.base import Embedder, Reranker

SAMPLE_TEXTS = ["func ParseRequest(r *http.Request) error", "package config\nfunc Load() {}",
                "func ParseRequest(r *http.Request) error"]


def check_embedder(e: Embedder) -> None:
    assert isinstance(e.model_id, str) and e.model_id, "model_id must be a non-empty string"
    v = e.embed(SAMPLE_TEXTS)
    assert isinstance(v, np.ndarray) and v.dtype == np.float32, "embed must return a float32 ndarray"
    assert v.shape == (3, e.dim), f"shape {v.shape} != (3, {e.dim})"
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-3), "rows must be L2-normalised"
    assert np.allclose(v[0], v[2], atol=1e-4), "identical texts must embed identically"
    assert np.allclose(e.embed(SAMPLE_TEXTS[:1])[0], v[0], atol=1e-4), "embedding must not depend on the batch"
    q = e.embed_query("parse an HTTP request")
    assert q.shape == (e.dim,) and abs(float(np.linalg.norm(q)) - 1.0) < 1e-3, "query vector must be normalised"
    assert e.embed([]).shape == (0, e.dim), "an empty batch returns an empty (0, dim) array"
    info = e.info()
    assert info["model_id"] == e.model_id and info["dim"] == e.dim


def check_reranker(r: Reranker) -> None:
    assert isinstance(r.model_id, str) and r.model_id
    s = r.score("parse an HTTP request", SAMPLE_TEXTS)
    assert isinstance(s, list) and len(s) == 3 and all(isinstance(x, float) for x in s)
    assert abs(s[0] - s[2]) < 1e-4, "identical texts must score identically"
    assert r.score("q", []) == []
    assert r.info()["model_id"] == r.model_id
