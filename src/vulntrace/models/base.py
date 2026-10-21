"""`Embedder` and `Reranker` interfaces (interfaces doc section 4).

Small extension to the informal interface: `Embedder.embed_query` exists because several open
embedding models expect an instruction prefix on queries but not on documents; the default
implementation simply embeds the text like a document. `info()` returns the provenance every
real call must record (model id, revision, settings)."""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class Embedder(ABC):
    model_id: str

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """float32 array of shape (len(texts), dim), each row L2-normalised."""

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    @property
    @abstractmethod
    def dim(self) -> int: ...

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "dim": self.dim}


class Reranker(ABC):
    model_id: str

    @abstractmethod
    def score(self, query: str, texts: list[str]) -> list[float]:
        """One relevance score per text; higher is more relevant."""

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id}


def l2_normalise(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms
