"""Contract tests for the CP5b helper modes (lift, callers, callees): recorded responses are
validated and mapped, every new status and error is covered, and the CP2 recordings still validate
against the extended schemas. These never need Go."""

import json
import subprocess
from pathlib import Path

import pytest

from vulntrace.methods.helper import HelperError, parse_response, run_helper
from vulntrace.methods.lift import (
    NEIGHBOR_METHOD, build_query_request, lifted_symbols, run_callees, run_callers, run_lift, to_lift_records,
)
from vulntrace.schemas import validate

pytest.importorskip("jsonschema")

DIR = Path(__file__).resolve().parent / "responses_cp5b"
INDEX = json.loads((DIR / "index.json").read_text(encoding="utf-8"))
FAKE = Path("vt-helper-not-run")


def recorded(name):
    return (DIR / name).read_text(encoding="utf-8")


def replay(name, rc=0):
    return lambda argv, timeout: (rc, recorded(name), "vt-helper: log\n")


def t(pkg, sym):
    return {"package": f"vtlift/{pkg}", "symbol": sym}


LIFT_SEEDS = [t("private_helper", "parse"), t("interface_call", "impl.run"), t("func_value", "step"),
              t("diamond", "sink"), t("root_only", "orphan"), t("already_exported", "Parse"),
              t("generic_seed", "Map"), t("private_helper", "Nope"), {"package": "not/there", "symbol": "X"}]


@pytest.mark.parametrize("entry", INDEX, ids=[e["file"] for e in INDEX])
def test_every_recording_validates(entry):
    resp = parse_response(recorded(entry["file"]), entry["mode"], entry["exit_code"])
    assert resp["ok"] == (entry["exit_code"] == 0)


def test_older_recordings_still_validate_against_the_extended_schemas():
    old = json.loads((Path(__file__).resolve().parent / "responses" / "index.json").read_text(encoding="utf-8"))
    assert len(old) == 12
    for e in old:
        text = (Path(__file__).resolve().parent / "responses" / e["file"]).read_text(encoding="utf-8")
        parse_response(text, e["mode"], e["exit_code"])


def test_every_lift_status_and_error_code_is_recorded():
    statuses, codes, results = set(), set(), []
    for e in INDEX:
        resp = json.loads(recorded(e["file"]))
        if not resp["ok"]:
            codes.add(resp["error"]["code"])
        elif resp["mode"] == "lift":
            for r in resp["results"]:
                statuses.add(r["status"])
                if r["error"]:
                    codes.add(r["error"]["code"])
    assert statuses == {"LIFTED", "ALREADY_EXPORTED", "ROOT_ONLY", "PACKAGE_NOT_IN_PROGRAM", "ERROR"}
    assert {"LOAD_FAILED", "BAD_REQUEST", "CONTRACT_MISMATCH", "TARGET_NOT_FOUND", "UNSUPPORTED_SYMBOL_FORM",
            "PACKAGE_NOT_LOADED"} <= codes


def test_lift_records_carry_both_rules_and_validate():
    recs = run_lift(Path("."), LIFT_SEEDS, binary=FAKE, runner=replay("lift_ok.json"))
    by = {r["target"]["symbol"]: r for r in recs}
    for r in recs:
        validate("lift_record", r)
    assert by["parse"]["status"] == "LIFTED" and lifted_symbols(by["parse"], "NEAREST") == {"Parse"}
    assert lifted_symbols(by["sink"], "NEAREST") == {"Left", "Right"}
    assert lifted_symbols(by["sink"], "ALL") == {"Left", "Right", "Top"}      # the rules differ on the diamond
    assert by["orphan"]["status"] == "ROOT_ONLY" and lifted_symbols(by["orphan"], "ALL") == set()
    assert by["Parse"]["status"] == "ALREADY_EXPORTED" and lifted_symbols(by["Parse"], "ALL") == {"Parse"}
    assert by["Map"]["status"] == "ERROR" and by["Map"]["error"]["code"] == "UNSUPPORTED_SYMBOL_FORM"
    assert by["Nope"]["error"]["code"] == "TARGET_NOT_FOUND"
    assert by["X"]["status"] == "PACKAGE_NOT_IN_PROGRAM" and by["X"]["details"]["package_not_in_program"] is True
    assert by["impl.run"]["rules"]["NEAREST"]["entries"][0]["dynamic"] is True


def test_an_invented_symbol_never_appears_for_root_only():
    recs = run_lift(Path("."), LIFT_SEEDS, binary=FAKE, runner=replay("lift_ok.json"))
    for r in recs:
        if r["status"] in ("ROOT_ONLY", "ERROR", "PACKAGE_NOT_IN_PROGRAM"):
            assert all(not v["entries"] for v in r["rules"].values()), r["target"]


def test_depth_limit_is_reported_and_not_a_silent_root_only():
    r = run_lift(Path("."), [t("chain", "a")], binary=FAKE, runner=replay("lift_depth_limit.json"))[0]
    assert r["status"] == "ROOT_ONLY" and r["rules"]["ALL"]["depth_limit_reached"] is True


def test_skipped_packages_are_counted_and_named_per_target():
    recs = run_lift(Path("."), [{"package": "bm/good", "symbol": "helper"}, {"package": "bm/user", "symbol": "X"}],
                    binary=FAKE, runner=replay("lift_package_not_loaded.json"))
    assert recs[0]["status"] == "LIFTED"
    assert recs[1]["status"] == "ERROR" and recs[1]["error"]["code"] == "PACKAGE_NOT_LOADED"
    load = recs[0]["details"]["load"]
    assert load["packages_skipped"] == 2 and load["packages_matched"] == 3 and len(load["first_errors"]) == 2


@pytest.mark.parametrize("name,code", [("error_lift_load_failed_dir.json", "LOAD_FAILED"),
                                       ("error_lift_load_failed_nothing_loads.json", "LOAD_FAILED"),
                                       ("error_lift_bad_request.json", "BAD_REQUEST"),
                                       ("error_lift_contract_mismatch.json", "CONTRACT_MISMATCH")])
def test_response_level_errors_become_error_records_for_every_seed(name, code):
    seeds = [t("diamond", "sink"), t("chain", "a")]
    recs = run_lift(Path("."), seeds, binary=FAKE, runner=replay(name, 1))
    assert [r["status"] for r in recs] == ["ERROR", "ERROR"]
    assert all(r["error"]["code"] == code and r["rules"] == {} for r in recs)
    for r in recs:
        validate("lift_record", r)


def test_load_failed_keeps_a_one_line_message():
    recs = run_lift(Path("."), [t("diamond", "sink")], binary=FAKE, runner=replay("error_lift_load_failed_nothing_loads.json", 1))
    assert "\n" not in recs[0]["error"]["message"] and recs[0]["error"]["message"].startswith("nl: ")


def test_callers_two_hops_and_empty_result():
    recs = run_callers(Path("."), [t("diamond", "sink"), t("never_called", "dead")], hops=2, binary=FAKE,
                       runner=replay("callers_two_hops.json"))
    for r in recs:
        validate("neighbor_record", r)
    assert recs[0]["method"] == NEIGHBOR_METHOD and recs[0]["query"] == "callers" and recs[0]["result"] == "FOUND"
    assert sorted((e["hop"], e["other"]["symbol"]) for e in recs[0]["edges"]) == [
        (1, "left"), (1, "right"), (2, "Left"), (2, "Right")]
    assert all(e["call_site"]["file"] and e["call_site"]["line"] > 0 for e in recs[0]["edges"])
    assert recs[1]["result"] == "NONE" and recs[1]["edges"] == []


def test_callees_dynamic_edge_truncation_and_missing_package():
    recs = run_callees(Path("."), [t("diamond", "Top"), t("interface_call", "Do")], binary=FAKE,
                       runner=replay("callees_one_hop.json"))
    assert {e["kind"] for e in recs[1]["edges"]} == {"DYNAMIC"} and recs[0]["truncated"] is False
    trunc = run_callees(Path("."), [t("diamond", "Top")], max_results=1, binary=FAKE, runner=replay("callees_truncated.json"))[0]
    assert trunc["truncated"] is True and len(trunc["edges"]) == 1
    gone = run_callers(Path("."), [{"package": "not/there", "symbol": "X"}], binary=FAKE,
                       runner=replay("callers_not_in_program.json"))[0]
    assert gone["result"] == "PACKAGE_NOT_IN_PROGRAM" and gone["details"]["package_not_in_program"] is True


def test_neighbor_errors_map_like_the_other_modes():
    r = run_callers(Path("."), [t("diamond", "sink")], binary=FAKE, runner=replay("error_callers_load_failed_dir.json", 1))[0]
    assert r["result"] == "ERROR" and r["error"]["code"] == "LOAD_FAILED" and r["edges"] == []
    validate("neighbor_record", r)
    wrong_mode = run_callees(Path("."), [t("diamond", "sink")], binary=FAKE, runner=replay("error_callers_load_failed_dir.json", 1))[0]
    assert wrong_mode["error"]["code"] == "BAD_RESPONSE"   # a callers response is not an answer to a callees request


def test_python_side_codes_for_the_new_modes():
    def timeout(argv, to):
        raise subprocess.TimeoutExpired(argv, to)

    def missing(argv, to):
        raise FileNotFoundError(argv[0])

    assert run_lift(Path("."), [t("diamond", "sink")], binary=FAKE, runner=timeout, timeout=0.01)[0]["error"]["code"] == "TIMEOUT"
    assert run_callers(Path("."), [t("diamond", "sink")], binary=FAKE, runner=missing)[0]["error"]["code"] == "HELPER_MISSING"
    bad = lambda argv, to: (1, "not json", "")  # noqa: E731
    assert run_lift(Path("."), [t("diamond", "sink")], binary=FAKE, runner=bad)[0]["error"]["code"] == "BAD_RESPONSE"


def test_results_for_other_seeds_are_rejected():
    recs = run_lift(Path("."), [t("other", "thing")], binary=FAKE, runner=replay("lift_depth_limit.json"))
    assert recs[0]["error"]["code"] == "BAD_RESPONSE"


def test_response_mode_must_match():
    with pytest.raises(HelperError) as exc:
        parse_response(recorded("callers_two_hops.json"), "lift")
    assert exc.value.code == "BAD_RESPONSE"


def test_requests_are_schema_valid(tmp_path):
    lift = build_query_request("lift", tmp_path, [t("diamond", "sink")])
    validate("helper_request", lift)
    assert lift["lift_rules"] == ["NEAREST", "ALL"] and lift["limits"]["max_lift_depth"] == 10
    app = build_query_request("callers", tmp_path, [t("diamond", "sink")], main_packages=["x\\cmd\\y"], external=True,
                              limits={"max_hops": 3})
    validate("helper_request", app)
    assert app["main_packages"] == ["x/cmd/y"] and app["external"] is True and "\\" not in app["module_dir"]
    seen = {}

    def runner(argv, to):
        seen["req"] = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        return 0, recorded("lift_depth_limit.json"), ""
    run_helper("lift", build_query_request("lift", tmp_path, [t("chain", "a")], limits={"max_lift_depth": 2}),
               binary=FAKE, runner=runner)
    assert seen["req"]["mode"] == "lift" and seen["req"]["limits"]["max_lift_depth"] == 2
    with pytest.raises(ValueError):
        run_helper("lift", {"contract_version": "1.0", "mode": "lift"}, binary=FAKE, runner=runner)   # no module_dir/targets


def test_to_lift_records_handles_a_missing_response_and_error_together():
    recs = to_lift_records([t("a", "b")], None, HelperError("TIMEOUT", "x"), 5)
    assert recs[0]["error"]["code"] == "TIMEOUT" and recs[0]["duration_ms"] == 5
