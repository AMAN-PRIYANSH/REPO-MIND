"""Contract tests: recorded helper responses, validated and mapped. These never need Go."""

import json
import subprocess
from pathlib import Path

import pytest

from vulntrace.methods.callgraph import build_request, run_vta_method
from vulntrace.methods.helper import HelperError, parse_response, run_helper
from vulntrace.methods.naive import run_naive_method
from vulntrace.schemas import validate

pytest.importorskip("jsonschema")

RESP_DIR = Path(__file__).resolve().parent / "responses"
INDEX = json.loads((RESP_DIR / "index.json").read_text(encoding="utf-8"))
HELPER_ERROR_CODES = {"BAD_REQUEST", "CONTRACT_MISMATCH", "LOAD_FAILED", "TYPE_ERRORS", "TARGET_NOT_FOUND", "INTERNAL"}
PER_TARGET_CODES = {"TARGET_NOT_FOUND", "UNSUPPORTED_SYMBOL_FORM"}
FAKE_BINARY = Path("vt-helper-not-run")
PARSE = {"package": "vtfixtures/vulnlib", "symbol": "Parse"}


def recorded(name: str) -> str:
    return (RESP_DIR / name).read_text(encoding="utf-8")


def replay(name: str, rc: int = 0):
    def runner(argv, timeout):
        assert argv[0] == str(FAKE_BINARY) and argv[2] == "--request"
        return rc, recorded(name), "vt-helper: log line\n"
    return runner


@pytest.mark.parametrize("entry", INDEX, ids=[e["file"] for e in INDEX])
def test_every_recorded_response_validates(entry):
    resp = parse_response(recorded(entry["file"]), entry["mode"], entry["exit_code"])
    assert resp["ok"] == (entry["exit_code"] == 0)


def test_recordings_cover_every_helper_error_code():
    codes = set()
    for e in INDEX:
        resp = json.loads(recorded(e["file"]))
        if not resp["ok"]:
            codes.add(resp["error"]["code"])
        else:
            for r in resp["results"] if resp["mode"] in ("reach", "naive") else []:
                if r["error"]:
                    codes.add(r["error"]["code"])
    assert HELPER_ERROR_CODES | PER_TARGET_CODES <= codes


def test_synthesised_responses_are_only_the_ones_the_helper_cannot_produce():
    synth = {e["file"] for e in INDEX if e["provenance"] != "RECORDED"}
    assert synth == {"error_internal.json", "error_target_not_found.json"}


@pytest.mark.parametrize("entry", [e for e in INDEX if e["exit_code"] != 0], ids=lambda e: e["file"])
def test_response_level_errors_map_to_error_results(entry):
    code = json.loads(recorded(entry["file"]))["error"]["code"]
    targets = [PARSE, {"package": "p", "symbol": "F"}]
    results = run_vta_method(Path("."), "vtfixtures/cmd/direct_call", targets, binary=FAKE_BINARY,
                             runner=replay(entry["file"], 1))
    assert [r["result"] for r in results] == ["ERROR", "ERROR"]
    assert all(r["error"]["code"] == code for r in results)
    for r in results:
        validate("method_result", r)


def test_per_target_errors_never_become_no_path():
    """A symbol missing from a loaded package is always an error, never NO_PATH."""
    targets = [PARSE, {"package": "vtfixtures/vulnlib", "symbol": "Missing"},
               {"package": "vtfixtures/initdep", "symbol": "X"}, {"package": "vtfixtures/vulnlib", "symbol": "a.b.c"}]
    results = run_vta_method(Path("."), "vtfixtures/cmd/direct_call", targets, binary=FAKE_BINARY,
                             runner=replay("reach_target_errors.json"))
    got = [(r["result"], (r["error"] or {}).get("code")) for r in results]
    assert got == [("PATH_FOUND", None), ("ERROR", "TARGET_NOT_FOUND"), ("NO_PATH", None),
                   ("ERROR", "UNSUPPORTED_SYMBOL_FORM")]
    for r in results:
        validate("method_result", r)


def test_package_not_in_program_becomes_no_path_not_target_not_found():
    """Interfaces contract, section 2 exception: an unloaded package is NO_PATH, not an error."""
    targets = [PARSE, {"package": "vtfixtures/vulnlib", "symbol": "Missing"},
               {"package": "vtfixtures/initdep", "symbol": "X"}, {"package": "vtfixtures/vulnlib", "symbol": "a.b.c"}]
    results = run_vta_method(Path("."), "vtfixtures/cmd/direct_call", targets, binary=FAKE_BINARY,
                             runner=replay("reach_target_errors.json"))
    not_in_program = results[2]
    assert not_in_program["result"] == "NO_PATH"
    assert not_in_program["error"] is None
    assert not_in_program["details"]["package_not_in_program"] is True
    assert results[0]["details"]["package_not_in_program"] is False
    validate("method_result", not_in_program)


def test_path_found_details_carry_the_shortest_path():
    r = run_vta_method(Path("."), "vtfixtures/cmd/direct_call", [PARSE], binary=FAKE_BINARY,
                       runner=replay("reach_path_found.json"))[0]
    assert r["method"] == "CALLGRAPH_VTA" and r["result"] == "PATH_FOUND" and r["error"] is None
    edge = r["details"]["path"]["edges"][0]
    assert edge == {"caller": "vtfixtures/cmd/direct_call.main", "callee": "vtfixtures/vulnlib.Parse",
                    "call_site": {"file": "cmd/direct_call/main.go", "line": 10}, "kind": "STATIC"}
    assert r["details"]["toolchain"]["x_tools_version"] == "v0.42.0"
    assert r["details"]["stats"]["callgraph_nodes"] > 0


def test_no_path_and_naive_method_name():
    r = run_vta_method(Path("."), "vtfixtures/cmd/dead_code", [PARSE], binary=FAKE_BINARY,
                       runner=replay("reach_no_path.json"))[0]
    assert r["result"] == "NO_PATH" and r["details"]["path"] is None
    n = run_naive_method(Path("."), "vtfixtures/cmd/func_value_map", [PARSE], binary=FAKE_BINARY,
                         runner=replay("naive_no_path.json"))[0]
    assert n["method"] == "CALLGRAPH_NAIVE" and n["result"] == "NO_PATH"
    validate("method_result", n)


def test_edges_and_funcs_responses_parse():
    e = parse_response(recorded("edges.json"), "edges")
    assert [x["exists"] for x in e["results"]] == [True, False]
    f = parse_response(recorded("funcs.json"), "funcs")
    syms = [fn["symbol"] for fn in f["results"][0]["functions"]]
    assert "Parse" in syms and "Impl.Run" in syms and "PImpl.Run" in syms


# Python-side codes -----------------------------------------------------------------------

def _codes(results):
    return [r["error"]["code"] for r in results]


def test_timeout_maps_to_timeout():
    def runner(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)
    results = run_vta_method(Path("."), "m", [PARSE], binary=FAKE_BINARY, runner=runner, timeout=0.01)
    assert _codes(results) == ["TIMEOUT"]
    validate("method_result", results[0])


def test_unrunnable_binary_maps_to_helper_missing():
    def runner(argv, timeout):
        raise FileNotFoundError(argv[0])
    assert _codes(run_vta_method(Path("."), "m", [PARSE], binary=FAKE_BINARY, runner=runner)) == ["HELPER_MISSING"]


def test_unbuildable_helper_maps_to_helper_missing(monkeypatch):
    import vulntrace.methods.helper as h

    def no_helper():
        raise HelperError("HELPER_MISSING", "go toolchain not found")
    monkeypatch.setattr(h, "ensure_helper", no_helper)
    assert _codes(run_vta_method(Path("."), "m", [PARSE], runner=replay("reach_path_found.json"))) == ["HELPER_MISSING"]


@pytest.mark.parametrize("stdout,code", [
    ("", "BAD_RESPONSE"),
    ("not json", "BAD_RESPONSE"),
    ("[1]", "BAD_RESPONSE"),
    (json.dumps({"contract_version": "1.0", "ok": True, "mode": "reach"}), "BAD_RESPONSE"),
    (json.dumps({"contract_version": "2.0", "ok": True, "mode": "reach"}), "CONTRACT_MISMATCH"),
])
def test_malformed_responses(stdout, code):
    runner = lambda argv, timeout: (1, stdout, "")  # noqa: E731
    assert _codes(run_vta_method(Path("."), "m", [PARSE], binary=FAKE_BINARY, runner=runner)) == [code]


def test_response_for_other_targets_is_rejected():
    results = run_vta_method(Path("."), "m", [{"package": "x", "symbol": "Y"}], binary=FAKE_BINARY,
                             runner=replay("reach_path_found.json"))
    assert _codes(results) == ["BAD_RESPONSE"]


def test_response_mode_must_match_request_mode():
    with pytest.raises(HelperError) as exc:
        parse_response(recorded("naive_no_path.json"), "reach")
    assert exc.value.code == "BAD_RESPONSE"


def test_request_is_schema_valid_and_normalises_windows_package_paths(tmp_path):
    req = build_request("reach", tmp_path, "vtfixtures\\cmd\\direct_call", [PARSE])
    validate("helper_request", req)
    assert req["main_packages"] == ["vtfixtures/cmd/direct_call"]
    assert "\\" not in req["module_dir"]


def test_request_file_is_written_and_passed(tmp_path):
    seen = {}

    def runner(argv, timeout):
        seen["request"] = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        seen["mode"], seen["timeout"] = argv[1], timeout
        return 0, recorded("reach_path_found.json"), ""
    run_helper("reach", build_request("reach", tmp_path, "vtfixtures/cmd/direct_call", [PARSE]),
               binary=FAKE_BINARY, runner=runner, timeout=12)
    assert seen["mode"] == "reach" and seen["timeout"] == 12 and seen["request"]["targets"] == [PARSE]


def test_invalid_request_is_a_programming_error():
    with pytest.raises(ValueError):
        run_helper("reach", {"contract_version": "1.0", "mode": "reach"}, binary=FAKE_BINARY,
                   runner=replay("reach_path_found.json"))
