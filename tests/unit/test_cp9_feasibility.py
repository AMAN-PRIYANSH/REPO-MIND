"""CP9: the path-feasibility filter stage, its verifier checks and the downgrade-only property.
No Go, no network: the helper's `feasibility` answers are written by hand in the shape of
schemas/helper_response.schema.json (the contract tests use real recordings)."""

import copy
import itertools
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.cp7_support import (FILES, GOOD_EDGES, LIB, LOCATED, MAIN_PKG, TARGET, FakeMethod, ctx,
                                    fake_inspect, path, vta_result)
from vulntrace.methods.callgraph import build_request
from vulntrace.pipeline import aggregate as ag, feasibility as fz, triage
from vulntrace.pipeline.cli import feasibility_settings
from vulntrace.schemas import validation_errors
from vulntrace.verdict import CANT_DETERMINE as CD, NOT_REACHABLE as NR, REACHABLE as R
from vulntrace.verifier import verify as vf

# --- a small world: main.go:4 calls mid (cmd/a/main.go:8), which calls lib.Parse ----------------------
MID = f"{MAIN_PKG}.mid"
WORLD = dict(FILES, **{"cmd/a/main.go": "package main\n\nfunc main() {\n\tlib.Parse(\"x\")\n\tmid()\n}\n\nfunc mid() {\n"
                                        "\tlib.Parse(\"y\")\n}\n"})
LONG_PATH = path(MAIN_PKG, TARGET, [(MID, "cmd/a/main.go", 5), (f"{LIB}.Parse", "cmd/a/main.go", 9)])
WORLD_EDGES = GOOD_EDGES | {(f"{MAIN_PKG}.main", MID, "cmd/a/main.go", 5), (MID, f"{LIB}.Parse", "cmd/a/main.go", 9)}
SHORT_PATH = path(MAIN_PKG, TARGET, [(f"{LIB}.Parse", "cmd/a/main.go", 4)])


def step(edge, pattern="F2", context=None, index=0):
    return {"pattern": pattern, "edge_index": index, "edge": copy.deepcopy(edge),
            "context_edges": copy.deepcopy(context or []), "reason": "fake reason"}


def answer(status, evidence=None, examined=None):
    return {"status": status, "max_examined_paths": 20, "examined": examined or [], "examined_truncated": False,
            "evidence_path": evidence, "evidence_source": "STATE_SEARCH" if status == fz.FEASIBLE else None,
            "undecided_reason": "STATE_LIMIT" if status == fz.UNDECIDED else None}


INFEASIBLE_SHORT = answer(fz.INFEASIBLE, examined=[{"length": 1, "first_infeasible": step(SHORT_PATH["edges"][0])}])


def entry(result, feas=None, paths=None, reason=None):
    e = {"target": dict(TARGET), "result": result, "reason_code": reason if result == CD else None,
         "methods": {"CALLGRAPH_VTA": "PATH_FOUND" if result == R else "NO_PATH",
                     "LINKER_PRESENCE": "PRESENT" if result == R else "ABSENT"},
         "method_errors": {}, "verified_path": None, "main_package": MAIN_PKG, "decides_verdict": True,
         "pre_verifier_result": result, "paths": paths if paths is not None else ([SHORT_PATH] if result == R else []),
         "verifier_failures": []}
    if feas is not None:
        e["feasibility"] = feas
    return e


def verdict_of(entries):
    v, r = ag.case_result(entries)
    return {"verdict": v, "reason_codes": r, "per_symbol": entries}


# --- the filter stage --------------------------------------------------------------------------------
def test_only_reachable_with_an_infeasible_answer_is_downgraded():
    entries = [entry(R, answer(fz.INFEASIBLE)), entry(R, answer(fz.FEASIBLE, SHORT_PATH)), entry(R, answer(fz.UNDECIDED)),
               entry(R), entry(NR), entry(CD, reason="METHOD_DISAGREEMENT", feas=answer(fz.INFEASIBLE))]
    before = copy.deepcopy(entries)
    out, n = fz.apply_filter(entries)
    assert entries == before, "the input must not be modified"
    assert n == 1
    assert [(e["result"], e["reason_code"]) for e in out] == [
        (CD, "PATHS_INFEASIBLE"), (R, None), (R, None), (R, None), (NR, None), (CD, "METHOD_DISAGREEMENT")]
    assert out[0]["pre_feasibility_result"] == R and out[0]["pre_verifier_result"] == CD
    assert "pre_feasibility_result" not in out[3], "no filter answer, no filter field"
    assert fz.status_counts(out) == {"INFEASIBLE": 1, "FEASIBLE": 1, "UNDECIDED": 1}


def test_filter_guard_rejects_anything_but_paths_infeasible():
    b = [entry(R, answer(fz.INFEASIBLE))]
    for bad in ([entry(NR, answer(fz.INFEASIBLE))], [entry(CD, answer(fz.FEASIBLE, SHORT_PATH), reason="PATHS_INFEASIBLE")],
                [entry(CD, answer(fz.INFEASIBLE), reason="VERIFIER_REJECTED")]):
        with pytest.raises(ag.DowngradeViolation):
            fz.assert_filter_downgrade_only(b, bad, R, ag.case_result(bad)[0])


def test_case_reason_is_paths_infeasible():
    out, _ = fz.apply_filter([entry(R, answer(fz.INFEASIBLE)), entry(NR)])
    assert ag.case_result(out) == (CD, ["PATHS_INFEASIBLE"])
    out, _ = fz.apply_filter([entry(R, answer(fz.INFEASIBLE)), entry(R, answer(fz.FEASIBLE, SHORT_PATH))])
    assert ag.case_result(out) == (R, []), "one feasible REACHABLE symbol keeps the case REACHABLE"


def test_settings_and_request():
    assert fz.helper_settings() == {"max_examined_paths": 20}
    with pytest.raises(ValueError):
        fz.helper_settings(0)
    assert feasibility_settings(SimpleNamespace(no_feasibility=True, max_examined_paths=20)) is None
    assert feasibility_settings(SimpleNamespace(no_feasibility=False, max_examined_paths=7)) == {"max_examined_paths": 7}
    plain = build_request("reach", "/tmp", "./cmd/a", [TARGET])
    assert "feasibility" not in plain, "a request without the filter is the pre-CP9 request"
    with_f = build_request("reach", "/tmp", "./cmd/a", [TARGET], feasibility={"max_examined_paths": 20})
    assert with_f["feasibility"] == {"max_examined_paths": 20}
    assert validation_errors("helper_request", with_f) == []


def test_deciding_pattern():
    e = entry(R, answer(fz.INFEASIBLE, examined=[{"length": 2, "first_infeasible": step(SHORT_PATH["edges"][0], "F1")},
                                                  {"length": 3, "first_infeasible": step(SHORT_PATH["edges"][0], "F3")}]))
    assert fz.first_patterns(e) == ["F1", "F3"] and fz.deciding_pattern(e) == "F1"
    assert fz.deciding_pattern(entry(R)) is None


# --- verifier checks of the filter's output -------------------------------------------------------
def world_ctx(**kw):
    kw.setdefault("located", LOCATED)
    return ctx(WORLD, WORLD_EDGES, **kw)


def test_evidence_path_becomes_the_verified_path():
    v = verdict_of([entry(R, answer(fz.FEASIBLE, LONG_PATH))])
    out = vf.verify(v, world_ctx())
    e = out["per_symbol"][0]
    assert e["result"] == R and e["verified_path"] == LONG_PATH
    assert out["verification"]["checks_by_kind"]["FILTERED_PATH"] == {"run": 1, "failed": 0, "skipped": 0}


def test_bad_evidence_path_is_rejected_even_when_a_method_path_passes():
    bad = copy.deepcopy(LONG_PATH)
    bad["edges"][1]["call_site"]["line"] = 3
    out = vf.verify(verdict_of([entry(R, answer(fz.FEASIBLE, bad))]), world_ctx())
    e = out["per_symbol"][0]
    assert (e["result"], e["reason_code"], e["verified_path"]) == (CD, "VERIFIER_REJECTED", None)
    assert any(f["check"] == "FILTERED_PATH" for f in e["verifier_failures"])
    assert validation_errors("verdict", {**out, "schema_version": "1.0", "case_id": "x", "target_app":
                                         {"path": "x", "module": None, "commit": None}, "statement":
                                         "Reachability only. This verdict does not assess exploitability.",
                                         "provenance": {"pipeline_version": "x", "helper_contract": "1.0",
                                                        "vulndb_commit": None, "created_at": "2026-11-17T00:00:00Z"}}) == []


def test_good_evidence_does_not_rescue_failed_method_paths():
    bad_method = copy.deepcopy(SHORT_PATH)
    bad_method["edges"][0]["call_site"]["line"] = 1
    out = vf.verify(verdict_of([entry(R, answer(fz.FEASIBLE, LONG_PATH), paths=[bad_method])]), world_ctx())
    assert out["per_symbol"][0]["result"] == CD, "the filter must never let the verifier accept what it rejects without it"


def test_undecided_keeps_the_old_verification():
    out = vf.verify(verdict_of([entry(R, answer(fz.UNDECIDED))]), world_ctx())
    e = out["per_symbol"][0]
    assert e["result"] == R and e["verified_path"] == SHORT_PATH
    assert out["verification"]["checks_by_kind"]["FILTERED_PATH"]["skipped"] == 1


def test_infeasible_steps_that_exist_keep_paths_infeasible():
    out, _ = fz.apply_filter([entry(R, INFEASIBLE_SHORT)])
    after = vf.verify(verdict_of(out), world_ctx())
    e = after["per_symbol"][0]
    assert (e["result"], e["reason_code"]) == (CD, "PATHS_INFEASIBLE")
    assert after["verification"]["checks_by_kind"]["INFEASIBLE_STEP"] == {"run": 1, "failed": 0, "skipped": 0}
    assert after["reason_codes"] == ["PATHS_INFEASIBLE"]


@pytest.mark.parametrize("corruption", ["line", "edge", "context"])
def test_infeasible_step_that_does_not_exist_is_rejected(corruption):
    st = step(LONG_PATH["edges"][1], context=[LONG_PATH["edges"][0]], index=1)
    if corruption == "line":
        st["edge"]["call_site"]["line"] = 2
    elif corruption == "edge":
        st["edge"]["callee"] = f"{LIB}.Elsewhere"
    else:
        st["context_edges"][0]["call_site"]["line"] = 99
    out, _ = fz.apply_filter([entry(R, answer(fz.INFEASIBLE, examined=[{"length": 2, "first_infeasible": st}]))])
    after = vf.verify(verdict_of(out), world_ctx())
    e = after["per_symbol"][0]
    assert (e["result"], e["reason_code"]) == (CD, "VERIFIER_REJECTED")
    assert any(f["check"] == "INFEASIBLE_STEP" for f in e["verifier_failures"])
    assert after["verification"]["infeasible_claims_rejected"] == 1
    assert after["reason_codes"] == ["VERIFIER_REJECTED"]


# --- end to end: the filter never makes a verdict stronger ------------------------------------------
# Each symbol S<i> of the fake library is called from main at cmd/a/main.go:4 (short path) and through
# mid at :5 and :9 (long path); the edges exist; the filter answer and the method results vary.
class FeasFake(FakeMethod):
    """A vta fake whose PATH_FOUND results carry a filter answer from `answers[(main, symbol)]`."""

    def __init__(self, table, answers):
        super().__init__("vta", table)
        self.answers = answers

    def __call__(self, module_dir, main, targets):
        out = super().__call__(module_dir, main, targets)
        for t, r in zip(targets, out):
            a = self.answers.get((main, t["symbol"]))
            if r["result"] == "PATH_FOUND" and a is not None:
                r["details"]["feasibility"] = copy.deepcopy(a)
        return out



def sym_target(i):
    return {"package": LIB, "symbol": f"S{i}"}


def sym_paths(i):
    t = sym_target(i)
    return (path(MAIN_PKG, t, [(f"{LIB}.S{i}", "cmd/a/main.go", 4)]),
            path(MAIN_PKG, t, [(MID, "cmd/a/main.go", 5), (f"{LIB}.S{i}", "cmd/a/main.go", 9)]))


def sym_answer(kind, i):
    short, long_ = sym_paths(i)
    bad_long = copy.deepcopy(long_)
    bad_long["edges"][1]["call_site"]["line"] = 2
    bad_step = step(short["edges"][0])
    bad_step["edge"]["call_site"]["line"] = 1
    return {"none": None,
            "feasible_good": answer(fz.FEASIBLE, long_),
            "feasible_bad": answer(fz.FEASIBLE, bad_long),
            "infeasible_good": answer(fz.INFEASIBLE, examined=[{"length": 1, "first_infeasible": step(short["edges"][0])}]),
            "infeasible_bad": answer(fz.INFEASIBLE, examined=[{"length": 1, "first_infeasible": bad_step}]),
            "undecided": answer(fz.UNDECIDED)}[kind]


ANSWER_KINDS = ("none", "feasible_good", "feasible_bad", "infeasible_good", "infeasible_bad", "undecided")
VTA_KINDS = ("path", "badpath", "nopath", "error")
LINK_KINDS = ("PRESENT", "ABSENT")


def run(symbols, on: bool):
    vta_table, link_table, answers, edges = {}, {}, {}, set(WORLD_EDGES)
    lib = "package lib\n"
    for i, (vk, lk, ak) in enumerate(symbols):
        short, _ = sym_paths(i)
        bad = copy.deepcopy(short)
        bad["edges"][0]["call_site"]["line"] = 2
        vta_table[(MAIN_PKG, LIB, f"S{i}")] = {"path": ("PATH_FOUND", {"paths": [short]}),
                                              "badpath": ("PATH_FOUND", {"paths": [bad]}),
                                              "nopath": ("NO_PATH", {}), "error": ("ERROR", {"code": "LOAD_FAILED"})}[vk]
        link_table[(MAIN_PKG, LIB, f"S{i}")] = (lk, {})
        answers[(MAIN_PKG, f"S{i}")] = sym_answer(ak, i)
        edges |= {(f"{MAIN_PKG}.main", f"{LIB}.S{i}", "cmd/a/main.go", 4), (MID, f"{LIB}.S{i}", "cmd/a/main.go", 9)}
        lib += f"\nfunc S{i}() {{\n}}\n"
    world = dict(WORLD, **{"/modcache/example.com/lib@v1.0.0/lib.go": lib})
    runners = triage.Runners(vta=FeasFake(vta_table, answers if on else {}), linker=FakeMethod("linker", link_table),
                             inspect=fake_inspect(mains=(MAIN_PKG,)),
                             verifier_ctx=lambda info, inc: ctx(world, edges, located=LOCATED),
                             feasibility=({"max_examined_paths": 20} if on else None))
    req = triage.TriageRequest(case_id="t", app=Path("/fake/app"), mode="targets",
                               targets=[sym_target(i) for i in range(len(symbols))], created_at="2026-11-17T00:00:00Z")
    return triage.run_triage(req, runners)


def test_filter_off_output_has_no_cp9_fields():
    v = run([("path", "PRESENT", "infeasible_good")], on=False)
    assert "feasibility" not in v
    assert all("feasibility" not in e and "pre_feasibility_result" not in e for e in v["per_symbol"])


def test_world_is_consistent():
    """Sanity of the fake world: with good paths and answers, REACHABLE survives the verifier and the
    filter changes what it should (otherwise the property test below would prove nothing)."""
    assert run([("path", "PRESENT", "none")], False)["verdict"] == R
    v = run([("path", "PRESENT", "feasible_good")], True)
    assert v["verdict"] == R and v["per_symbol"][0]["verified_path"] == sym_paths(0)[1]
    v = run([("path", "PRESENT", "infeasible_good")], True)
    assert (v["verdict"], v["reason_codes"]) == (CD, ["PATHS_INFEASIBLE"])
    assert v["feasibility"] == {"enabled": True, "max_examined_paths": 20, "downgraded": 1,
                                "by_status": {"INFEASIBLE": 1}, "pre_filter_verdict": R, "pre_filter_reason_codes": []}
    v = run([("path", "PRESENT", "infeasible_bad")], True)
    assert (v["verdict"], v["reason_codes"]) == (CD, ["VERIFIER_REJECTED"])
    assert run([("path", "PRESENT", "feasible_bad")], True)["verdict"] == CD
    assert run([("path", "PRESENT", "undecided")], True)["verdict"] == R


def test_filter_on_is_never_stronger_than_filter_off():
    kinds = list(itertools.product(VTA_KINDS, LINK_KINDS, ANSWER_KINDS))
    pairs = random.Random(9).sample(list(itertools.product(kinds, repeat=2)), 300)
    for combo in [(k,) for k in kinds] + pairs:
        off, on = run(list(combo), False), run(list(combo), True)
        assert ag.not_stronger(off["verdict"], on["verdict"]), (combo, off["verdict"], on["verdict"])
        for a, b in zip(off["per_symbol"], on["per_symbol"]):
            assert b["result"] in (a["result"], CD), (combo, a["result"], b["result"])
            assert b["methods"] == a["methods"] and b["paths"] == a["paths"]
            if b["result"] != a["result"]:
                assert b["reason_code"] in ("PATHS_INFEASIBLE", "VERIFIER_REJECTED"), (combo, b["reason_code"])
        assert validation_errors("verdict", on) == [], (combo, validation_errors("verdict", on)[:2])
