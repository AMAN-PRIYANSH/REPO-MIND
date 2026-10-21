import json
import shutil

import pytest

from vulntrace.eval.fixture_score import score_linker, strip_timing
from vulntrace.paths import FIXTURES_DIR
from vulntrace.schemas import validate

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="SKIPPED: Go toolchain (`go`) not found on PATH")

TRIAL3 = {  # feasibility trial 3 observations
    "direct_call": "PRESENT",
    "safe_only": "ABSENT",
    "func_value_map": "PRESENT",
    "reflect_method": "PRESENT",
    "dead_code": "ABSENT",
}


@pytest.fixture(scope="module")
def report():
    return score_linker(FIXTURES_DIR)


def test_every_manifest_case_is_run(report):
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in report["cases"]] == [c["id"] for c in manifest["cases"]]
    for case in report["cases"]:
        for r in case["method_results"]:
            assert (r["error"] or {}).get("code") not in ("BUILD_FAILED", "NM_FAILED", "GO_NOT_FOUND"), case["id"]


def test_trial3_cases_reproduce_observations(report):
    got = {c["id"]: c["method_results"][0]["result"] for c in report["cases"]}
    for case_id, expected in TRIAL3.items():
        assert got[case_id] == expected, case_id


def test_reflection_case_keeps_method_symbols():
    from vulntrace.methods.linker import NO_INLINE_FLAGS, run_linker_method

    r = run_linker_method(
        FIXTURES_DIR, "vtfixtures/cmd/reflect_method",
        [{"package": "vtfixtures/vulnlib", "symbol": "Impl.Run"}], NO_INLINE_FLAGS)
    assert r[0]["result"] == "PRESENT"
    assert set(r[0]["details"]["matched_binary_symbols"]) <= {"vtfixtures/vulnlib.Impl.Run", "vtfixtures/vulnlib.(*Impl).Run"}


def test_generic_target_is_unsupported(report):
    case = next(c for c in report["cases"] if c["id"] == "generic_target")
    assert case["method_results"][0]["error"]["code"] == "UNSUPPORTED_SYMBOL_FORM"


def test_all_method_results_validate_against_schema(report):
    pytest.importorskip("jsonschema")
    for case in report["cases"]:
        for r in case["method_results"]:
            validate("method_result", r)


def test_determinism_apart_from_timing(report):
    again = score_linker(FIXTURES_DIR)
    assert strip_timing(again) == strip_timing(report)


def test_scoring_does_not_use_network(report):
    # Every go invocation uses go_env(); see unit tests for GOPROXY=off.
    # This asserts the run succeeded with GOPROXY=off, i.e. without fetching modules.
    from vulntrace.env import go_env
    assert go_env()["GOPROXY"] == "off"
    assert report["counts"]["cases"] > 0


def test_committed_cp1_results_doc_matches_a_fresh_run():
    """The tables in docs/results/CP1_LINKER_RESULTS.md come from code, not by hand."""
    from vulntrace.eval.results_doc import load_notes, render_cp1_doc
    from vulntrace.paths import REPO_ROOT

    fresh = render_cp1_doc(score_linker(FIXTURES_DIR, compare_inlining=True), load_notes("cp1_linker"), "x")
    committed = (REPO_ROOT / "docs" / "results" / "CP1_LINKER_RESULTS.md").read_text(encoding="utf-8")
    table = lambda text: [ln for ln in text.splitlines() if ln.startswith("|") or ln.startswith("Cases:")]
    assert table(committed) == table(fresh)
