"""CP10 deliverable 3: D3c selection with two strata and quotas (fake probe, no network)."""

import json
from pathlib import Path

import pytest

from tests.unit.test_d3_select import FakeProbe, _repo
from vulntrace.d3 import select as sl

ROOT = Path(__file__).resolve().parents[2]
FIX = {"host": "github.com", "owner": "vuln", "repo": "lib", "sha": "f" * 40}


def entry(aid, module, stratum):
    return {"id": aid, "module": module, "events": [{"introduced": "1.0.0"}, {"fixed": "1.3.0"}], "created": "2026-02-01",
            "fix_commit": FIX, "packages": [module], "core_symbols": 2 if stratum == "S" else 0, "stratum": stratum}


INDEX = {"github.com/vuln/lib": [entry(f"GO-2026-000{i}", "github.com/vuln/lib", "S") for i in range(1, 5)]
         + [entry(f"GO-2026-010{i}", "github.com/vuln/lib", "N") for i in range(1, 5)],
         "github.com/vuln/other": [entry("GO-2026-0201", "github.com/vuln/other", "N")]}
MOD = "module github.com/{o}/{r}\n\ngo 1.22\n\nrequire (\n\tgithub.com/vuln/lib v1.2.0\n\tgithub.com/vuln/other v1.2.0\n)\n"


def _cfg(repos, **kw):
    cfg = {"seed": 20261126, "pin_cutoff": "2025-12-31T23:59:59Z", "min_apps": 2, "max_apps": 3, "quota_s": 4,
           "quota_n": 4, "max_cases_per_stratum_per_app": 3, "max_requires": 150, "max_mains": 10, "max_tag_probes": 60,
           "excluded_apps": ["github.com/old/app"],
           "candidates": [{"repo": k, "domain": v.pop("_domain")} for k, v in repos.items()]}
    cfg.update(kw)
    return cfg


def _repos(n):
    return {f"github.com/o{i}/app": {**_repo(f"o{i}", "app", go_mod=MOD.format(o=f"o{i}", r="app"),
                                             selected={"github.com/vuln/lib": "v1.2.0", "github.com/vuln/other": "v1.2.0"}),
                                     "_domain": f"d{i}"} for i in range(n)}


def test_pick_cases_strata_caps_each_stratum_and_never_repeats_an_advisory():
    elig = [dict(e, version="v1.2.0") for es in INDEX.values() for e in es]
    picked = sl.pick_cases_strata("github.com/o0/app", elig, 20261126, 3)
    by = [e["stratum"] for e in picked]
    assert by.count("S") == 3 and by.count("N") == 3 and by[:3] == ["S"] * 3
    assert len({e["id"] for e in picked}) == len(picked)
    # the N round-robin covers both modules
    assert {e["module"] for e in picked if e["stratum"] == "N"} == {"github.com/vuln/lib", "github.com/vuln/other"}


def test_select_d3c_stops_when_min_apps_and_both_quotas_are_met():
    repos = _repos(4)
    res = sl.select_d3c(_cfg(repos), INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)
    statuses = [r["status"] for r in res["records"]]
    assert statuses == [sl.KEPT, sl.KEPT, sl.NOT_EVALUATED, sl.NOT_EVALUATED]
    assert res["totals"] == {"S": 6, "N": 6} and res["quotas_met"] is True
    assert all(r["detail"] == "quotas met" for r in res["records"] if r["status"] == sl.NOT_EVALUATED)
    cases = sl.case_list(res["kept"])
    assert {c["stratum"] for c in cases} == {"S", "N"} and all("stratum" in c for c in cases)


def test_select_d3c_adds_applications_until_stratum_n_is_filled():
    repos = _repos(4)
    cfg = _cfg(repos, quota_n=7, max_apps=4)
    res = sl.select_d3c(cfg, INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)
    assert [r["status"] for r in res["records"]][:3] == [sl.KEPT] * 3 and res["totals"]["N"] == 9
    assert res["quotas_met"] is True


def test_select_d3c_reports_unmet_quotas_when_candidates_run_out():
    repos = _repos(2)
    res = sl.select_d3c(_cfg(repos, quota_n=99), INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)
    assert res["quotas_met"] is False and len(res["kept"]) == 2 and res["candidates_evaluated"] == 2


def test_select_d3c_refuses_an_excluded_application():
    repos = {"github.com/old/app": {**_repo("old", "app"), "_domain": "x"}}
    with pytest.raises(ValueError):
        sl.select_d3c(_cfg(repos), INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)


def test_d3_selection_is_unchanged_by_the_strata_code():
    """`select` (D3/D3b) never sees a stratum and its cases carry none."""
    from tests.unit.test_d3_select import INDEX as D3_INDEX
    from tests.unit.test_d3_select import _config

    repos = {f"github.com/o{i}/app": {**_repo(f"o{i}", "app"), "_domain": f"d{i}"} for i in range(2)}
    res = sl.select(_config(repos), D3_INDEX, FakeProbe(repos), "go1.26.10", log=lambda m: None)
    assert all("stratum" not in c for c in sl.case_list(res["kept"]))
    assert all("eligible_selected_by_stratum" not in r for r in res["kept"])


def test_committed_d3c_candidates_match_the_rules_doc():
    cfg = json.loads((ROOT / "docs" / "evaluation" / "d3c_candidates.json").read_text(encoding="utf-8"))
    doc = (ROOT / "docs" / "evaluation" / "D3C_SELECTION_RULES.md").read_text(encoding="utf-8")
    d3 = json.loads((ROOT / "docs" / "evaluation" / "d3_candidates.json").read_text(encoding="utf-8"))
    d3b_cases = json.loads((ROOT / "docs" / "results" / "cp9" / "d3b" / "d3_cases.json").read_text(encoding="utf-8"))
    d3_cases = json.loads((ROOT / "docs" / "results" / "cp7b" / "d3_cases.json").read_text(encoding="utf-8"))
    earlier = {c["app_repo"] for c in d3_cases["cases"] + d3b_cases["cases"]}
    assert len(earlier) == 8 and set(cfg["excluded_apps"]) == earlier
    repos = [c["repo"] for c in cfg["candidates"]]
    assert len(repos) == len(set(repos)) == 57 and not earlier & set(repos)
    assert {c["repo"] for c in d3["candidates"]} - earlier <= set(repos)
    assert cfg["seed"] == 20261126 and "20261126" in doc
    assert (cfg["min_apps"], cfg["max_apps"], cfg["quota_s"], cfg["quota_n"], cfg["max_cases_per_stratum_per_app"]) == \
        (4, 8, 8, 8, 3)
    assert cfg["pin_cutoff"] == "2025-12-31T23:59:59Z" and cfg["max_requires"] == 150 and cfg["max_mains"] == 10


def test_stratum_s_index_is_exactly_the_d3_index():
    from vulntrace.dataset import vulndb

    if not vulndb.is_up_to_date(None):
        pytest.skip("no pinned vulndb snapshot (python -m vulntrace dataset fetch)")
    idx = sl.advisory_index_strata()
    s_only = {m: [{k: v for k, v in e.items() if k not in ("stratum", "review_status")} for e in es if e["stratum"] == "S"]
              for m, es in idx.items()}
    assert {m: v for m, v in s_only.items() if v} == sl.advisory_index()
    assert all(e["core_symbols"] == 0 for es in idx.values() for e in es if e["stratum"] == "N")
