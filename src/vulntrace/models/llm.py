"""`LLMClient` (interfaces doc section 4, CP5 deliverable 1).

The real client speaks the OpenAI-compatible chat-completions protocol over plain HTTP to a
*local* server (Ollama by default), using only the standard library. Zero cost is enforced
here, not by convention:

- Only loopback hosts are accepted by default.
- Known paid API hostnames (and their sub-domains) are rejected always, even if the user names
  them in the environment variable that otherwise allows one extra host.
- A non-loopback host needs `VULNTRACE_LLM_ALLOWED_HOST` set to exactly that host (and is still
  rejected if it is on the paid list).
- Redirects are never followed and system proxy settings are ignored, so a local server cannot
  bounce a request to another host and traffic cannot leave through a proxy.

Every response carries the provenance a real call must record: model name, digest, settings,
token counts and latency.
"""

import hashlib
import ipaddress
import json
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

DEFAULT_BASE_URL = "http://localhost:11434/v1"
ENV_ALLOWED_HOST = "VULNTRACE_LLM_ALLOWED_HOST"

# Paid LLM API hostnames. A host is "paid" if it equals one of these or is a sub-domain of one.
PAID_API_HOSTS = (
    "api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com", "api.mistral.ai",
    "api.cohere.com", "api.groq.com", "openrouter.ai", "api.together.xyz", "api.deepseek.com",
    "api.x.ai", "api.perplexity.ai", "api.fireworks.ai", "api.deepinfra.com", "api.replicate.com",
    "api.cerebras.ai", "api.ai21.com", "openai.azure.com", "aiplatform.googleapis.com",
)


class EndpointError(ValueError):
    """The configured endpoint is not allowed (zero-cost rule)."""


class LLMError(Exception):
    """A call failed for infrastructure reasons (server down, HTTP error, unreadable reply).
    Distinct from an *invalid answer*, which is a result, not an error."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


@dataclass(frozen=True)
class LLMSettings:
    temperature: float = 0.0
    seed: int = 7
    max_tokens: int = 1024
    json_mode: bool = False  # ask the server for a JSON object (OpenAI `response_format`)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LLMResponse:
    text: str
    model: str
    model_digest: str | None
    settings: dict[str, Any]
    input_tokens: int | None
    output_tokens: int | None
    latency_s: float
    finish_reason: str | None = None
    cached: bool = False

    @property
    def response_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def provenance(self) -> dict[str, Any]:
        """Everything about the call except the text (safe to commit)."""
        return {"model": self.model, "model_digest": self.model_digest, "settings": self.settings,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "latency_s": round(self.latency_s, 3), "finish_reason": self.finish_reason,
                "cached": self.cached, "response_sha256": self.response_sha256}


Messages = list[Mapping[str, str]]


class LLMClient(ABC):
    model_id: str

    @property
    def model_digest(self) -> str | None:
        return None

    @abstractmethod
    def complete(self, messages: Messages, settings: LLMSettings | None = None, json_schema: dict | None = None,
                 tools: list | None = None) -> LLMResponse:
        """One chat completion. `json_schema`/`tools` are part of the interface for later
        checkpoints; CP5 passes neither."""

    def identity(self) -> str:
        """What makes two clients interchangeable for caching: the model name plus its digest."""
        return f"{self.model_id}@{self.model_digest or 'unknown'}"

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "model_digest": self.model_digest}


# --- endpoint rule ---------------------------------------------------------------------------
def normalise_host(host: str) -> str:
    return host.strip().lower().rstrip(".")


def is_loopback_host(host: str) -> bool:
    h = normalise_host(host)
    if h == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def is_paid_host(host: str) -> bool:
    h = normalise_host(host)
    return any(h == p or h.endswith("." + p) for p in PAID_API_HOSTS)


def check_endpoint(url: str, environ: Mapping[str, str] | None = None) -> str:
    """Return `url` (without a trailing slash) if the endpoint rule allows it, else raise
    `EndpointError`."""
    env = os.environ if environ is None else environ
    try:
        parsed = urlparse(url.strip())
        host, _port = parsed.hostname, parsed.port  # .port raises ValueError on a bad port
    except ValueError as exc:
        raise EndpointError(f"unreadable endpoint URL {url!r}: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise EndpointError(f"endpoint must be an http(s) URL, got {url!r}")
    if not host:
        raise EndpointError(f"endpoint has no host: {url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise EndpointError("credentials in the endpoint URL are not accepted (no paid or authenticated API is used)")
    if is_paid_host(host):
        raise EndpointError(f"{normalise_host(host)} is a known paid API host; this project never calls paid APIs")
    if not is_loopback_host(host):
        allowed = normalise_host(env.get(ENV_ALLOWED_HOST, ""))
        if not allowed or allowed != normalise_host(host):
            raise EndpointError(f"{normalise_host(host)} is not a loopback host; only localhost endpoints are accepted "
                                f"unless {ENV_ALLOWED_HOST} names exactly this host")
    return url.strip().rstrip("/")


# --- real client -----------------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LLMError("REDIRECT", f"the server answered with a redirect ({code}); redirects are never followed")


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


class OpenAICompatClient(LLMClient):
    """Chat completions against an OpenAI-compatible server on this machine (Ollama)."""

    endpoint_kind = "OLLAMA"

    def __init__(self, model: str, base_url: str = DEFAULT_BASE_URL, settings: LLMSettings | None = None,
                 timeout: float = 900.0, environ: Mapping[str, str] | None = None):
        self._environ = environ
        self.base_url = check_endpoint(base_url, environ)
        self.model_id = model
        self.default_settings = settings or LLMSettings()
        self.timeout = timeout
        self._digest: str | None = None
        self._digest_looked_up = False
        self.digest_error: str | None = None

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        check_endpoint(url, self._environ)  # re-checked on every request, not only at construction
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with _opener().open(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except LLMError:
            raise
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise LLMError("HTTP_ERROR", f"{exc.code} from {url}: {detail}") from exc
        except TimeoutError as exc:
            raise LLMError("TIMEOUT", f"no answer from {url} within {self.timeout}s") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise LLMError("CONNECTION", f"cannot reach {url}: {exc}") from exc
        except ValueError as exc:
            raise LLMError("BAD_RESPONSE", f"{url} did not return JSON: {exc}") from exc

    @property
    def model_digest(self) -> str | None:
        """The digest Ollama reports for this model tag (`/api/tags`), looked up once."""
        if not self._digest_looked_up:
            self._digest_looked_up = True
            root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
            try:
                tags = self._request("GET", root + "/api/tags").get("models", [])
                names = {self.model_id, self.model_id + ":latest"}
                self._digest = next((m.get("digest") for m in tags if m.get("name") in names or m.get("model") in names),
                                    None)
                if self._digest is None:
                    self.digest_error = f"model {self.model_id!r} not listed by {root}/api/tags"
            except LLMError as exc:
                self.digest_error = str(exc)
        return self._digest

    def info(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "model_digest": self.model_digest, "endpoint_kind": self.endpoint_kind,
                "base_url": self.base_url, "digest_error": self.digest_error}

    def complete(self, messages: Messages, settings: LLMSettings | None = None, json_schema: dict | None = None,
                 tools: list | None = None) -> LLMResponse:
        s = settings or self.default_settings
        body: dict[str, Any] = {"model": self.model_id, "messages": [dict(m) for m in messages],
                                "temperature": s.temperature, "seed": s.seed, "max_tokens": s.max_tokens,
                                "stream": False}
        if json_schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": json_schema}
        elif s.json_mode:
            body["response_format"] = {"type": "json_object"}
        if tools:
            body["tools"] = tools
        digest = self.model_digest
        t0 = time.monotonic()
        reply = self._request("POST", self.base_url + "/chat/completions", body)
        latency = time.monotonic() - t0
        try:
            choice = reply["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError("BAD_RESPONSE", f"unexpected reply shape: {str(reply)[:200]}") from exc
        usage = reply.get("usage") or {}
        return LLMResponse(text=text, model=self.model_id, model_digest=digest, settings=s.as_dict(),
                           input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
                           latency_s=latency, finish_reason=choice.get("finish_reason"))
