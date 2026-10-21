"""CP3 review finding 5: the D4 case-list selection must really shuffle the non-forced pool
and really explore every forced (post-cutoff) case first. A silent sort-by-id once passed
every test; these tests observe the actual exploration order."""

import vulntrace.dataset.datasets as datasets_mod
from tests.unit.test_datasets import make_case
from vulntrace.dataset.datasets import build_d4_case_list


def _explore_order(monkeypatch, cases, seed, **kw):
    order = []

    def fake_count(case, module, binary, cache_root, runner=None):
        order.append(case["id"])
        return {"status": "AVAILABLE", "candidates": [], "from": {"commit": "a"}, "to": {"commit": "b"},
                "commits": []}

    monkeypatch.setattr(datasets_mod, "d4_candidate_count", fake_count)
    result = build_d4_case_list(cases, seed=seed, binary=None, **kw)
    return order, result


def _pool():
    forced = [make_case(id_=f"GO-2026-{9000 + i}", created="2026-12-01") for i in range(4)]
    rest = [make_case(id_=f"GO-2020-{i:04d}", created="2020-01-01") for i in range(40)]
    return forced, rest


def test_forced_cases_are_explored_before_any_other(monkeypatch):
    forced, rest = _pool()
    order, _ = _explore_order(monkeypatch, rest + forced, seed=1, target=44, large_target=0, batch_size=10)
    assert set(order[:4]) == {c["id"] for c in forced}


def test_non_forced_pool_is_really_shuffled_and_seed_deterministic(monkeypatch):
    forced, rest = _pool()
    o1, _ = _explore_order(monkeypatch, forced + rest, seed=1, target=44, large_target=0)
    o1b, _ = _explore_order(monkeypatch, forced + rest, seed=1, target=44, large_target=0)
    o2, _ = _explore_order(monkeypatch, forced + rest, seed=2, target=44, large_target=0)
    tail1, tail2 = o1[4:], o2[4:]
    ids = sorted(c["id"] for c in rest)
    assert sorted(tail1) == ids                  # a permutation: nothing dropped or duplicated
    assert tail1 != ids and tail1 != ids[::-1]   # not id-sorted (the CP3 bug)
    assert o1 == o1b                             # deterministic for a seed
    assert tail1 != tail2                        # and actually depends on the seed


def test_input_order_does_not_change_exploration_order(monkeypatch):
    forced, rest = _pool()
    o1, _ = _explore_order(monkeypatch, forced + rest, seed=3, target=44, large_target=0)
    o2, _ = _explore_order(monkeypatch, list(reversed(rest)) + forced, seed=3, target=44, large_target=0)
    assert o1 == o2


def test_early_stop_still_samples_all_forced_and_a_shuffled_prefix(monkeypatch):
    forced, rest = _pool()
    order, result = _explore_order(monkeypatch, forced + rest, seed=1, target=10, large_target=0, batch_size=10)
    sample_ids = {c["id"] for c in result["sample"]}
    assert {c["id"] for c in forced} <= sample_ids
    assert len(sample_ids) == 10
    assert sample_ids - {c["id"] for c in forced} == set(order[4:10])
