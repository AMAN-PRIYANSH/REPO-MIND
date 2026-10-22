from vulntrace.llm.models_config import (MODELS, contamination_bucket, headline_bucket, resolve)


def test_buckets_with_a_documented_cutoff():
    c = "2023-12-31"
    assert contamination_bucket("2024-01-02T10:00:00Z", c) == "post"
    assert contamination_bucket("2023-12-31T23:00:00Z", c) == "pre"   # the cutoff day itself is not clean
    assert contamination_bucket("2021-03-04", c) == "pre"
    assert contamination_bucket(None, c) == "undated" and contamination_bucket("", c) == "undated"


def test_without_a_documented_cutoff_every_dated_case_is_possibly_seen():
    assert contamination_bucket("2026-09-01", None) == "possibly_seen"
    assert contamination_bucket(None, None) == "undated"
    assert headline_bucket(None) is None and headline_bucket("2023-12-31") == "post"


def test_at_most_two_models_and_each_cites_its_cutoff_source():
    assert len(MODELS) <= 2
    for m in MODELS.values():
        assert m["cutoff_source"] and m["ollama_tag"]
    assert resolve("llama3.1:8b")["alias"] == "llama3.1-8b" and resolve("mystery:1b")["cutoff"] is None
