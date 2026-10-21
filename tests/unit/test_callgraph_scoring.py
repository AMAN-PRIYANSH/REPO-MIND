import json
import subprocess
from pathlib import Path

from vulntrace.eval import callgraph_score as cs
from vulntrace.eval.fixture_score import strip_timing
from vulntrace.schemas import validate

RESP = Path(__file__).resolve().parents[1] / "contract" / "responses"


def tiny_suite(tmp_path: Path) -> Path:
    d = tmp_path / "suite"
    d.mkdir()
    (d / "go.mod").write_text("module vtfixtures\n\ngo 1.21\n")
    t = [{"package": "vtfixtures/vulnlib", "symbol": "Parse"}]
    cases = [
        {"id": "direct_call", "category": "DIRECT", "main_package": "vtfixtures/cmd/direct_call", "targets": t,
         "truth": "REACHABLE", "rationale": "main calls Parse directly."},
        {"id": "dead_code", "category": "DEAD_CODE", "main_package": "vtfixtures/cmd/dead_code", "targets": t,
         "truth": "NOT_REACHABLE", "rationale": "Parse only in a function nothing calls."},
    ]
    (d / "manifest.json").write_text(json.dumps({"schema_version": "1.0", "module_dir": "fixtures/reachability",
                                                 "vulnerable_package": "vtfixtures/vulnlib", "cases": cases}))
    return d


def vta_runner(argv, timeout):
    req = json.loads(Path(argv[3]).read_text())
    name = "reach_path_found.json" if req["main_packages"] == ["vtfixtures/cmd/direct_call"] else "reach_no_path.json"
    return 0, (RESP / name).read_text(), ""


def linker_runner(present: bool):
    def runner(cmd, **kw):
        if cmd[1] == "version":
            return subprocess.CompletedProcess(cmd, 0, "go version go1.24.7 linux/amd64\n", "")
        if cmd[1] == "env":
            return subprocess.CompletedProcess(cmd, 0, "linux\namd64\n", "")
        if cmd[1] == "build":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "  1 T vtfixtures/vulnlib.Parse\n" if present else "", "")
    return runner


def test_predict_and_outcome():
    assert cs.predict_callgraph([{"result": "NO_PATH"}, {"result": "PATH_FOUND"}]) == "REACHABLE"
    assert cs.predict_callgraph([{"result": "NO_PATH"}, {"result": "ERROR"}]) == "ERROR"
    assert cs.predict_callgraph([{"result": "NO_PATH"}]) == "NOT_REACHABLE"
    assert cs.outcome("REACHABLE", "CANT_DETERMINE") == "CANT_DETERMINE"
    assert cs.outcome("REACHABLE", "NOT_REACHABLE") == "FALSE_NOT_REACHABLE"
    assert cs.outcome("NOT_REACHABLE", "REACHABLE") == "FALSE_REACHABLE"
    assert cs.outcome("NOT_REACHABLE", "ERROR") == "ERROR"


def test_score_vta_with_recorded_responses(tmp_path):
    rep = cs.score_callgraph(tiny_suite(tmp_path), cs.VTA_METHOD, binary=Path("fake"), runner=vta_runner)
    assert [c["outcome"] for c in rep["cases"]] == ["AGREE", "AGREE"]
    assert rep["counts"] == {"cases": 2, "agreements": 2, "false_not_reachable": 0, "false_reachable": 0,
                             "cant_determine": 0, "errors": 0}
    assert rep["environment"]["x_tools_version"] == "v0.42.0"


def test_score_combined_disagreement_and_agreement(tmp_path):
    suite = tiny_suite(tmp_path)
    rep = cs.score_combined(suite, binary=Path("fake"), vta_runner=vta_runner, linker_runner=linker_runner(True),
                            created_at="2026-10-21T00:00:00Z")
    by_id = {c["id"]: c for c in rep["cases"]}
    assert by_id["direct_call"]["predicted"] == "REACHABLE"
    # dead_code: VTA NO_PATH, linker PRESENT (fake) -> disagreement
    assert by_id["dead_code"]["predicted"] == "CANT_DETERMINE"
    assert by_id["dead_code"]["reason_codes"] == ["METHOD_DISAGREEMENT"]
    assert rep["counts"]["cant_determine"] == 1 and rep["counts"]["cant_determine_by_reason"] == {"METHOD_DISAGREEMENT": 1}
    assert rep["confusion"]["NOT_REACHABLE"]["CANT_DETERMINE"] == 1
    for c in rep["cases"]:
        validate("verdict", c["verdict"])
        assert c["verdict"]["target_app"]["module"] == "vtfixtures"
    rep2 = cs.score_combined(suite, binary=Path("fake"), vta_runner=vta_runner, linker_runner=linker_runner(False))
    assert {c["id"]: c["predicted"] for c in rep2["cases"]} == {"direct_call": "CANT_DETERMINE", "dead_code": "NOT_REACHABLE"}
    assert strip_timing(rep2) == strip_timing(
        cs.score_combined(suite, binary=Path("fake"), vta_runner=vta_runner, linker_runner=linker_runner(False)))


def naive_runner(argv, timeout):
    return 0, (RESP / "naive_no_path.json").read_text(), ""


def test_write_score_and_markdown(tmp_path):
    rep = cs.score_callgraph(tiny_suite(tmp_path), cs.NAIVE_METHOD, binary=Path("fake"), runner=naive_runner)
    jp, mp = cs.write_score(rep, tmp_path / "out")
    assert jp.name == "naive_score.json" and json.loads(jp.read_text())["method"] == "CALLGRAPH_NAIVE"
    assert "| direct_call | DIRECT | REACHABLE | NO_PATH | NOT_REACHABLE | FALSE_NOT_REACHABLE |" in mp.read_text()


def test_reach_response_for_a_naive_request_is_an_error(tmp_path):
    rep = cs.score_callgraph(tiny_suite(tmp_path), cs.NAIVE_METHOD, binary=Path("fake"), runner=vta_runner)
    assert {r["error"]["code"] for c in rep["cases"] for r in c["method_results"]} == {"BAD_RESPONSE"}
