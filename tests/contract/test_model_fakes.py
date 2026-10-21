"""The fake embedder and reranker obey the same interface checks the Colab notebook runs on
the real models (vulntrace.models.contract)."""

import sys

import numpy as np

from vulntrace.models import contract
from vulntrace.models.fakes import FakeEmbedder, FakeReranker
from vulntrace.models.registry import EMBEDDERS, RERANKERS, make_embedder, make_reranker


def test_fake_embedder_obeys_the_embedder_contract():
    contract.check_embedder(FakeEmbedder())
    contract.check_embedder(FakeEmbedder(dim=8))


def test_fake_reranker_obeys_the_reranker_contract():
    contract.check_reranker(FakeReranker())


def test_fake_embedder_is_deterministic_and_similarity_follows_shared_tokens():
    e1, e2 = FakeEmbedder(), FakeEmbedder()
    texts = ["func ParseRequest(r *http.Request)", "func WriteFile(path string)"]
    assert np.array_equal(e1.embed(texts), e2.embed(texts))
    q = e1.embed_query("parse request")
    v = e1.embed(texts)
    assert float(v[0] @ q) > float(v[1] @ q)


def test_fake_reranker_is_token_overlap():
    r = FakeReranker()
    assert r.score("parse http request", ["ParseRequest http", "nothing", ""]) == [1.0, 0.0, 0.0]
    assert r.score("", ["x"]) == [0.0]


def test_registry_fakes_need_no_ml_libraries():
    make_embedder("fake")
    make_reranker("fake")
    assert "sentence_transformers" not in sys.modules and "torch" not in sys.modules


def test_registry_lists_at_most_two_real_models_of_each_kind_and_no_paid_hosts():
    real_e = [k for k, v in EMBEDDERS.items() if v["kind"] != "FAKE"]
    real_r = [k for k, v in RERANKERS.items() if v["kind"] != "FAKE"]
    assert len(real_e) <= 2 and len(real_r) <= 2  # open question Q6
    for spec in [*EMBEDDERS.values(), *RERANKERS.values()]:
        assert "http" not in spec.get("hf_id", "")  # Hugging Face model ids, not API endpoints
