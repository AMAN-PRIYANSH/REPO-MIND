"""Check that a freshly installed Ollama server really generates text (CP5b task 0b).

`which ollama` only proves the CLI exists. A partial install (the CLI without its runner
`llama-server`) answers `/api/tags` but fails every generate call with HTTP 500, and a CP5
notebook run lost time to exactly that. `ensure_working` takes one tiny generate call as the
test and, if it fails, runs the caller's repair (reinstall and restart) before trying again.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable

DEFAULT_URL = "http://127.0.0.1:11434"


class OllamaSetupError(RuntimeError):
    pass


def probe_generate(tag: str, base_url: str = DEFAULT_URL, timeout: float = 600.0,
                   opener: Callable = urllib.request.urlopen) -> str | None:
    """One tiny generate call (one token). None means the server generated text; otherwise the
    first line of what went wrong. The first call loads the model, so the timeout is long."""
    body = json.dumps({"model": tag, "prompt": "Say ok.", "stream": False, "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with opener(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace").strip().splitlines()[0][:300]
        except Exception:
            pass
        return f"HTTP {exc.code}: {detail}".rstrip(": ")
    except Exception as exc:  # connection refused, timeout, bad JSON ...
        return f"{type(exc).__name__}: {str(exc)[:300]}"
    if not isinstance(data, dict) or "response" not in data:
        return f"unexpected generate response: {str(data)[:200]}"
    return None


def ensure_working(probe: Callable[[], str | None], repair: Callable[[], None], max_repairs: int = 1,
                   log: Callable[[str], None] = print) -> int:
    """Run `probe`; while it reports a problem and repairs remain, call `repair` and probe
    again. Returns the number of repairs used. Raises OllamaSetupError, with the last problem,
    if the server still does not generate - the run stops here instead of failing call by call."""
    problem = probe()
    repairs = 0
    while problem is not None and repairs < max_repairs:
        log(f"ollama generate probe failed ({problem}); reinstalling and restarting (repair {repairs + 1}/{max_repairs})")
        repair()
        repairs += 1
        problem = probe()
    if problem is not None:
        raise OllamaSetupError(f"Ollama does not generate text after {repairs} repair(s): {problem}")
    log("ollama generate probe: ok" + (f" (after {repairs} repair)" if repairs else ""))
    return repairs
