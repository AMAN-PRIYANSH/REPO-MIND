import json

from vulntrace.models import fakes
from vulntrace.models.llm import LLMSettings
from vulntrace.models.llm_cache import CachedLLMClient, LLMCache, cache_key

MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]


def test_miss_then_hit_calls_the_model_once(tmp_path):
    inner = fakes.FakeLLMClient(fallback=lambda m: fakes.resp_select(["c1"]))
    c = CachedLLMClient(inner, LLMCache(tmp_path))
    first = c.complete(MSGS)
    second = c.complete(MSGS)
    assert (c.misses, c.hits, len(inner.calls)) == (1, 1, 1)
    assert first.cached is False and second.cached is True
    assert second.text == first.text and second.input_tokens == first.input_tokens
    assert len(LLMCache(tmp_path)) == 1  # a fresh object on the same directory sees it


def test_key_depends_on_model_settings_and_messages():
    s = LLMSettings()
    base = cache_key("m@d", s, MSGS)
    assert base == cache_key("m@d", LLMSettings(), [dict(m) for m in MSGS])
    assert base != cache_key("m@d2", s, MSGS)
    assert base != cache_key("m2@d", s, MSGS)
    assert base != cache_key("m@d", LLMSettings(seed=8), MSGS)
    assert base != cache_key("m@d", LLMSettings(temperature=0.2), MSGS)
    assert base != cache_key("m@d", s, MSGS[:1] + [{"role": "user", "content": "u2"}])


def test_different_settings_do_not_share_an_entry(tmp_path):
    inner = fakes.FakeLLMClient(fallback=lambda m: "x")
    c = CachedLLMClient(inner, LLMCache(tmp_path))
    c.complete(MSGS, LLMSettings(seed=1))
    c.complete(MSGS, LLMSettings(seed=2))
    assert (c.misses, c.hits) == (2, 0)


def test_entry_holds_prompt_and_raw_response_on_disk_only(tmp_path):
    inner = fakes.FakeLLMClient(fallback=lambda m: "RAW-RESPONSE")
    CachedLLMClient(inner, LLMCache(tmp_path)).complete(MSGS)
    (path,) = list(tmp_path.glob("*/*.json"))
    entry = json.loads(path.read_text())
    assert entry["messages"][1]["content"] == "u" and entry["response"]["text"] == "RAW-RESPONSE"


def test_corrupt_or_foreign_entry_is_a_miss_not_a_crash(tmp_path):
    cache = LLMCache(tmp_path)
    key = cache_key("m@d", LLMSettings(), MSGS)
    p = cache._path(key)
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert cache.get(key) is None
    p.write_text(json.dumps({"schema_version": "0"}))
    assert cache.get(key) is None


def test_errors_are_not_cached(tmp_path):
    inner = fakes.FakeLLMClient()  # no script, no fallback: raises KeyError
    c = CachedLLMClient(inner, LLMCache(tmp_path))
    try:
        c.complete(MSGS)
    except KeyError:
        pass
    assert len(LLMCache(tmp_path)) == 0
