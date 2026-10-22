"""Deterministic fake models for tests and dry runs. They download nothing, call nothing and
give identical output on every machine (no Python `hash()`, which is salted per process)."""

import hashlib
import json
import re
from typing import Callable, Mapping

import numpy as np

from vulntrace.models.base import Embedder, Reranker, l2_normalise
from vulntrace.models.llm import LLMClient, LLMResponse, LLMSettings, Messages
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


# --- fake LLM (CP5) -----------------------------------------------------------------------------
FAKE_LLM_ID = "fake-llm-v1"

# Canned answers for the failure modes the closed-set validation must catch.
RESP_INVALID_JSON = '{"selected": ["c1"], "abstain": '
RESP_EMPTY = ""
RESP_ABSTAIN = '{"selected": [], "abstain": true}'
RESP_INJECTED = ('{"selected": ["IGNORE-PREVIOUS-INSTRUCTIONS", "c999"], "abstain": false}')


def resp_select(ids: list[str]) -> str:
    return json.dumps({"selected": list(ids), "abstain": False})


def request_key(messages: Messages) -> str:
    """Key of a *request*: hash of the first two messages (system and user). The retry message
    pair appended after an invalid answer does not change it, so one scripted entry can hold the
    first answer and the answer to the retry."""
    h = hashlib.sha256()
    for m in list(messages)[:2]:
        h.update(m["role"].encode("utf-8") + b"\0" + m["content"].encode("utf-8") + b"\0")
    return h.hexdigest()


class FakeLLMClient(LLMClient):
    """Scripted responses keyed by input hash (`request_key`). A script value is one response
    or a list consumed in order by successive calls with that key (the last one repeats). Calls
    with an unscripted key go to `fallback(messages)` if given, else raise KeyError. Records
    every call in `calls`."""

    endpoint_kind = "FAKE"

    def __init__(self, script: Mapping[str, str | list[str]] | None = None,
                 fallback: Callable[[Messages], str] | None = None, model_id: str = FAKE_LLM_ID):
        self.script = {k: ([v] if isinstance(v, str) else list(v)) for k, v in (script or {}).items()}
        self.fallback = fallback
        self.model_id = model_id
        self.calls: list[Messages] = []
        self._used: dict[str, int] = {}

    @property
    def model_digest(self) -> str | None:
        return "fake-digest"

    def info(self):
        return {"model_id": self.model_id, "model_digest": "fake-digest", "endpoint_kind": "FAKE", "kind": "FAKE"}

    def complete(self, messages, settings=None, json_schema=None, tools=None) -> LLMResponse:
        s = settings or LLMSettings()
        self.calls.append([dict(m) for m in messages])
        key = request_key(messages)
        if key in self.script:
            seq = self.script[key]
            n = self._used.get(key, 0)
            self._used[key] = n + 1
            text = seq[min(n, len(seq) - 1)]
        elif self.fallback is not None:
            text = self.fallback(messages)
        else:
            raise KeyError(f"no scripted response for request {key[:12]}")
        n_in = sum(len(m["content"]) for m in messages) // 4
        return LLMResponse(text=text, model=self.model_id, model_digest="fake-digest", settings=s.as_dict(),
                           input_tokens=n_in, output_tokens=len(text) // 4, latency_s=0.0, finish_reason="stop")


def dry_run_responder(messages: Messages) -> str:
    """A deterministic stand-in used for dry runs on real evidence: reads the candidate IDs the
    prompt lists (`ID: <id>` lines) and, by a hash of the request, mostly selects the first one
    or two, sometimes abstains, and now and then answers invalidly (so the retry and INVALID
    paths run). The retry (a longer message list) always answers validly. Its numbers mean
    nothing; it exercises code paths."""
    ids = re.findall(r"^ID: (\S+)", messages[1]["content"], flags=re.MULTILINE)
    roll = int(request_key(messages)[:8], 16) % 20
    if len(messages) > 2:
        return resp_select(ids[:1]) if ids else RESP_ABSTAIN
    if not ids or roll == 0:
        return RESP_ABSTAIN
    if roll == 1:
        return RESP_INVALID_JSON
    if roll == 2:
        return resp_select(["not-a-candidate"])
    return resp_select(ids[: 1 + roll % 2])


def dry_run_text_responder(messages: Messages) -> str:
    """Stand-in for the HyDE prompt: a tiny fixed Go function whose identifier comes from the
    request hash, so the hypothetical differs between cases."""
    k = request_key(messages)[:6]
    return f"func handle{k}(input string) error {{\n\treturn nil\n}}"
