"""Integration: the real helper's lift, callers and callees modes on fixtures/lifting.
The manifest holds the truth by construction; these tests compare it with what the helper observes."""

import json
import shutil

import pytest

from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.methods.lift import lifted_symbols, run_callees, run_callers, run_lift
from vulntrace.paths import REPO_ROOT
from vulntrace.schemas import validate

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="SKIPPED: Go toolchain (`go`) not found on PATH")

LIFT_DIR = REPO_ROOT / "fixtures" / "lifting"
MANIFEST = json.loads((LIFT_DIR / "manifest.json").read_text(encoding="utf-8"))
CASES = MANIFEST["cases"]


@pytest.fixture(scope="module")
def helper():
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


@pytest.fixture(scope="module")
def observed(helper):
    """{case id: lift record}, one helper call per distinct depth limit."""
    out = {}
    for limit in sorted({c["expected"].get("limit") or 0 for c in CASES}):
        group = [c for c in CASES if (c["expected"].get("limit") or 0) == limit]
        limits = {"max_lift_depth": limit} if limit else None
        recs = run_lift(LIFT_DIR, [c["target"] for c in group], limits=limits, binary=helper)
        out.update({c["id"]: r for c, r in zip(group, recs)})
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fixture_truth_matches_the_helper(case, observed):
    rec, exp = observed[case["id"]], case["expected"]
    validate("lift_record", rec)
    assert rec["status"] == exp["status"], case["rationale"]
    if "error_code" in exp:
        assert rec["error"]["code"] == exp["error_code"]
        return
    assert rec["error"] is None
    assert sorted(lifted_symbols(rec, "NEAREST")) == exp["NEAREST"], case["rationale"]
    assert sorted(lifted_symbols(rec, "ALL")) == exp["ALL"], case["rationale"]
    if exp.get("dynamic"):
        assert rec["rules"]["NEAREST"]["entries"][0]["dynamic"] is True
    assert rec["rules"]["ALL"]["depth_limit_reached"] is exp.get("depth_limit_reached", False)


def test_root_only_never_invents_a_symbol(observed):
    for case in CASES:
        if case["expected"]["status"] == "ROOT_ONLY":
            rec = observed[case["id"]]
            assert all(not v["entries"] for v in rec["rules"].values())


def test_the_diamond_separates_the_two_rules(observed):
    d = observed["diamond"]
    near, everything = lifted_symbols(d, "NEAREST"), lifted_symbols(d, "ALL")
    assert near < everything and everything - near == {"Top"}


def test_nearest_is_always_a_subset_of_all(observed):
    for rec in observed.values():
        assert lifted_symbols(rec, "NEAREST") <= lifted_symbols(rec, "ALL")


def test_lifting_is_deterministic(helper):
    seeds = [c["target"] for c in CASES if "limit" not in c["expected"]]
    runs = []
    for _ in range(2):
        recs = run_lift(LIFT_DIR, seeds, binary=helper)
        for r in recs:
            r["duration_ms"] = 0
            r["details"]["stats"]["duration_ms"] = 0
            r["details"]["stats"]["peak_rss_kb"] = None
        runs.append(json.dumps(recs, sort_keys=True))
    assert runs[0] == runs[1]


def test_example_path_is_a_real_chain_ending_at_the_seed(helper):
    rec = run_lift(LIFT_DIR, [{"package": "vtlift/diamond", "symbol": "sink"}], binary=helper)[0]
    for rule, v in rec["rules"].items():
        for e in v["entries"]:
            edges = e["path"]["edges"]
            assert len(edges) == e["depth"] > 0
            assert edges[0]["caller"].endswith("." + e["symbol"]) and edges[-1]["callee"].endswith(".sink")
            assert all(edges[i]["caller"] == edges[i - 1]["callee"] for i in range(1, len(edges)))
            assert all(x["call_site"]["file"].endswith("diamond/p.go") and x["call_site"]["line"] > 0 for x in edges)


def test_callers_and_callees_agree_with_the_graph(helper):
    callers = run_callers(LIFT_DIR, [{"package": "vtlift/diamond", "symbol": "sink"}], hops=2, binary=helper)[0]
    assert callers["result"] == "FOUND"
    assert {(e["hop"], e["other"]["symbol"]) for e in callers["edges"]} == {(1, "left"), (1, "right"), (2, "Left"), (2, "Right")}
    callees = run_callees(LIFT_DIR, [{"package": "vtlift/diamond", "symbol": "Top"}], binary=helper)[0]
    assert {e["other"]["symbol"] for e in callees["edges"]} == {"Left", "Right"}
    iface = run_callees(LIFT_DIR, [{"package": "vtlift/interface_call", "symbol": "Do"}], binary=helper)[0]
    assert {e["kind"] for e in iface["edges"]} == {"DYNAMIC"}
    leaf = run_callers(LIFT_DIR, [{"package": "vtlift/never_called", "symbol": "dead"}], binary=helper)[0]
    assert leaf["result"] == "NONE"


def test_a_module_that_cannot_be_loaded_is_a_counted_error_not_a_crash(helper, tmp_path):
    (tmp_path / "go.mod").write_text("module nl\n\ngo 1.21\n")
    (tmp_path / "a.go").write_text("package a\n\nfunc F( {\n")
    rec = run_lift(tmp_path, [{"package": "nl", "symbol": "F"}], binary=helper)[0]
    assert rec["status"] == "ERROR" and rec["error"]["code"] == "LOAD_FAILED" and "\n" not in rec["error"]["message"]


def test_the_older_reach_fixtures_still_work(helper):
    from vulntrace.methods.callgraph import run_vta_method
    from vulntrace.paths import FIXTURES_DIR

    r = run_vta_method(FIXTURES_DIR, "vtfixtures/cmd/direct_call", [{"package": "vtfixtures/vulnlib", "symbol": "Parse"}],
                       binary=helper)[0]
    assert r["result"] == "PATH_FOUND"
