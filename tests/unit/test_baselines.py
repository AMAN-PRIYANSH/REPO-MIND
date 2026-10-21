from vulntrace.dataset.baselines import (
    advisory_identifiers,
    bid_predict,
    core_and_derived_symbols,
    core_symbols,
    e0_predict,
)


def make_case(id_="GO-2026-0001", aliases=None, modules=None):
    return {
        "id": id_, "aliases": aliases or ["CVE-2026-00001", "GHSA-aaaa-bbbb-cccc"],
        "modules": modules or [{
            "module": "m", "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
            "packages": [{"package": "p", "core_symbols": ["Parse"], "derived_symbols": ["Convert"]}],
        }],
    }


def test_core_symbols_flattened_across_packages_and_modules():
    case = make_case(modules=[
        {"module": "m1", "vulnerable_at": None, "fixed_in": None,
         "packages": [{"package": "p1", "core_symbols": ["A"], "derived_symbols": []}]},
        {"module": "m2", "vulnerable_at": None, "fixed_in": None,
         "packages": [{"package": "p2", "core_symbols": ["B"], "derived_symbols": ["C"]}]},
    ])
    assert core_symbols(case) == {"A", "B"}
    assert core_and_derived_symbols(case) == {"A", "B", "C"}


def test_e0_predicts_every_changed_function():
    fix_ev = {"candidates": [{"symbol": "Parse"}, {"symbol": "helper"}]}
    assert e0_predict(fix_ev) == {"Parse", "helper"}


def test_e0_on_empty_evidence_abstains():
    assert e0_predict({"candidates": []}) == set()


def test_advisory_identifiers_includes_id_and_aliases_uppercased():
    case = make_case(id_="GO-2026-0001", aliases=["CVE-2026-00001", "ghsa-aaaa-bbbb-cccc"])
    assert advisory_identifiers(case) == {"GO-2026-0001", "CVE-2026-00001", "GHSA-AAAA-BBBB-CCCC"}


def test_bid_predicts_symbols_of_matching_commits():
    case = make_case(id_="GO-2026-0001", aliases=["CVE-2026-00001"])
    rr = {
        "candidates": [{"candidate_id": "r1", "symbol": "Parse"}, {"candidate_id": "r2", "symbol": "Other"}],
        "commits": [
            {"subject": "unrelated bump", "body": "", "touches_candidates": ["r2"]},
            {"subject": "fix security issue", "body": "Fixes CVE-2026-00001", "touches_candidates": ["r1"]},
        ],
    }
    assert bid_predict(case, rr) == {"Parse"}


def test_bid_matches_in_subject_too():
    case = make_case(id_="GO-2026-0001", aliases=[])
    rr = {
        "candidates": [{"candidate_id": "r1", "symbol": "Parse"}],
        "commits": [{"subject": "GO-2026-0001: fix parse", "body": "", "touches_candidates": ["r1"]}],
    }
    assert bid_predict(case, rr) == {"Parse"}


def test_bid_abstains_when_no_commit_matches():
    case = make_case(id_="GO-2026-0001", aliases=["CVE-2026-00001"])
    rr = {
        "candidates": [{"candidate_id": "r1", "symbol": "Parse"}],
        "commits": [{"subject": "unrelated", "body": "nothing here", "touches_candidates": ["r1"]}],
    }
    assert bid_predict(case, rr) == set()


def test_bid_is_case_insensitive():
    case = make_case(id_="GO-2026-0001", aliases=["CVE-2026-00001"])
    rr = {
        "candidates": [{"candidate_id": "r1", "symbol": "Parse"}],
        "commits": [{"subject": "fix cve-2026-00001", "body": "", "touches_candidates": ["r1"]}],
    }
    assert bid_predict(case, rr) == {"Parse"}


def test_bid_ignores_unknown_candidate_ids():
    """A matched commit's touches_candidates referencing an id outside the candidate list
    (should never happen, but must not crash) is simply ignored."""
    case = make_case(id_="GO-2026-0001", aliases=[])
    rr = {
        "candidates": [{"candidate_id": "r1", "symbol": "Parse"}],
        "commits": [{"subject": "GO-2026-0001", "body": "", "touches_candidates": ["r1", "r99"]}],
    }
    assert bid_predict(case, rr) == {"Parse"}
