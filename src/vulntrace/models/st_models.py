"""Real models via sentence-transformers (optional extra `.[ml]`). Used only in evaluation
runs (Colab); tests never import this module. Models are downloaded from Hugging Face by
sentence-transformers itself; this code never calls any hosted inference API."""

from typing import Any

import numpy as np

from vulntrace.models.base import Embedder, Reranker, l2_normalise


def _resolved_revision(hf_id: str, requested: str | None) -> str | None:
    """The Hugging Face commit the model was loaded from, for the results' provenance."""
    if requested:
        return requested
    try:
        from huggingface_hub import model_info

        return model_info(hf_id).sha
    except Exception:  # offline, or the hub API changed: record that it is unknown
        return None


def _versions() -> dict[str, str]:
    out = {}
    for mod in ("sentence_transformers", "transformers", "torch"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception:
            out[mod] = "unknown"
    return out


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, hf_id: str, query_prefix: str = "", device: str | None = None, revision: str | None = None,
                 batch_size: int = 64, max_seq_length: int | None = None):
        from sentence_transformers import SentenceTransformer

        self.model_id = hf_id
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self.revision = _resolved_revision(hf_id, revision)
        self._model = SentenceTransformer(hf_id, device=device, revision=revision)
        if max_seq_length:
            self._model.max_seq_length = min(max_seq_length, self._model.max_seq_length or max_seq_length)
        self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        v = self._model.encode(texts, batch_size=self.batch_size, convert_to_numpy=True,
                               normalize_embeddings=True, show_progress_bar=False)
        return l2_normalise(v)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([self.query_prefix + text])[0]

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "revision": self.revision, "dim": self._dim, "kind": "SENTENCE_TRANSFORMERS",
                "query_prefix": self.query_prefix, "max_seq_length": self._model.max_seq_length,
                "device": str(self._model.device), "batch_size": self.batch_size, "versions": _versions()}


class CrossEncoderReranker(Reranker):
    def __init__(self, hf_id: str, device: str | None = None, revision: str | None = None, batch_size: int = 32,
                 max_length: int = 512):
        from sentence_transformers import CrossEncoder

        self.model_id = hf_id
        self.batch_size = batch_size
        self.max_length = max_length
        self.revision = _resolved_revision(hf_id, revision)
        kwargs = {"device": device, "max_length": max_length}
        if revision:
            kwargs["revision"] = revision
        self._model = CrossEncoder(hf_id, **kwargs)

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        s = self._model.predict([(query, t) for t in texts], batch_size=self.batch_size, show_progress_bar=False)
        return [float(x) for x in np.asarray(s).reshape(-1)]

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "revision": self.revision, "kind": "CROSS_ENCODER",
                "max_length": self.max_length, "batch_size": self.batch_size, "versions": _versions()}
