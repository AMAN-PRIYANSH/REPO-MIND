"""CP7 end to end with the real Go helper and toolchain (skipped with a message if Go is missing).
No network: the fixture module has no dependencies and every build uses GOPROXY=off."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.methods.linker import run_linker_method
from vulntrace.paths import FIXTURES_DIR, REPO_ROOT
from vulntrace.pipeline import app as app_mod, triage
from vulntrace.pipeline.cli import default_runners
from vulntrace.schemas import validation_errors
from vulntrace.verifier.verify import verify

PARSE = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}


@pytest.fixture(scope="module")
def binary():
    if shutil.which("go") is None:
        pytest.skip("SKIPPED: Go is not installed; CP7 integration tests need the go toolchain")
    try:
        return ensure_helper()
    except HelperError as exc:
        pytest.skip(f"SKIPPED: vt-helper could not be built ({exc.message[:200]})")


@pytest.fixture(scope="module")
def runners(binary):
    return default_runners(binary=binary)


@pytest.fixture(scope="module")
def pack(binary, tmp_path_factory):
    from vulntrace.eval import triage_fixtures as tfx

    return tfx.build_pack(tmp_path_factory.mktemp("pack"), binary)


def _run(runners, **kw):
    kw.setdefault("app", FIXTURES_DIR)
    kw.setdefault("case_id", "fixture")
    v = triage.run_triage(triage.TriageRequest(**kw), runners)
    assert validation_errors("verdict", v) == []
    return v


def test_cli_prints_one_verdict(binary, tmp_path):
    adv = tmp_path / "adv.json"
    adv.write_text(json.dumps({"id": "FIXTURE-PARSE", "summary": "Parse", "module": "vtfixtures", "fix_commits": []}))
    p = subprocess.run([sys.executable, "-m", "vulntrace", "triage", "--advisory-file", str(adv), "--app", str(FIXTURES_DIR),
                        "--mode", "targets", "--target", "vtfixtures/vulnlib:Parse", "--main", "./cmd/direct_call"],
                       capture_output=True, text=True, cwd=REPO_ROOT, timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    v = json.loads(p.stdout)
    assert v["verdict"] == "REACHABLE" and v["per_symbol"][0]["verified_path"]
    assert v["verification"]["status"] == "PASSED"


def test_cli_bad_input_exit_code(tmp_path):
    p = subprocess.run([sys.executable, "-m", "vulntrace", "triage", "--advisory-file", str(tmp_path / "missing.json"),
                        "--app", str(tmp_path)], capture_output=True, text=True, cwd=REPO_ROOT, timeout=120)
    assert p.returncode == 2


@pytest.mark.parametrize("case,truth", [("direct_call", "REACHABLE"), ("init_imported", "REACHABLE"),
                                        ("method_expression", "REACHABLE"), ("safe_only", "NOT_REACHABLE"),
                                        ("present_but_unreachable", "CANT_DETERMINE"), ("reflect_method", "CANT_DETERMINE")])
def test_targets_mode_on_fixtures(runners, case, truth):
    v = _run(runners, mode="targets", targets=[PARSE], mains=[f"./cmd/{case}"])
    assert v["verdict"] == truth
    if truth == "REACHABLE":
        assert v["per_symbol"][0]["verified_path"] in v["per_symbol"][0]["paths"]


def test_mode1_and_mode2_on_fixtures(runners, pack):
    p = pack["Parse"]
    m1 = _run(runners, mode="auto", advisory=p["advisory"], fix_evidence=p["fix_evidence"], module_rel="", mains=["./cmd/direct_call"])
    assert m1["mode"] == "FIX" and m1["verdict"] == "REACHABLE"
    m2 = _run(runners, mode="release", advisory=p["advisory"], release_range=p["release_range"],
              candidate_code=p["candidate_code"], module_rel="", mains=["./cmd/interface_not_instantiated"])
    assert m2["pre_policy_verdict"] == "NOT_REACHABLE" and m2["verdict"] == "CANT_DETERMINE"
    assert m2["reason_codes"] == ["MODE2_NOT_REACHABLE_DOWNGRADED"]
    # the decoy Safe is reachable from safe_only: candidate-level REACHABLE, as designed
    m3 = _run(runners, mode="release", advisory=p["advisory"], release_range=p["release_range"],
              candidate_code=p["candidate_code"], module_rel="", mains=["./cmd/safe_only"])
    assert m3["verdict"] == "REACHABLE" and m3["evidence_level"] == "CANDIDATE_LEVEL"
    assert [e["target"]["symbol"] for e in m3["per_symbol"] if e["result"] == "REACHABLE"] == ["Safe"]


def test_generic_target_in_vulndb_form_is_reachable_in_mode1(runners, pack):
    p = pack["ParseAny[T]"]
    v = _run(runners, mode="fix", advisory=p["advisory"], fix_evidence=p["fix_evidence"], module_rel="",
             mains=["./cmd/generic_target"])
    e = next(x for x in v["per_symbol"] if x["target"]["symbol"] == "ParseAny")
    assert e["methods"] == {"CALLGRAPH_VTA": "PATH_FOUND", "LINKER_PRESENCE": "PRESENT"} and e["result"] == "REACHABLE"


def test_real_verifier_rejects_corrupted_paths(runners):
    v = _run(runners, mode="targets", targets=[PARSE], mains=["./cmd/interface_dispatch"])
    assert v["verdict"] == "REACHABLE"
    info = app_mod.inspect_app(FIXTURES_DIR, mains=["./cmd/interface_dispatch"], max_mains=1)
    pre = copy.deepcopy(v)
    e = pre["per_symbol"][0]
    e["verified_path"], e["verifier_failures"] = None, []
    good = e["paths"][0]
    wrong_line = copy.deepcopy(good)
    wrong_line["edges"][-1]["call_site"]["line"] += 1
    missing_edge = copy.deepcopy(good)
    missing_edge["edges"][0]["callee"] = "vtfixtures/vulnlib.Safe"
    missing_edge["edges"][1]["caller"] = "vtfixtures/vulnlib.Safe"
    for bad in (wrong_line, missing_edge):
        x = copy.deepcopy(pre)
        x["per_symbol"][0]["paths"] = [bad]
        out = verify(x, runners.verifier_ctx(info, False))
        assert (out["per_symbol"][0]["result"], out["per_symbol"][0]["reason_code"]) == ("CANT_DETERMINE", "VERIFIER_REJECTED")
    ok = verify(pre, runners.verifier_ctx(info, False))
    assert ok["per_symbol"][0]["result"] == "REACHABLE"


def test_deterministic(binary):
    a = _run(default_runners(binary=binary), mode="targets", targets=[PARSE], mains=["./cmd/generic_call"])
    b = _run(default_runners(binary=binary), mode="targets", targets=[PARSE], mains=["./cmd/generic_call"])
    view = lambda v: [(e["result"], e["methods"], e["verified_path"]) for e in v["per_symbol"]]  # noqa: E731
    assert view(a) == view(b)


def test_inspect_app_lists_mains_and_limits(binary):
    info = app_mod.inspect_app(FIXTURES_DIR, max_mains=3)
    assert len(info.mains) == 3 and len(info.mains_skipped) >= 18
    assert info.module == "vtfixtures" and info.commit and info.commit_source == "GIT_HEAD"


GEN_LIB = """package lib

type List[T any] struct{ items []T }

func (l *List[T]) Push(v T) { l.items = append(l.items, v) }

type Box[T any] struct{ v T }

func (b Box[T]) Get() T { return b.v }

func Map[T, U any](xs []T, f func(T) U) []U {
\tout := make([]U, 0, len(xs))
\tfor _, x := range xs {
\t\tout = append(out, f(x))
\t}
\treturn out
}
"""
GEN_MAIN = """package main

import (
\t"fmt"

\t"probe.example/lib"
)

func main() {
\tvar l lib.List[string]
\tl.Push("a")
\tb := lib.Box[[]byte]{}
\tfmt.Println(b.Get(), lib.Map([]int{1}, func(i int) string { return "x" }))
}
"""


def test_generic_symbols_in_vulndb_form_on_a_real_binary(binary, tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "cmd" / "app").mkdir(parents=True)
    (tmp_path / "go.mod").write_text("module probe.example\n\ngo 1.21\n")
    (tmp_path / "lib" / "lib.go").write_text(GEN_LIB)
    (tmp_path / "cmd" / "app" / "main.go").write_text(GEN_MAIN)
    targets = [{"package": "probe.example/lib", "symbol": s} for s in ("Map", "List.Push", "Box.Get")]
    res = run_linker_method(tmp_path, "probe.example/cmd/app", targets)
    assert [r["result"] for r in res] == ["PRESENT", "PRESENT", "PRESENT"], [r["details"] for r in res]
    v = triage.run_triage(triage.TriageRequest(case_id="probe", app=tmp_path, mode="targets", targets=targets),
                          default_runners(binary=binary))
    assert [e["result"] for e in v["per_symbol"]] == ["REACHABLE"] * 3 and v["verification"]["status"] == "PASSED"
