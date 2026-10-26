"""CP7 evidence verifier with fakes: corrupted paths are rejected, and no input makes a verdict stronger."""

import copy
import itertools
import random

import pytest

from tests.unit.cp7_support import (FILES, GOOD_EDGES, GOOD_PATH, LIB, LOCATED, MAIN_PKG, TARGET, ctx, good_ctx, path)
from vulntrace.pipeline import aggregate as ag
from vulntrace.schemas import validation_errors
from vulntrace.verdict import CANT_DETERMINE as CD, NOT_REACHABLE as NR, REACHABLE as R, STATEMENT
from vulntrace.verifier import verify as vf

METHODS = {R: ("PATH_FOUND", "PRESENT"), NR: ("NO_PATH", "ABSENT"), CD: ("NO_PATH", "PRESENT")}


def entry(result=R, paths=None, target=TARGET, main=MAIN_PKG, not_in_program=False, paths_omitted=None):
    vta, ln = METHODS[result]
    return {"target": dict(target), "result": result, "reason_code": "METHOD_DISAGREEMENT" if result == CD else None,
            "methods": {"CALLGRAPH_VTA": vta, "LINKER_PRESENCE": ln}, "method_errors": {}, "verified_path": None,
            "main_package": main, "origin": "FIXTURE", "rank": None, "score": None, "candidate_id": None,
            "decides_verdict": True, "evidence_level": "TARGET_LEVEL", "pre_verifier_result": result,
            "paths": copy.deepcopy(paths if paths is not None else ([GOOD_PATH] if result == R else [])),
            "paths_omitted": paths_omitted, "package_not_in_program": not_in_program, "linker_matched": [],
            "verifier_failures": []}


def verdict(entries, case=None):
    case = case or ag.case_result(entries)
    return {"schema_version": "1.0", "case_id": "T", "target_app": {"path": "app", "module": "example.com/app",
                                                                    "commit": "c0ffee"},
            "verdict": case[0], "reason_codes": case[1], "per_symbol": entries,
            "verification": {"status": "NOT_RUN", "checks_run": 0, "failures": []}, "statement": STATEMENT,
            "provenance": {"pipeline_version": "0.1.0", "helper_contract": "1.0", "vulndb_commit": None,
                           "created_at": "2026-10-26T00:00:00Z"}}


def test_correct_path_passes_and_is_kept_verbatim():
    v = verdict([entry(R)])
    out = vf.verify(v, good_ctx())
    e = out["per_symbol"][0]
    assert e["result"] == R and e["verified_path"] == GOOD_PATH
    assert out["verification"]["status"] == "PASSED" and out["verification"]["downgraded"] == 0
    assert out["verdict"] == R
    assert v["per_symbol"][0]["verified_path"] is None, "the input must not be modified"
    assert not validation_errors("verdict", out)


def test_wrong_line_is_rejected():
    bad = copy.deepcopy(GOOD_PATH)
    bad["edges"][0]["call_site"]["line"] = 1           # inside the file, outside main's body
    out = vf.verify(verdict([entry(R, paths=[bad])]), good_ctx())
    e = out["per_symbol"][0]
    assert (e["result"], e["reason_code"]) == (CD, "VERIFIER_REJECTED")
    checks = {f["check"] for f in e["verifier_failures"]}
    assert {"CALL_SITE", "EDGE_EXISTS", "REACHABLE_HAS_PATH"} <= checks
    assert out["verdict"] == CD and out["reason_codes"] == ["VERIFIER_REJECTED"]
    assert out["verification"]["status"] == "FAILED"


def test_line_past_end_of_file_is_rejected():
    bad = copy.deepcopy(GOOD_PATH)
    bad["edges"][0]["call_site"]["line"] = 999
    e = vf.verify(verdict([entry(R, paths=[bad])]), good_ctx())["per_symbol"][0]
    assert e["result"] == CD and any("does not exist" in f["reason"] for f in e["verifier_failures"])


def test_missing_edge_is_rejected():
    out = vf.verify(verdict([entry(R)]), ctx(FILES, edges=set(), located=LOCATED))
    e = out["per_symbol"][0]
    assert (e["result"], e["reason_code"]) == (CD, "VERIFIER_REJECTED")
    assert "EDGE_EXISTS" in {f["check"] for f in e["verifier_failures"]}


def test_fabricated_hop_is_rejected():
    bad = path(MAIN_PKG, TARGET, [(f"{LIB}.Safe", "cmd/a/main.go", 4), (f"{LIB}.Parse", "cmd/a/main.go", 4)])
    e = vf.verify(verdict([entry(R, paths=[bad])]), good_ctx())["per_symbol"][0]
    assert e["result"] == CD


def test_second_path_can_verify_when_first_is_corrupt():
    bad = copy.deepcopy(GOOD_PATH)
    bad["edges"][0]["call_site"]["line"] = 1
    out = vf.verify(verdict([entry(R, paths=[bad, GOOD_PATH])]), good_ctx())
    e = out["per_symbol"][0]
    assert e["result"] == R and e["verified_path"] == GOOD_PATH and e["verifier_failures"] == []


def test_reachable_without_paths_is_rejected():
    out = vf.verify(verdict([entry(R, paths=[], paths_omitted="MAX_PATH_LENGTH")]), good_ctx())
    e = out["per_symbol"][0]
    assert e["result"] == CD and any("MAX_PATH_LENGTH" in f["reason"] for f in e["verifier_failures"])


def test_target_must_be_declared():
    located = {LIB: vf.PackageLocation(vf.FOUND, files=["/modcache/example.com/lib@v1.0.0/lib.go"])}
    other = {"package": LIB, "symbol": "Missing"}
    p = path(MAIN_PKG, other, [(f"{LIB}.Missing", "cmd/a/main.go", 4)])
    edges = {(f"{MAIN_PKG}.main", f"{LIB}.Missing", "cmd/a/main.go", 4)}
    e = vf.verify(verdict([entry(R, paths=[p], target=other)]), ctx(FILES, edges, located))["per_symbol"][0]
    assert e["result"] == CD and "TARGET_EXISTS" in {f["check"] for f in e["verifier_failures"]}


def test_not_reachable_mapping_error_is_rejected():
    """A package that should be in the build but cannot be found (a wrong import path) must not read as NOT_REACHABLE."""
    located = {LIB: vf.PackageLocation(vf.MISSING, reason="module example.com/lib is in the build")}
    out = vf.verify(verdict([entry(NR, not_in_program=True)]), ctx(FILES, GOOD_EDGES, located))
    assert out["per_symbol"][0]["result"] == CD and out["verdict"] == CD


def test_not_reachable_package_outside_build_passes():
    located = {LIB: vf.PackageLocation(vf.NOT_IN_BUILD, reason="no module provides it")}
    out = vf.verify(verdict([entry(NR, not_in_program=True)]), ctx(FILES, GOOD_EDGES, located))
    assert out["per_symbol"][0]["result"] == NR and out["verdict"] == NR
    assert out["verification"]["checks_by_kind"]["TARGET_EXISTS"]["skipped"] == 1


def test_not_in_build_needs_the_helper_to_agree():
    located = {LIB: vf.PackageLocation(vf.NOT_IN_BUILD, reason="no module provides it")}
    out = vf.verify(verdict([entry(NR, not_in_program=False)]), ctx(FILES, GOOD_EDGES, located))
    assert out["per_symbol"][0]["result"] == CD


def test_edges_error_rejects_reachable():
    out = vf.verify(verdict([entry(R)]), good_ctx(edges_error="edges: TIMEOUT"))
    e = out["per_symbol"][0]
    assert e["result"] == CD and "VERIFIER_ERROR" in {f["check"] for f in e["verifier_failures"]}


def test_cant_determine_entries_are_not_touched():
    v = verdict([entry(CD)])
    out = vf.verify(v, ctx({}, set(), {}))
    assert out["per_symbol"] == v["per_symbol"] and out["verification"]["status"] == "NOT_RUN"


def test_incomplete_coverage_is_kept_when_recomputing():
    v = verdict([entry(R), entry(NR, target={"package": LIB, "symbol": "G"})], case=(R, []))
    out = vf.verify(v, ctx(FILES, set(), LOCATED, incomplete=True))
    assert out["verdict"] == CD and "INCOMPLETE_COVERAGE" in out["reason_codes"]


# --- no input makes the verdict stronger -----------------------------------------------------------
TARGET_OUTCOMES = ("FOUND_DECLARED", "FOUND_UNDECLARED", "MISSING", "NOT_IN_BUILD", "UNKNOWN")
PATH_OUTCOMES = ("GOOD", "BAD_LINE", "NO_EDGE", "NO_PATH", "BAD_STRUCTURE")


def _world(target_outcome: str, path_outcome: str, symbol: str):
    t = {"package": LIB, "symbol": symbol}
    p = path(MAIN_PKG, t, [(f"{LIB}.{symbol}", "cmd/a/main.go", 4)])
    lib = f"package lib\n\nfunc {symbol if target_outcome == 'FOUND_DECLARED' else 'Other'}() {{\n}}\n"
    files = dict(FILES, **{"/modcache/lib.go": lib})
    loc = {"FOUND_DECLARED": vf.PackageLocation(vf.FOUND, files=["/modcache/lib.go"]),
           "FOUND_UNDECLARED": vf.PackageLocation(vf.FOUND, files=["/modcache/lib.go"]),
           "MISSING": vf.PackageLocation(vf.MISSING), "NOT_IN_BUILD": vf.PackageLocation(vf.NOT_IN_BUILD),
           "UNKNOWN": vf.PackageLocation(vf.UNKNOWN)}[target_outcome]
    edges = {(f"{MAIN_PKG}.main", f"{LIB}.{symbol}", "cmd/a/main.go", 4)}
    if path_outcome == "BAD_LINE":
        p["edges"][0]["call_site"]["line"] = 1
    elif path_outcome == "NO_EDGE":
        edges = set()
    elif path_outcome == "BAD_STRUCTURE":
        p["entry"]["symbol"] = "helper"
    paths = [] if path_outcome == "NO_PATH" else [p]
    return t, paths, files, loc, edges


@pytest.mark.parametrize("n_entries", [1, 2])
def test_exhaustive_never_stronger(n_entries):
    combos = list(itertools.product((R, NR, CD), TARGET_OUTCOMES, PATH_OUTCOMES, (False, True)))
    cases = itertools.product(combos, repeat=n_entries) if n_entries == 1 else random.Random(7).sample(
        list(itertools.product(combos, repeat=2)), 3000)
    for spec in cases:
        entries, files, located, edges = [], dict(FILES), {}, set()
        for i, (result, tout, pout, nip) in enumerate(spec):
            t, paths, f, loc, ed = _world(tout, pout, f"S{i}")
            files.update(f)
            located[LIB] = loc        # one package: the last outcome wins, which only mixes more states
            edges |= ed
            entries.append(entry(result, paths=paths if result == R else [], target=t, not_in_program=nip))
        before = verdict(entries)
        after = vf.verify(before, ctx(files, edges, located))
        ag.assert_downgrade_only(before, after)            # raises on any upgrade, added symbol or changed path
        assert len(after["per_symbol"]) == len(before["per_symbol"])
        for b, a in zip(before["per_symbol"], after["per_symbol"]):
            assert a["result"] in (b["result"], CD)
            assert a["paths"] == b["paths"]


def test_random_inputs_never_stronger():
    rng = random.Random(20261026)
    for _ in range(400):
        n = rng.randint(0, 4)
        entries = []
        for i in range(n):
            result = rng.choice((R, NR, CD))
            t = {"package": LIB, "symbol": f"S{i}"}
            p = path(MAIN_PKG, t, [(f"{LIB}.S{i}", rng.choice(["cmd/a/main.go", "nope.go", ""]), rng.choice([0, 1, 4, 99]))])
            if rng.random() < 0.3:
                p["edges"][0]["callee"] = f"{LIB}.Elsewhere"
            entries.append(entry(result, paths=[p] if result == R and rng.random() < 0.9 else [], target=t,
                                 not_in_program=rng.random() < 0.5))
        before = verdict(entries, case=ag.case_result(entries, incomplete=rng.random() < 0.2))
        located = {LIB: vf.PackageLocation(rng.choice([vf.FOUND, vf.MISSING, vf.NOT_IN_BUILD, vf.UNKNOWN]),
                                           files=["/modcache/example.com/lib@v1.0.0/lib.go"])}
        edges = {(f"{MAIN_PKG}.main", f"{LIB}.S{i}", "cmd/a/main.go", 4) for i in range(n) if rng.random() < 0.7}
        after = vf.verify(before, ctx(FILES, edges, located, incomplete=rng.random() < 0.2))
        ag.assert_downgrade_only(before, after)
        assert after["verification"]["status"] in ("PASSED", "FAILED", "NOT_RUN")


def test_symbol_only_in_constraint_excluded_files():
    """Declared only in a file the build configuration excludes: supports NOT_REACHABLE, never REACHABLE."""
    files = dict(FILES, **{"/m/lib_darwin.go": "package lib\n\nfunc Parse(s string) string {\n}\n", "/m/lib.go": "package lib\n"})
    loc = {LIB: vf.PackageLocation(vf.FOUND, files=["/m/lib.go"], ignored=["/m/lib_darwin.go"])}
    nr = vf.verify(verdict([entry(NR, not_in_program=True)]), ctx(files, GOOD_EDGES, loc))
    assert nr["per_symbol"][0]["result"] == NR and nr["verification"]["checks_by_kind"]["TARGET_EXISTS"]["skipped"] == 1
    r = vf.verify(verdict([entry(R)]), ctx(files, GOOD_EDGES, loc))
    assert r["per_symbol"][0]["result"] == CD
    gone = {LIB: vf.PackageLocation(vf.FOUND, files=["/m/lib.go"], ignored=["/m/lib.go"])}
    assert vf.verify(verdict([entry(NR, not_in_program=True)]), ctx(files, GOOD_EDGES, gone))["per_symbol"][0]["result"] == CD


def test_go_list_locator_classifies(tmp_path):
    import json as _json

    def runner(cmd, **kw):
        class P:
            returncode = 0
            stderr = ""
        p = P()
        if cmd[2] == "-m":
            p.stdout = "example.com/app\nexample.com/lib\n"
        elif cmd[-1] == "example.com/lib/darwinonly":
            p.stdout = _json.dumps({"ImportPath": cmd[-1], "Dir": "/x/darwinonly", "IgnoredGoFiles": ["a_darwin.go"],
                                    "Error": {"Err": "build constraints exclude all Go files in /x/darwinonly"}})
        elif cmd[-1] == "example.com/lib/typo":
            p.stdout = _json.dumps({"ImportPath": cmd[-1], "Error": {"Err": "no Go files"}})
        else:
            p.stdout = _json.dumps({"ImportPath": cmd[-1], "Error": {"Err": "no required module provides package"}})
        return p

    loc = vf.go_list_locator(tmp_path, runner=runner)
    d = loc("example.com/lib/darwinonly")
    assert d.status == vf.FOUND and d.files == [] and d.ignored == ["/x/darwinonly/a_darwin.go"]
    assert loc("example.com/lib/typo").status == vf.MISSING
    assert loc("other.org/pkg").status == vf.NOT_IN_BUILD
