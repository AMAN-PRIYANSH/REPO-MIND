"""On-disk response cache for LLM calls (CP5 deliverable 2).

Key = hash of (model identity, settings, messages): identical inputs are never paid for twice,
a re-run is free, and every metric can be recomputed from the cache. Entries hold the full
prompt and raw response, so the cache directory is gitignored (`data/`) and is never copied into
committed results: committed result files carry only parsed selections, validity flags, token
counts and latencies.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from vulntrace.models.llm import LLMClient, LLMResponse, LLMSettings, Messages

SCHEMA_VERSION = "1.0"


def cache_key(identity: str, settings: LLMSettings, messages: Messages) -> str:
    payload = json.dumps({"model": identity, "settings": settings.as_dict(),
                          "messages": [{"role": m["role"], "content": m["content"]} for m in messages]},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMCache:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        try:
            entry = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return entry if entry.get("schema_version") == SCHEMA_VERSION and "response" in entry else None

    def put(self, key: str, messages: Messages, response: LLMResponse) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {"schema_version": SCHEMA_VERSION, "key": key, "messages": [dict(m) for m in messages],
                 "response": {"text": response.text, "model": response.model, "model_digest": response.model_digest,
                              "settings": response.settings, "input_tokens": response.input_tokens,
                              "output_tokens": response.output_tokens, "latency_s": response.latency_s,
                              "finish_reason": response.finish_reason}}
        tmp = p.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)  # atomic: an interrupted run never leaves a half-written entry

    def __len__(self) -> int:
        return sum(1 for _ in self.root.glob("*/*.json")) if self.root.is_dir() else 0


class CachedLLMClient(LLMClient):
    """Wraps a client with the cache. A hit returns the stored response with `cached=True` and
    the original latency; `hits`/`misses` count lookups. LLMErrors are never cached."""

    def __init__(self, inner: LLMClient, cache: LLMCache):
        self.inner, self.cache = inner, cache
        self.model_id = inner.model_id
        self.hits = self.misses = 0

    @property
    def model_digest(self) -> str | None:
        return self.inner.model_digest

    def info(self):
        return self.inner.info()

    def complete(self, messages, settings=None, json_schema=None, tools=None) -> LLMResponse:
        if json_schema is not None or tools:
            return self.inner.complete(messages, settings, json_schema, tools)  # not cached in CP5
        s = settings or getattr(self.inner, "default_settings", None) or LLMSettings()
        key = cache_key(self.inner.identity(), s, messages)
        entry = self.cache.get(key)
        if entry is not None:
            self.hits += 1
            r = entry["response"]
            return LLMResponse(text=r["text"], model=r["model"], model_digest=r["model_digest"], settings=r["settings"],
                               input_tokens=r["input_tokens"], output_tokens=r["output_tokens"],
                               latency_s=r["latency_s"], finish_reason=r.get("finish_reason"), cached=True)
        self.misses += 1
        response = self.inner.complete(messages, s)
        self.cache.put(key, messages, response)
        return response
