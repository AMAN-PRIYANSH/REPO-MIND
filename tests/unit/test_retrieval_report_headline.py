"""The CP4 renderer's headline must not name a winner unless the paired interval against the
runner-up excludes 0 (CP4 review: BM25, dense and hybrid were indistinguishable)."""

from vulntrace.eval.retrieval_report import (Summaries, best_vs_runner_up, headline, method_comparison_pairs)

N = 24


def _cases():
    return {"cutoff": "2026-06-30", "rclone_cluster": "none", "cases": [
        {"id": f"c{i}", "cluster_key": f"k{i}", "size_bucket": ">100", "date_bucket": "post", "n_gold_core": 1,
         "n_gold_core_derived": 1, "query_names_gold": False} for i in range(N)]}


def _run(config, kind, ranks, variant="code+commits"):
    rows = [{"id": f"c{i}", "core": {"first_rank": r, "top_ranks": [r] if r and r <= 20 else []},
             "core_derived": {"first_rank": r, "top_ranks": [r] if r and r <= 20 else []}}
            for i, r in enumerate(ranks)]
    return {"config": config, "kind": kind, "variant": variant, "rows": rows}


def _ranks(pattern):
    return [pattern[i % len(pattern)] for i in range(N)]


def test_equal_methods_give_no_clear_winner():
    r = _ranks([1, 2, 3, 1, 5, 2])
    runs = [_run("bid", "bid", _ranks([9, 7, 12, 30]), "-"), _run("bm25", "bm25", r),
            _run("dense:fake", "dense", list(r)), _run("hybrid:fake", "hybrid", list(r))]
    text = "\n".join(headline(Summaries(_cases(), runs)))
    assert "No clear winner" in text


def test_a_method_far_ahead_of_the_rest_is_named():
    runs = [_run("bid", "bid", _ranks([9, 7, 12, 30]), "-"), _run("bm25", "bm25", _ranks([20, 25, 15, 30])),
            _run("dense:fake", "dense", _ranks([1, 1, 1, 2]))]
    s = Summaries(_cases(), runs)
    retrieval = [1, 2]
    best, runner, d, ahead = best_vs_runner_up(s, retrieval)
    assert runs[best]["config"] == "dense:fake" and runs[runner]["config"] == "bm25" and ahead
    assert "No clear winner" not in "\n".join(headline(s))


def test_masked_variant_of_the_same_method_is_not_the_runner_up():
    r = _ranks([1, 2, 3])
    runs = [_run("bid", "bid", _ranks([9]), "-"), _run("bm25", "bm25", r),
            _run("bm25", "bm25", list(r), "code+commits_idmasked")]
    s = Summaries(_cases(), runs)
    _best, runner, _d, ahead = best_vs_runner_up(s, [1, 2])
    assert runner is None and not ahead  # only one run on the primary variant


def test_method_comparison_pairs_cover_bm25_dense_hybrid_rerank():
    r = _ranks([1, 2])
    runs = [_run("bm25", "bm25", r), _run("dense:fake", "dense", r), _run("hybrid:fake", "hybrid", r),
            _run("hybrid+rerank:fake+fake", "hybrid+rerank", r)]
    labels = [lab for lab, _a, _b in method_comparison_pairs(runs)]
    assert labels == ["dense:fake vs bm25", "hybrid:fake vs bm25", "hybrid:fake vs dense:fake",
                      "hybrid+rerank:fake+fake vs hybrid:fake"]
