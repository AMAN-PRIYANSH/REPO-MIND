"""LLMClient: endpoint rule (zero cost), the real HTTP client against a local stub server, and the fake."""

import http.server
import json
import threading

import pytest

from vulntrace.models import fakes
from vulntrace.models.llm import (DEFAULT_BASE_URL, ENV_ALLOWED_HOST, PAID_API_HOSTS, EndpointError, LLMError,
                                  LLMSettings, OpenAICompatClient, check_endpoint, is_loopback_host)

REQUIRED_PAID = ("api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com", "api.mistral.ai",
                 "api.cohere.com", "api.groq.com", "openrouter.ai", "api.together.xyz", "api.deepseek.com")


# --- endpoint rule ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", [DEFAULT_BASE_URL, "http://localhost:8000/v1", "http://127.0.0.1:11434/v1",
                                 "http://127.5.6.7/v1", "http://[::1]:11434/v1", "http://LOCALHOST:11434/v1/",
                                 "http://localhost./v1", "http://[::ffff:127.0.0.1]:1/v1"])
def test_loopback_hosts_are_accepted(url):
    assert check_endpoint(url, {}).startswith("http")


@pytest.mark.parametrize("host", REQUIRED_PAID)
def test_every_listed_paid_host_is_rejected(host):
    for url in (f"https://{host}/v1", f"https://{host}:443/v1", f"https://{host.upper()}/v1", f"https://{host}./v1",
                f"https://{host.title()}:8443/v1", f"http://user@{host}/v1", f"https://sub.{host}/v1",
                f"http://localhost@{host}/v1"):
        with pytest.raises(EndpointError):
            check_endpoint(url, {})


@pytest.mark.parametrize("host", REQUIRED_PAID)
def test_paid_hosts_stay_rejected_even_when_the_environment_names_them(host):
    for named in (host, host.upper(), host + "."):
        with pytest.raises(EndpointError):
            check_endpoint(f"https://{host}/v1", {ENV_ALLOWED_HOST: named})


def test_required_hosts_are_in_the_list():
    assert set(REQUIRED_PAID) <= set(PAID_API_HOSTS)


def test_non_loopback_host_needs_the_exact_host_in_the_environment():
    url = "http://gpu-box.lan:11434/v1"
    with pytest.raises(EndpointError):
        check_endpoint(url, {})
    with pytest.raises(EndpointError):
        check_endpoint(url, {ENV_ALLOWED_HOST: "other-box.lan"})
    with pytest.raises(EndpointError):
        check_endpoint("http://evil.gpu-box.lan/v1", {ENV_ALLOWED_HOST: "gpu-box.lan"})
    assert check_endpoint(url, {ENV_ALLOWED_HOST: "GPU-box.lan."}) == url


@pytest.mark.parametrize("url", ["ftp://localhost/v1", "localhost:11434/v1", "http:///v1", "http://localhost:notaport/v1",
                                 "http://user:pw@localhost/v1", "http://localhost.evil.com/v1", "http://2130706433/v1",
                                 "http://0x7f.0.0.1/v1", "http://127.0.0.1.evil.com/v1"])
def test_odd_or_look_alike_urls_are_rejected(url):
    with pytest.raises(EndpointError):
        check_endpoint(url, {})


def test_is_loopback_host():
    assert is_loopback_host("localhost") and is_loopback_host("127.0.0.1") and is_loopback_host("::1")
    assert not is_loopback_host("192.168.0.2") and not is_loopback_host("0.0.0.0")


def test_client_constructor_applies_the_rule():
    with pytest.raises(EndpointError):
        OpenAICompatClient("m", base_url="https://api.openai.com/v1")


# --- real client against a stub server on 127.0.0.1 -------------------------------------------------
class _Handler(http.server.BaseHTTPRequestHandler):
    seen: list = []
    redirect = False

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send({"models": [{"name": "stub:7b", "digest": "abc123"}]})
        else:
            self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append(body)
        if type(self).redirect:
            self.send_response(302)
            self.send_header("Location", "https://api.openai.com/v1/chat/completions")
            self.end_headers()
            return
        if body["model"] == "boom":
            self._send({"error": "no such model"}, 404)
            return
        self._send({"choices": [{"message": {"content": '{"selected": ["c1"], "abstain": false}'},
                                 "finish_reason": "stop"}], "usage": {"prompt_tokens": 11, "completion_tokens": 7}})


@pytest.fixture
def stub():
    _Handler.seen, _Handler.redirect = [], False
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1", _Handler
    srv.shutdown()


def test_real_client_records_provenance(stub):
    url, h = stub
    c = OpenAICompatClient("stub:7b", base_url=url)
    r = c.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                   LLMSettings(temperature=0.0, seed=3, max_tokens=50, json_mode=True))
    assert r.text.startswith("{") and (r.input_tokens, r.output_tokens) == (11, 7)
    assert r.model == "stub:7b" and r.model_digest == "abc123" and r.latency_s >= 0
    assert r.settings == {"temperature": 0.0, "seed": 3, "max_tokens": 50, "json_mode": True}
    body = h.seen[0]
    assert (body["temperature"], body["seed"], body["max_tokens"]) == (0.0, 3, 50)
    assert body["response_format"] == {"type": "json_object"} and body["stream"] is False
    assert c.info()["model_digest"] == "abc123"


def test_http_error_is_an_llm_error_not_an_invalid_answer(stub):
    url, _ = stub
    with pytest.raises(LLMError) as e:
        OpenAICompatClient("boom", base_url=url).complete([{"role": "user", "content": "u"}])
    assert e.value.code == "HTTP_ERROR"


def test_redirects_are_never_followed(stub):
    url, h = stub
    h.redirect = True
    with pytest.raises(LLMError) as e:
        OpenAICompatClient("stub:7b", base_url=url).complete([{"role": "user", "content": "u"}])
    assert e.value.code == "REDIRECT"


def test_unreachable_server_is_a_connection_error():
    with pytest.raises(LLMError) as e:
        OpenAICompatClient("m", base_url="http://127.0.0.1:1/v1", timeout=2).complete([{"role": "user", "content": "u"}])
    assert e.value.code == "CONNECTION"


# --- fake -------------------------------------------------------------------------------------
def test_fake_client_is_scripted_by_request_hash_and_supports_a_retry_sequence():
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    key = fakes.request_key(msgs)
    f = fakes.FakeLLMClient({key: [fakes.RESP_INVALID_JSON, fakes.resp_select(["c1"])]})
    assert f.complete(msgs).text == fakes.RESP_INVALID_JSON
    retry = msgs + [{"role": "assistant", "content": "x"}, {"role": "user", "content": "fix"}]
    assert f.complete(retry).text == fakes.resp_select(["c1"])  # same request key
    assert len(f.calls) == 2 and f.complete(msgs).text == fakes.resp_select(["c1"])  # last repeats
    with pytest.raises(KeyError):
        f.complete([{"role": "system", "content": "other"}, {"role": "user", "content": "u"}])


def test_fake_canned_responses_cover_the_failure_modes():
    assert fakes.RESP_EMPTY == "" and fakes.RESP_INJECTED.count("c999") == 1
    with pytest.raises(ValueError):
        json.loads(fakes.RESP_INVALID_JSON)
