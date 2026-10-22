"""The open instruction-tuned models CP5 may use (at most two), and their documented training
cutoffs for the contamination split (CP5 deliverables 6 and 7).

Models run through Ollama on the owner's machine or a free Colab T4 at 4-bit. The exact Ollama
tag is a request; the digest the server reports is recorded at run time. If a tag cannot be
pulled the run reports it - it never falls back to a paid API.

`cutoff` is the training-data cutoff *documented by the model's publisher* as an ISO date (the
last day of the documented month), or None when no cutoff is documented, in which case every
case is treated as possibly seen. Each entry cites where the value came from.
"""

from typing import Any

MODELS: dict[str, dict[str, Any]] = {
    "qwen2.5-coder-7b": {
        "ollama_tag": "qwen2.5-coder:7b-instruct", "params": "7B", "quantization": "Ollama default (4-bit)",
        "cutoff": None,
        "cutoff_source": ("Not documented: the official Qwen2.5-Coder model card "
                          "(https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) was not reachable from the build "
                          "session, and third-party listings (e.g. OpenRouter: 'Jun 2024') are not the publisher. "
                          "Treated as undocumented, so every case counts as possibly seen."),
    },
    "llama3.1-8b": {
        "ollama_tag": "llama3.1:8b", "params": "8B", "quantization": "Ollama default (4-bit)",
        "cutoff": "2023-12-31",
        "cutoff_source": ("Meta Llama 3.1 model card, 'Data Freshness: The pretraining data has a cutoff of December 2023' "
                          "(https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct). Read in the build session only "
                          "through third-party copies of the card (search results, 2026-10-22); the owner should "
                          "check the official page."),
    },
}
FAKE_MODEL = "fake"


def resolve(alias_or_tag: str) -> dict[str, Any]:
    """Model entry by alias or by Ollama tag. An unknown tag is allowed (cutoff undocumented)."""
    if alias_or_tag in MODELS:
        return {"alias": alias_or_tag, **MODELS[alias_or_tag]}
    for alias, m in MODELS.items():
        if m["ollama_tag"] == alias_or_tag:
            return {"alias": alias, **m}
    return {"alias": alias_or_tag, "ollama_tag": alias_or_tag, "params": None, "quantization": None, "cutoff": None,
            "cutoff_source": "Unknown model: no documented cutoff; every case counts as possibly seen."}


BUCKET_PRE, BUCKET_POST, BUCKET_UNDATED, BUCKET_POSSIBLY_SEEN = "pre", "post", "undated", "possibly_seen"


def contamination_bucket(created: str | None, cutoff: str | None) -> str:
    """`post`: created after the model's documented cutoff (cannot be in its training data);
    `pre`: on or before it; `undated`: the report has no created date; `possibly_seen`: the
    model's cutoff is undocumented, so no dated case can be called clean."""
    if not created:
        return BUCKET_UNDATED
    if cutoff is None:
        return BUCKET_POSSIBLY_SEEN
    return BUCKET_POST if created[:10] > cutoff[:10] else BUCKET_PRE


def headline_bucket(cutoff: str | None) -> str | None:
    """The bucket the headline numbers use; None means 'all cases, flagged as possibly seen'."""
    return BUCKET_POST if cutoff else None
