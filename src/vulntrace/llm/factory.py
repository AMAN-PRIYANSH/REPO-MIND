"""Build the `LLMClient` an evaluation command uses: the real local client behind the disk
cache, or the fake (`--model fake`, dry runs)."""

from pathlib import Path

from vulntrace.llm import models_config
from vulntrace.models import fakes
from vulntrace.models.llm import DEFAULT_BASE_URL, LLMClient, OpenAICompatClient
from vulntrace.models.llm_cache import CachedLLMClient, LLMCache


def _fake_responder(messages):
    if "code search engine" in messages[0]["content"]:
        return fakes.dry_run_text_responder(messages)
    return fakes.dry_run_responder(messages)


def make_client(model: str, base_url: str = DEFAULT_BASE_URL, cache_dir: Path | None = None) -> LLMClient:
    if model == models_config.FAKE_MODEL:
        return fakes.FakeLLMClient(fallback=_fake_responder)
    inner = OpenAICompatClient(models_config.resolve(model)["ollama_tag"], base_url=base_url)
    return CachedLLMClient(inner, LLMCache(cache_dir)) if cache_dir is not None else inner
