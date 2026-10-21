"""Short names for the models CP4 may use (open question Q6: at most two embedders and two
rerankers). All are free, open models from Hugging Face, loaded locally with
sentence-transformers - never a paid API. Real models are only constructed when asked for, so
importing this module never imports torch or sentence-transformers.

Choices:
- `bge-small`: BAAI/bge-small-en-v1.5 - small (33M) general English text embedder; documented
  query instruction prefix.
- `codesearch`: flax-sentence-embeddings/st-codesearch-distilroberta-base - small (82M)
  code-oriented embedder trained for natural-language-to-code search on CodeSearchNet (which
  includes Go); a native sentence-transformers model, so no remote code runs in Colab.
- `minilm`: cross-encoder/ms-marco-MiniLM-L-6-v2 - small (22M) general passage reranker.
- `bge-reranker`: BAAI/bge-reranker-base - larger (278M) general reranker (the second, optional).

Exact revisions are recorded at run time (the resolved Hugging Face commit), and can be pinned
with `revision`.
"""

from typing import Any

from vulntrace.models.fakes import FakeEmbedder, FakeReranker

EMBEDDERS: dict[str, dict[str, Any]] = {
    "fake": {"kind": "FAKE"},
    "bge-small": {"kind": "ST", "hf_id": "BAAI/bge-small-en-v1.5",
                  "query_prefix": "Represent this sentence for searching relevant passages: ", "max_seq_length": 512},
    "codesearch": {"kind": "ST", "hf_id": "flax-sentence-embeddings/st-codesearch-distilroberta-base",
                   "query_prefix": "", "max_seq_length": 512},
}
RERANKERS: dict[str, dict[str, Any]] = {
    "fake": {"kind": "FAKE"},
    "minilm": {"kind": "CE", "hf_id": "cross-encoder/ms-marco-MiniLM-L-6-v2", "max_length": 512},
    "bge-reranker": {"kind": "CE", "hf_id": "BAAI/bge-reranker-base", "max_length": 512},
}


def make_embedder(name: str, device: str | None = None, revision: str | None = None, batch_size: int = 64):
    spec = EMBEDDERS[name]
    if spec["kind"] == "FAKE":
        return FakeEmbedder()
    from vulntrace.models.st_models import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(spec["hf_id"], query_prefix=spec["query_prefix"], device=device,
                                       revision=revision, batch_size=batch_size,
                                       max_seq_length=spec["max_seq_length"])


def make_reranker(name: str, device: str | None = None, revision: str | None = None, batch_size: int = 32):
    spec = RERANKERS[name]
    if spec["kind"] == "FAKE":
        return FakeReranker()
    from vulntrace.models.st_models import CrossEncoderReranker

    return CrossEncoderReranker(spec["hf_id"], device=device, revision=revision, batch_size=batch_size,
                                max_length=spec["max_length"])
