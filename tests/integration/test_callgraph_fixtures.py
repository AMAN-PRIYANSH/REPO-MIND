"""Integration: the real helper on the fixture suite (VTA, naive, combined, edges, funcs)."""

import json
import shutil

import pytest

from vulntrace.eval import callgraph_score as cs
from vulntrace.eval.fixture_score import strip_timing
from vulntrace.methods.callgraph import run_vta_method
from vulntrace.methods.helper import CONTRACT_VERSION, HelperError, ensure_helper, run_helper
from vulntrace.paths import FIXTURES_DIR
from vulntrace.schemas import validate

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="SKIPPED: Go toolchain (`go`) not found on PATH")

PARSE = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}
INFRA_ERRORS = {"LOAD_FAILED", "TYPE_ERRORS", "INTERNAL", "TIMEOUT", "HELPER_MISSING", "BAD_RESPONSE",
                "BAD_REQUEST", "CONTRACT_MISMATCH"}
MANIFEST = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def helper():
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


@pytest.fixture(scope="module")
def vta(helper):
    return cs.score_callgraph(FIXTURES_DIR, cs.VTA_METHOD, binary=helper)


@pytest.fixture(scope="module")
def naive(helper):
    return cs.score_callgraph(FIXTURES_DIR, cs.NAIVE_METHOD, binary=helper)


@pytest.fixture(scope="module")
def combined(helper):
    return cs.score_combined(FIXTURES_DIR, binary=helper)


def _all_results(report):
    for case in report["cases"]:
        mr = case["method_results"]
        yield from (mr if isinstance(mr, list) else [r for rs in mr.values() for r in rs])


@pytest.mark.parametrize("name", ["vta", "naive", "combined"])
def test_every_case_runs_without_infrastructure_errors(name, request):
    report = request.getfixturevalue(name)
    assert [c["id"] for c in report["cases"]] == [c["id"] for c in MANIFEST["cases"]]
    for r in _all_results(report):
        assert (r["error"] or {}).get("code") not in INFRA_ERRORS, r
        validate("method_result", r)


def test_every_combined_verdict_validates(combined):
    for case in combined["cases"]:
        validate("verdict", case["verdict"])
        assert case["verdict"]["verification"]["status"] == "NOT_RUN"


def test_combined_has_no_false_not_reachable(combined):
    assert [c["id"] for c in combined["cases"] if c["outcome"] == "FALSE_NOT_REACHABLE"] == []


def test_method_disagreement_gives_cant_determine(combined):
    seen = 0
    for case in combined["cases"]:
        for s in case["verdict"]["per_symbol"]:
            m = s["methods"]
            if (m["CALLGRAPH_VTA"], m["LINKER_PRESENCE"]) in (("NO_PATH", "PRESENT"), ("PATH_FOUND", "ABSENT")):
                seen += 1
                assert (s["result"], s["reason_code"]) == ("CANT_DETERMINE", "METHOD_DISAGREEMENT"), case["id"]
                assert case["verdict"]["verdict"] == "CANT_DETERMINE"
    assert seen > 0, "the suite is meant to contain disagreement cases"


def test_naive_control_misses_function_value_and_reflection_paths(naive):
    false_nr = {c["id"] for c in naive["cases"] if c["outcome"] == "FALSE_NOT_REACHABLE"}
    assert {"func_value_map", "reflect_method"} <= false_nr


def test_init_root_is_used(vta):
    case = next(c for c in vta["cases"] if c["id"] == "init_imported")
    r = case["method_results"][0]
    assert r["result"] == "PATH_FOUND" and r["details"]["path"]["entry"]["symbol"] == "init"


def test_target_not_found_is_never_no_path(helper):
    targets = [PARSE, {"package": "vtfixtures/vulnlib", "symbol": "DoesNotExist"},
               {"package": "vtfixtures/initdep", "symbol": "Result"}]
    res = run_vta_method(FIXTURES_DIR, "vtfixtures/cmd/direct_call", targets, binary=helper)
    assert [(r["result"], (r["error"] or {}).get("code")) for r in res] == [
        ("PATH_FOUND", None), ("ERROR", "TARGET_NOT_FOUND"), ("ERROR", "TARGET_NOT_FOUND")]
    # vulnlib is imported only from a file excluded by a build tag: not in the program.
    res = run_vta_method(FIXTURES_DIR, "vtfixtures/cmd/build_tag_excluded", [PARSE], binary=helper)
    assert (res[0]["result"], res[0]["error"]["code"]) == ("ERROR", "TARGET_NOT_FOUND")


def test_timeout_is_reported_as_timeout(helper):
    res = run_vta_method(FIXTURES_DIR, "vtfixtures/cmd/direct_call", [PARSE], binary=helper, timeout=0.01)
    assert res[0]["result"] == "ERROR" and res[0]["error"]["code"] == "TIMEOUT"


def test_determinism_apart_from_timing(helper, vta, naive, combined):
    assert strip_timing(cs.score_callgraph(FIXTURES_DIR, cs.VTA_METHOD, binary=helper)) == strip_timing(vta)
    assert strip_timing(cs.score_callgraph(FIXTURES_DIR, cs.NAIVE_METHOD, binary=helper)) == strip_timing(naive)
    assert strip_timing(cs.score_combined(FIXTURES_DIR, binary=helper)) == strip_timing(combined)


def _req(mode, **kw):
    return {"contract_version": CONTRACT_VERSION, "mode": mode, "module_dir": FIXTURES_DIR.as_posix(),
            "main_packages": ["vtfixtures/cmd/interface_dispatch"], "build": {"tags": [], "goos": None, "goarch": None},
            **kw}


def test_edges_confirms_every_edge_of_a_vta_path_and_rejects_others(helper, vta):
    case = next(c for c in vta["cases"] if c["id"] == "interface_dispatch")
    path = case["method_results"][0]["details"]["path"]
    assert any(e["kind"] == "DYNAMIC" for e in path["edges"])
    queries = [{"caller": e["caller"], "callee": e["callee"], "call_site": e["call_site"]} for e in path["edges"]]
    queries.append({"caller": "vtfixtures/cmd/interface_dispatch.main", "callee": "vtfixtures/vulnlib.Parse"})
    resp = run_helper("edges", _req("edges", edges=queries), binary=helper)
    assert [r["exists"] for r in resp["results"]] == [True] * len(path["edges"]) + [False]


def test_funcs_lists_declarations_with_lines(helper):
    resp = run_helper("funcs", {"contract_version": CONTRACT_VERSION, "mode": "funcs",
                                "module_dir": FIXTURES_DIR.as_posix(), "files": ["vulnlib/vulnlib.go"]}, binary=helper)
    funcs = {f["symbol"]: f for f in resp["results"][0]["functions"]}
    lines = (FIXTURES_DIR / "vulnlib" / "vulnlib.go").read_text(encoding="utf-8").splitlines()
    assert set(funcs) == {"Parse", "ParseTiny", "ParseAny", "Safe", "Impl.Run", "PImpl.Run"}
    for f in funcs.values():
        assert lines[f["start"] - 1].startswith("func "), f
        assert lines[f["end"] - 1].rstrip().endswith("}"), f

