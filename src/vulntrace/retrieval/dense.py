"""Dense retrieval through the `Embedder` interface (CP4 deliverable 4).

Embeddings are cached by (embedding model, sha256 of the chunk text): a chunk whose text
changes gets a new hash and is re-embedded; an unchanged chunk is never embedded twice, across
runs and across cases that share a range (index freshness). The cache is a directory of
append-only `.npz` shards, so an interrupted Colab run keeps what it finished.
"""

import json
import re
import time
from pathlib import Path
from typing import Iterable

import numpy as np

from vulntrace.models.base import Embedder
from vulntrace.retrieval.chunking import Chunk
from vulntrace.retrieval.vectorstore import VectorRecord, VectorStore

DEFAULT_BATCH = 256


def model_slug(model_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", model_id)


class EmbeddingCache:
    """content_sha256 -> vector for one embedding model, persisted under `root/<model>/`
    (or memory-only when `root` is None)."""

    def __init__(self, root: Path | None, model_id: str):
        self.model_id = model_id
        self.dir = (Path(root) / model_slug(model_id)) if root is not None else None
        self._vectors: dict[str, np.ndarray] = {}
        if self.dir is not None and self.dir.is_dir():
            for shard in sorted(self.dir.glob("shard_*.npz")):
                with np.load(shard, allow_pickle=False) as z:
                    for k, v in zip(z["keys"], z["vectors"]):
                        self._vectors[str(k)] = v

    def __contains__(self, sha: str) -> bool:
        return sha in self._vectors

    def __len__(self) -> int:
        return len(self._vectors)

    def get(self, sha: str) -> np.ndarray:
        return self._vectors[sha]

    def put_many(self, shas: list[str], vectors: np.ndarray) -> None:
        if not shas:
            return
        for k, v in zip(shas, vectors):
            self._vectors[k] = np.asarray(v, dtype=np.float32)
        if self.dir is None:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        n = len(list(self.dir.glob("shard_*.npz")))
        tmp = self.dir / f"shard_{n:06d}.tmp.npz"
        np.savez(tmp, keys=np.array(shas), vectors=np.asarray(vectors, dtype=np.float32))
        tmp.replace(self.dir / f"shard_{n:06d}.npz")
        (self.dir / "model.json").write_text(json.dumps({"model_id": self.model_id}), encoding="utf-8")


def embed_missing(embedder: Embedder, cache: EmbeddingCache, texts_by_sha: dict[str, str],
                  batch_size: int = DEFAULT_BATCH, progress=None) -> dict[str, int]:
    """Embed every text whose hash is not cached yet; returns counts and seconds spent."""
    todo = [s for s in texts_by_sha if s not in cache]
    t0 = time.monotonic()
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        cache.put_many(batch, embedder.embed([texts_by_sha[s] for s in batch]))
        if progress is not None:
            progress(min(i + batch_size, len(todo)), len(todo))
    return {"requested": len(texts_by_sha), "embedded": len(todo), "cached": len(texts_by_sha) - len(todo),
            "seconds": round(time.monotonic() - t0, 2)}


def index_chunks(store: VectorStore, cache: EmbeddingCache, chunks: Iterable[Chunk], variant: str) -> int:
    """Upsert cached vectors for `chunks` (in one variant) into `store`. Every text must
    already be in the cache (`embed_missing` first)."""
    records = []
    for c in chunks:
        t = c.text(variant)
        records.append(VectorRecord(c.chunk_id, cache.get(t.content_sha256),
                                    c.metadata(variant, cache.model_id, t.content_sha256)))
    store.upsert(records)
    return len(records)


def dense_scores(store: VectorStore, query_vector: np.ndarray, range_key: str, variant: str, model_id: str,
                 n: int) -> dict[str, float]:
    """candidate_id -> cosine similarity for every chunk of the range (k = n = range size)."""
    hits = store.search(query_vector, {"embedding_model": model_id, "variant": variant, "range_key": range_key}, k=n)
    return {h.metadata["candidate_id"]: h.score for h in hits}
