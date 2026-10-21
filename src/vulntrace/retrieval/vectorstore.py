"""`VectorStore` interface and the in-memory backend (CP4 deliverable 2; interfaces doc
section 4). The PostgreSQL + pgvector backend is in `pgvector_store`.

Contract (enforced identically by both backends and checked by one shared test suite):

- A record is identified by (chunk_id, variant, embedding_model); upserting the same identity
  again replaces it.
- Metadata filters are exact-match on the fields in `FILTER_FIELDS`; any other key is an error.
- `search` must filter on `embedding_model` (vectors from different models are not
  comparable and may differ in dimension). Scores are cosine similarity; results are ordered by
  descending score, ties by `chunk_id`.
- `delete` needs at least one filter (no accidental "delete everything") and returns the number
  of records removed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

FILTER_FIELDS = ("variant", "embedding_model", "range_key", "module", "version", "package", "symbol",
                 "candidate_id", "content_sha256")
REQUIRED_METADATA = ("variant", "embedding_model", "range_key")


@dataclass
class VectorRecord:
    chunk_id: str
    vector: np.ndarray
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    metadata: dict[str, str]


class VectorStoreError(ValueError):
    pass


def check_filters(filters: dict[str, Any], *, for_search: bool) -> None:
    unknown = set(filters) - set(FILTER_FIELDS)
    if unknown:
        raise VectorStoreError(f"unknown filter field(s): {sorted(unknown)}")
    if for_search and "embedding_model" not in filters:
        raise VectorStoreError("search must filter on embedding_model")
    if not for_search and not filters:
        raise VectorStoreError("delete needs at least one filter")


def check_record(r: VectorRecord) -> None:
    missing = [k for k in REQUIRED_METADATA if not r.metadata.get(k)]
    if missing:
        raise VectorStoreError(f"record {r.chunk_id!r} lacks metadata {missing}")
    unknown = set(r.metadata) - set(FILTER_FIELDS)
    if unknown:
        raise VectorStoreError(f"record {r.chunk_id!r} has unknown metadata {sorted(unknown)}")


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, records: list[VectorRecord]) -> None: ...

    @abstractmethod
    def search(self, vector: np.ndarray, filters: dict[str, str], k: int) -> list[SearchHit]: ...

    @abstractmethod
    def delete(self, filters: dict[str, str]) -> int: ...

    @abstractmethod
    def count(self, filters: dict[str, str] | None = None) -> int: ...


def _unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class InMemoryVectorStore(VectorStore):
    """Brute-force cosine similarity over float32 vectors, with a per-field inverted index so
    the eval harness's (embedding_model, variant, range_key) scoped searches stay fast."""

    def __init__(self):
        self._records: dict[tuple[str, str, str], tuple[np.ndarray, dict[str, str]]] = {}
        self._index: dict[str, dict[str, set]] = {f: {} for f in FILTER_FIELDS}

    @staticmethod
    def _key(r_chunk_id: str, meta: dict[str, str]) -> tuple[str, str, str]:
        return r_chunk_id, meta["variant"], meta["embedding_model"]

    def _unindex(self, key, meta):
        for f, v in meta.items():
            self._index[f].get(v, set()).discard(key)

    def upsert(self, records: list[VectorRecord]) -> None:
        for r in records:
            check_record(r)
            key = self._key(r.chunk_id, r.metadata)
            if key in self._records:
                self._unindex(key, self._records[key][1])
            meta = {k: v for k, v in r.metadata.items() if v != ""}  # as the SQL backend returns them
            self._records[key] = (_unit(r.vector), meta)
            for f, v in meta.items():
                self._index[f].setdefault(v, set()).add(key)

    def _matching(self, filters: dict[str, str]) -> set:
        if not filters:
            return set(self._records)
        sets = [self._index[f].get(v, set()) for f, v in filters.items()]
        return set.intersection(*map(set, sets))

    def search(self, vector: np.ndarray, filters: dict[str, str], k: int) -> list[SearchHit]:
        check_filters(filters, for_search=True)
        keys = sorted(self._matching(filters))  # sorted: deterministic, chunk_id-first order
        if not keys or k <= 0:
            return []
        q = _unit(vector)
        m = np.stack([self._records[key][0] for key in keys])
        if m.shape[1] != q.shape[0]:
            raise VectorStoreError(f"query has dimension {q.shape[0]}, stored vectors have {m.shape[1]}")
        sims = m @ q
        order = sorted(range(len(keys)), key=lambda i: (-float(sims[i]), keys[i][0]))[:k]
        return [SearchHit(keys[i][0], float(sims[i]), dict(self._records[keys[i]][1])) for i in order]

    def delete(self, filters: dict[str, str]) -> int:
        check_filters(filters, for_search=False)
        keys = self._matching(filters)
        for key in keys:
            self._unindex(key, self._records.pop(key)[1])
        return len(keys)

    def count(self, filters: dict[str, str] | None = None) -> int:
        if filters:
            check_filters(filters, for_search=False)
        return len(self._matching(filters or {}))
