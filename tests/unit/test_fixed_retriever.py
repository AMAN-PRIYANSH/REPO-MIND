from vulntrace.eval.retrieval import parse_config
from vulntrace.retrieval import fixed
from vulntrace.retrieval.chunking import VARIANTS


def test_fixed_retriever_is_the_cp4_choice_and_parses():
    f = fixed.load()
    assert f.config == "hybrid:bge-small" and f.variant == "code+commits" and f.default_k == 10
    assert f.variant in VARIANTS
    assert parse_config(f.config).kind == "hybrid" and parse_config(f.secondary_config).kind == "bm25"
    assert 5 in f.ablation_k
