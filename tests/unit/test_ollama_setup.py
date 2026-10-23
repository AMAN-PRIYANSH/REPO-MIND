"""CP5b task 0b: the Ollama install check is a real generate call, with a repair step (no server needed)."""

import io
import json
import urllib.error

import pytest

from vulntrace.llm import ollama_setup as o


class Resp:
    def __init__(self, payload):
        self._b = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_probe_ok_when_the_server_returns_a_response():
    seen = {}

    def opener(req, timeout):
        seen["url"], seen["body"], seen["timeout"] = req.full_url, json.loads(req.data), timeout
        return Resp({"response": "ok", "done": True})

    assert o.probe_generate("llama3.1:8b", opener=opener, timeout=5) is None
    assert seen["url"].endswith("/api/generate") and seen["body"]["model"] == "llama3.1:8b"
    assert seen["body"]["options"]["num_predict"] == 1 and seen["body"]["stream"] is False


def test_probe_reports_http_500_with_the_servers_first_line():
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 500, "x", {}, io.BytesIO(b'{"error":"llama runner missing"}\nmore'))

    msg = o.probe_generate("m", opener=opener)
    assert msg.startswith("HTTP 500") and "llama runner missing" in msg and "more" not in msg


@pytest.mark.parametrize("exc", [ConnectionRefusedError("refused"), TimeoutError("slow")])
def test_probe_reports_connection_problems(exc):
    def opener(req, timeout):
        raise exc

    assert type(exc).__name__ in o.probe_generate("m", opener=opener)


def test_probe_rejects_a_reply_without_a_response_field():
    assert "unexpected" in o.probe_generate("m", opener=lambda req, timeout: Resp({"models": []}))
    assert o.probe_generate("m", opener=lambda req, timeout: Resp(b"not json")) is not None


def test_ensure_working_does_not_repair_a_working_server():
    calls = []
    assert o.ensure_working(lambda: None, lambda: calls.append("repair"), log=lambda s: None) == 0
    assert calls == []


def test_ensure_working_repairs_once_then_succeeds():
    state = {"broken": True}
    log = []

    def repair():
        state["broken"] = False

    n = o.ensure_working(lambda: "HTTP 500: runner" if state["broken"] else None, repair, log=log.append)
    assert n == 1 and any("HTTP 500" in line for line in log)


def test_ensure_working_stops_with_the_last_problem_when_repair_does_not_help():
    repairs = []
    with pytest.raises(o.OllamaSetupError, match="HTTP 500: still broken"):
        o.ensure_working(lambda: "HTTP 500: still broken", lambda: repairs.append(1), max_repairs=2, log=lambda s: None)
    assert len(repairs) == 2


def test_ensure_working_with_no_repairs_allowed_fails_at_once():
    with pytest.raises(o.OllamaSetupError):
        o.ensure_working(lambda: "down", lambda: None, max_repairs=0, log=lambda s: None)
