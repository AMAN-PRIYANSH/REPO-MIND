"""Deterministic fake models for tests and dry runs. They download nothing, call nothing and
give identical output on every machine (no Python `hash()`, which is salted per process)."""

import hashlib

import numpy as np

from vulntrace.models.base import Embedder, Reranker, l2_normalise
from vulntrace.retrieval.tokenize import code_tokens

FAKE_EMBEDDER_ID = "fake-hash-embedder-v1"
FAKE_RERANKER_ID = "fake-token-overlap-reranker-v1"


def _bucket_and_sign(token: str, dim: int) -> tuple[int, float]:
    h = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "little") % dim, (1.0 if h[4] & 1 else -1.0)


class FakeEmbedder(Embedder):
    """Signed feature hashing of `code_tokens`, L2-normalised: texts that share tokens get a
    higher cosine similarity, so retrieval tests are meaningful, not just shape checks.
    `calls` counts embedded texts (used by the index-freshness tests)."""

    def __init__(self, dim: int = 64, model_id: str = FAKE_EMBEDDER_ID):
        self._dim = dim
        self.model_id = model_id
        self.calls = 0

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls += len(texts)
        m = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in code_tokens(t):
                j, s = _bucket_and_sign(tok, self._dim)
                m[i, j] += s
        return l2_normalise(m)

    def info(self):
        return {"model_id": self.model_id, "dim": self._dim, "kind": "FAKE"}


class FakeReranker(Reranker):
    """Fraction of the query's distinct tokens that occur in the text."""

    def __init__(self, model_id: str = FAKE_RERANKER_ID):
        self.model_id = model_id
        self.calls = 0

    def score(self, query: str, texts: list[str]) -> list[float]:
        self.calls += len(texts)
        q = set(code_tokens(query))
        if not q:
            return [0.0] * len(texts)
        return [len(q & set(code_tokens(t))) / len(q) for t in texts]

    def info(self):
        return {"model_id": self.model_id, "kind": "FAKE"}
