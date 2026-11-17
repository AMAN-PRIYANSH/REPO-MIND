"""CP9 integration: the path-feasibility filter end to end with the real Go helper on the CP9
fixtures (truth by construction) and on the CP2/CP7 fixtures (TARGETS mode). Skipped with a message
if Go is missing. No network: the fixture modules have no dependencies (GOPROXY=off)."""

import json
import shutil

import pytest

from vulntrace.eval.triage_eval import _stable_view
from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.paths import FEASIBILITY_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT
from vulntrace.pipeline import feasibility as fz, triage
from vulntrace.pipeline.cli import default_runners
from vulntrace.schemas import validation_errors

CP9 = json.loads((FEASIBILITY_FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))["cases"]
CP7 = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))["cases"]
CP7_ROWS = json.loads((REPO_ROOT / "docs" / "results" / "cp7" / "fixtures.json").read_text(encoding="utf-8"))["rows"]


@pytest.fixture(scope="module")
def binary():
    if shutil.which("go") is None:
        pytest.skip("SKIPPED: Go is not installed; CP9 integration tests need the go toolchain")
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


@pytest.fixture(scope="module")
def on(binary):
    return default_runners(binary=binary, feasibility=fz.helper_settings())


@pytest.fixture(scope="module")
def off(binary):
    return default_runners(binary=binary)


def _run(runners, app, case):
    req = triage.TriageRequest(case_id=case["id"], app=app, mode="targets", targets=case["targets"],
                               mains=[case["main_package"]], max_mains=1)
    v = triage.run_triage(req, runners)
    assert validation_errors("verdict", v) == []
    return v


@pytest.mark.parametrize("case", CP9, ids=[c["id"] for c in CP9])
def test_cp9_fixture_behaves_as_constructed(case, on, off):
    before, after = _run(off, FEASIBILITY_FIXTURES_DIR, case), _run(on, FEASIBILITY_FIXTURES_DIR, case)
    assert before["verdict"] == "REACHABLE", "every CP9 fixture is REACHABLE without the filter (by design)"
    e = after["per_symbol"][0]
    assert e["feasibility"]["status"] == case["expected_filter"]
    if case["kind"] == "INFEASIBLE":
        assert (after["verdict"], after["reason_codes"]) == ("CANT_DETERMINE", ["PATHS_INFEASIBLE"])
        assert after["verification"]["checks_by_kind"]["INFEASIBLE_STEP"]["failed"] == 0
        assert case["pattern"] in fz.first_patterns(e), "the case's own pattern must appear among the first infeasible steps"
    else:
        assert after["verdict"] == "REACHABLE", f"{case['kind']} must stay REACHABLE"
        assert e["verified_path"] == e["feasibility"]["evidence_path"]


@pytest.mark.parametrize("case", CP7, ids=[c["id"] for c in CP7])
def test_cp7_fixtures_unchanged_and_reproduced(case, on, off):
    before, after = _run(off, FIXTURES_DIR, case), _run(on, FIXTURES_DIR, case)
    committed = next(r for r in CP7_ROWS if r["id"] == case["id"] and r["mode"] == "TARGETS")
    # --no-feasibility reproduces CP7 (TARGETS mode; `eval feasibility --set fixtures` compares every row)
    assert (before["verdict"], before["reason_codes"]) == (committed["verdict"], committed["reason_codes"])
    assert "feasibility" not in before
    # the filter changes nothing on the CP2/CP7 fixtures
    assert _stable_view(after)[:2] == _stable_view(before)[:2]
    for a, b in zip(before["per_symbol"], after["per_symbol"]):
        assert (a["result"], a["reason_code"]) == (b["result"], b["reason_code"])
