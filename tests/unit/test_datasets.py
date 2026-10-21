import vulntrace.dataset.datasets as datasets_mod
from vulntrace.dataset.datasets import (
    CONTAMINATION_CUTOFF,
    build_d4_case_list,
    eligible_for_d1,
    eligible_for_d4,
    has_core_symbols,
    is_stdlib_or_toolchain,
    pick_d4_module,
    stratified_sample,
)


def make_case(id_="GO-2026-0001", review_status="REVIEWED", withdrawn=False, created="2026-01-01",
             modules=None, fix_commits=None):
    return {
        "schema_version": "1.0", "id": id_, "aliases": [], "summary": "s", "review_status": review_status,
        "withdrawn": withdrawn, "created": created,
        "fix_commits": fix_commits if fix_commits is not None else [
            {"host": "github.com", "owner": "o", "repo": "r", "sha": "a" * 40}],
        "fix_references": [],
        "modules": modules if modules is not None else [{
            "module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
            "packages": [{"package": "github.com/o/r", "core_symbols": ["F"], "derived_symbols": []}],
        }],
        "source": {"vulndb_commit": "e" * 40, "report_path": f"data/reports/{id_}.yaml"},
    }


def test_has_core_symbols():
    assert has_core_symbols(make_case())
    no_symbols = make_case(modules=[{"module": "m", "vulnerable_at": None, "fixed_in": None,
                                     "packages": [{"package": "p", "core_symbols": [], "derived_symbols": []}]}])
    assert not has_core_symbols(no_symbols)


def test_is_stdlib_or_toolchain():
    std = make_case(modules=[{"module": "std", "vulnerable_at": "1.21", "fixed_in": None, "packages": []}])
    cmd = make_case(modules=[{"module": "cmd", "vulnerable_at": "1.21", "fixed_in": None, "packages": []}])
    assert is_stdlib_or_toolchain(std) and is_stdlib_or_toolchain(cmd)
    assert not is_stdlib_or_toolchain(make_case())


def test_eligible_for_d1_requires_reviewed_not_withdrawn_symbols_and_fix_commit():
    assert eligible_for_d1(make_case())
    assert not eligible_for_d1(make_case(review_status="UNREVIEWED"))
    assert not eligible_for_d1(make_case(review_status="NEEDS_REVIEW"))
    assert not eligible_for_d1(make_case(withdrawn=True))
    assert not eligible_for_d1(make_case(fix_commits=[]))
    no_symbols = make_case(modules=[{"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
                                     "packages": [{"package": "p", "core_symbols": [], "derived_symbols": []}]}])
    assert not eligible_for_d1(no_symbols)
    assert not eligible_for_d1(make_case(modules=[{"module": "std", "vulnerable_at": "1.21", "fixed_in": None,
                                                    "packages": []}]))


def test_pick_d4_module_prefers_one_with_symbols():
    case = make_case(modules=[
        {"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
         "packages": [{"package": "p1", "core_symbols": [], "derived_symbols": []}]},
        {"module": "github.com/o/r/sub", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
         "packages": [{"package": "p2", "core_symbols": ["F"], "derived_symbols": []}]},
    ])
    assert pick_d4_module(case)["module"] == "github.com/o/r/sub"


def test_pick_d4_module_requires_both_vulnerable_at_and_fixed_in():
    case = make_case(modules=[{"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": None,
                               "packages": [{"package": "p", "core_symbols": ["F"], "derived_symbols": []}]}])
    assert pick_d4_module(case) is None
    assert not eligible_for_d4(case)


def test_pick_d4_module_falls_back_to_a_module_without_symbols_if_none_has_both():
    case = make_case(modules=[{"module": "github.com/o/r", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
                               "packages": [{"package": "p", "core_symbols": [], "derived_symbols": []}]}])
    assert pick_d4_module(case)["module"] == "github.com/o/r"


def test_eligible_for_d4_is_eligible_for_d1_plus_a_usable_module():
    assert eligible_for_d4(make_case())


def test_stratified_sample_forces_in_post_cutoff_cases():
    late = make_case(id_="GO-2026-9999", created="2026-12-01")
    earlier = [make_case(id_=f"GO-2020-{i:04d}", created="2020-01-01") for i in range(10)]
    sample = stratified_sample([late, *earlier], target=3, seed=1)
    assert late in sample
    assert len(sample) == 3


def test_stratified_sample_is_deterministic_for_a_seed():
    cases = [make_case(id_=f"GO-{y}-{i:04d}", created=f"{y}-01-01") for y in range(2020, 2026) for i in range(20)]
    a = stratified_sample(cases, target=30, seed=7)
    b = stratified_sample(cases, target=30, seed=7)
    assert [c["id"] for c in a] == [c["id"] for c in b]


def test_stratified_sample_different_seeds_can_differ():
    cases = [make_case(id_=f"GO-{y}-{i:04d}", created=f"{y}-01-01") for y in range(2020, 2026) for i in range(20)]
    a = stratified_sample(cases, target=30, seed=1)
    b = stratified_sample(cases, target=30, seed=2)
    assert [c["id"] for c in a] != [c["id"] for c in b]


def test_stratified_sample_covers_every_year_proportionally():
    cases = ([make_case(id_=f"GO-2020-{i:04d}", created="2020-01-01") for i in range(80)]
            + [make_case(id_=f"GO-2021-{i:04d}", created="2021-01-01") for i in range(20)])
    sample = stratified_sample(cases, target=50, seed=3)
    years = {c["id"].split("-")[1] for c in sample}
    assert years == {"2020", "2021"}
    n_2020 = sum(1 for c in sample if c["id"].startswith("GO-2020"))
    assert 35 <= n_2020 <= 45  # roughly 80% of 50


def test_stratified_sample_returns_everything_if_pool_smaller_than_target():
    cases = [make_case(id_=f"GO-2020-{i:04d}", created="2020-01-01") for i in range(5)]
    sample = stratified_sample(cases, target=50, seed=1)
    assert len(sample) == 5


def test_contamination_cutoff_is_the_documented_placeholder():
    assert CONTAMINATION_CUTOFF == "2026-06-30"


def test_build_d4_case_list_counts_truncated_cases_as_large(monkeypatch):
    """A TRUNCATED range still carries a real candidate list (it comes from a single
    two-tree diff, not from the - possibly incomplete - commit walk it was truncated for),
    so a truncated-but-large case must still count toward large_found."""
    case = make_case(id_="GO-2026-0001", created="2020-01-01")

    def fake_count(case, module, binary, cache_root, runner=None):
        return {"status": "TRUNCATED", "candidates": [{"symbol": f"F{i}"} for i in range(150)],
               "from": {"commit": "a"}, "to": {"commit": "b"}, "commits": []}

    monkeypatch.setattr(datasets_mod, "d4_candidate_count", fake_count)
    result = build_d4_case_list([case], seed=1, binary=None, target=1, large_target=1)
    assert result["large_ids"] == ["GO-2026-0001"]
    assert case in result["sample"]
