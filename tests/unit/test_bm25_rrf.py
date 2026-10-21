"""BM25, code tokenisation, RRF and tie-breaking on hand-computed examples (CP4 D3, D5)."""

import math

import pytest

from vulntrace.retrieval import fusion, ranking
from vulntrace.retrieval.bm25 import BM25
from vulntrace.retrieval.tokenize import code_tokens


def test_tokeniser_splits_camel_snake_dots_and_slashes():
    assert code_tokens("readFile") == ["read", "file", "readfile"]
    assert code_tokens("HTTPServer") == ["http", "server", "httpserver"]
    assert code_tokens("parse_http2_frame") == ["parse", "http", "2", "frame", "parse_http2_frame"]
    assert code_tokens("github.com/rclone/rclone/backend/local.Fs.Move") == [
        "github", "com", "rclone", "rclone", "backend", "local", "fs", "move"]
    assert code_tokens("func (s *Server) ServeHTTP(w") == [
        "func", "s", "server", "serve", "http", "servehttp", "w"]


def test_tokeniser_keeps_numbers_and_has_no_stop_words():
    assert code_tokens("if x == 0 { return nil }") == ["if", "x", "0", "return", "nil"]
    assert code_tokens("CVE-2026-1234") == ["cve", "2026", "1234"]
    assert code_tokens("") == []
    assert code_tokens("héllo") == ["h", "llo"]  # non-ASCII letters separate words (documented)


# Corpus: d0 = [a, b] (|d|=2), d1 = [a] (|d|=1), d2 = [c, c, b] (|d|=3). N = 3, avgdl = 2.
DOCS = [["a", "b"], ["a"], ["c", "c", "b"]]
IDF_DF2 = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))  # ln(1.6) = 0.470004 for df = 2


def test_bm25_idf_hand_computed():
    bm = BM25(DOCS)
    assert bm.idf("a") == pytest.approx(0.4700036292)
    assert bm.idf("c") == pytest.approx(math.log(1 + 2.5 / 1.5))  # df = 1: ln(2.6667) = 0.980829
    assert bm.idf("zzz") == pytest.approx(math.log(1 + 3.5 / 0.5))  # unseen: ln(8)


def test_bm25_scores_hand_computed():
    bm = BM25(DOCS)
    s = bm.scores(["b"])
    # d0: tf=1, |d|/avgdl=1 -> norm = 1.2 -> 1*2.2/(1+1.2) = 1.0
    assert s[0] == pytest.approx(IDF_DF2 * 1.0)
    assert s[1] == 0.0
    # d2: tf=1, |d|/avgdl=1.5 -> norm = 1.2*(0.25+1.125) = 1.65 -> 2.2/2.65 = 0.830189
    assert s[2] == pytest.approx(IDF_DF2 * 2.2 / 2.65)
    assert s[2] == pytest.approx(0.390192, abs=1e-6)


def test_bm25_query_term_frequency_is_a_linear_weight():
    bm = BM25(DOCS)
    s = bm.scores(["a", "a"])
    assert s[0] == pytest.approx(2 * IDF_DF2 * 1.0)
    # d1: |d|/avgdl = 0.5 -> norm = 1.2*(0.25+0.375) = 0.75 -> 2.2/1.75 = 1.257143
    assert s[1] == pytest.approx(2 * IDF_DF2 * 2.2 / 1.75)
    assert s[1] == pytest.approx(1.181724, abs=1e-6)
    assert s[2] == 0.0


def test_bm25_term_saturation_and_empty_corpus():
    bm = BM25([["x"] * 1, ["x"] * 10])
    s = bm.scores(["x"])
    assert s[1] > s[0]          # more occurrences score higher...
    assert s[1] < 10 * s[0]     # ...but saturate (k1)
    assert BM25([]).scores(["x"]) == []
    assert BM25([[], []]).scores(["x"]) == [0.0, 0.0]


def test_rrf_hand_computed():
    a = ["x", "y", "z"]
    b = ["y", "z", "x"]
    s = fusion.rrf_scores([a, b], k=60)
    assert s["x"] == pytest.approx(1 / 61 + 1 / 63)
    assert s["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert s["z"] == pytest.approx(1 / 63 + 1 / 62)
    assert fusion.rrf([a, b], group="g") == ["y", "x", "z"]


def test_rrf_item_missing_from_one_ranking_gets_only_its_other_contribution():
    s = fusion.rrf_scores([["x", "y"], ["w"]], k=60)
    assert s == pytest.approx({"x": 1 / 61, "y": 1 / 62, "w": 1 / 61})
    assert fusion.DEFAULT_K == 60


def test_rank_breaks_ties_by_seeded_hash_not_input_order():
    items = [f"r{i}" for i in range(1, 30)]
    r1 = ranking.rank(items, [0.0] * len(items), group="case-a", seed=1)
    r2 = ranking.rank(list(reversed(items)), [0.0] * len(items), group="case-a", seed=1)
    assert r1 == r2                     # independent of input order
    assert r1 != items                  # not candidate order
    assert ranking.rank(items, [0.0] * len(items), group="case-a", seed=2) != r1
    assert ranking.rank(items, [0.0] * len(items), group="case-b", seed=1) != r1
    scored = ranking.rank(["a", "b", "c"], [0.1, 0.9, 0.5], group="g")
    assert scored == ["b", "c", "a"]


def test_random_ranking_is_a_deterministic_permutation():
    items = [f"r{i}" for i in range(1, 101)]
    r = ranking.random_ranking(items, "g", seed=5)
    assert sorted(r) == sorted(items) and r == ranking.random_ranking(items, "g", seed=5)
    with pytest.raises(ValueError):
        ranking.rank(["a"], [1.0, 2.0], "g")
