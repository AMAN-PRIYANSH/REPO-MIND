"""The one retriever S1 and HyDE may use (CP5 task 0c), read from `fixed_retriever.json`.

The file is data, not a command-line option: the evaluation commands call `load()` and have no
flag to name another retriever, so a CP5 number cannot silently come from a different one.
"""

import json
from dataclasses import dataclass
from importlib import resources

FILE_NAME = "fixed_retriever.json"


@dataclass(frozen=True)
class FixedRetriever:
    config: str
    variant: str
    secondary_config: str | None
    default_k: int
    ablation_k: tuple[int, ...]


def load() -> FixedRetriever:
    raw = json.loads(resources.files("vulntrace.retrieval").joinpath(FILE_NAME).read_text(encoding="utf-8"))
    if raw.get("reranker") is not None:
        raise ValueError("CP5 fixes the retriever without a reranker")
    return FixedRetriever(config=raw["config"], variant=raw["variant"], secondary_config=raw.get("secondary_config"),
                          default_k=int(raw["default_k"]), ablation_k=tuple(int(k) for k in raw.get("ablation_k", ())))
