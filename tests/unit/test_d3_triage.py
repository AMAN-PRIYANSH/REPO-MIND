"""CP7b deliverables 2-3: the D3 triage runner and the govulncheck reference, without Go, git or network."""

import json
from pathlib import Path

import pytest

from tests.unit import cp7_support as s
from vulntrace.d3 import govuln
from vulntrace.d3 import triage_run as tr
from vulntrace.schemas import validation_errors


# --- govulncheck output mapping --------------------------------------------------------------------
def _finding(osv, frames):
    return {"finding": {"osv": osv, "fixed_version": "v1.0.1", "trace": frames}}


SYM = [{"module": "example.com/lib", "version": "v1.0.0", "package": "example.com/lib", "function": "Parse",
        "position": {"filename": "lib.go", "line": 3}},
       {"module": "example.com/app", "package": "example.com/app/cmd/a", "function": "main",
        "position": {"filename": "cmd/a/main.go", "line": 4}}]
PKG = [{"module": "example.com/lib", "version": "v1.0.0", "package": "example.com/lib"}]
MOD = [{"module": "example.com/lib", "version": "v1.0.0"}]


def _run(*msgs, ok=True):
    stream = "\n".join(json.dumps(m, indent=1) for m in ({"config": {"go_version": "go1.26.10", "scanner_name": "govulncheck",
                                                                    "scanner_version": "v1.9.0"}}, *msgs))
    return {"ok": ok, "error": None if ok else "boom", "messages": govuln.parse_stream(stream)}


def test_parse_stream_reads_concatenated_objects():
    msgs = govuln.parse_stream('{"a": 1}\n{\n "b": {"c": [1, 2]}\n}\n  ')
    assert msgs == [{"a": 1}, {"b": {"c": [1, 2]}}]


@pytest.mark.parametrize("msgs,verdict,level", [
    ([_finding("GO-1", MOD), _finding("GO-1", PKG), _finding("GO-1", SYM)], govuln.REACHABLE, govuln.LEVEL_SYMBOL),
    ([_finding("GO-1", MOD), _finding("GO-1", PKG)], govuln.NOT_REACHABLE, govuln.LEVEL_PACKAGE),
    ([_finding("GO-1", MOD)], govuln.NOT_REACHABLE, govuln.LEVEL_MODULE),
    ([_finding("GO-2", SYM)], govuln.NOT_AFFECTED, govuln.LEVEL_NONE),          # another advisory's finding
])
def test_advisory_result_levels(msgs, verdict, level):
    r = govuln.advisory_result(_run(*msgs), "GO-1")
    assert (r["verdict"], r["level"]) == (verdict, level)
    if verdict == govuln.REACHABLE:
        assert r["trace"][0] == "example.com/lib.Parse (lib.go:3)" and r["symbols"] == ["example.com/lib.Parse"]


def test_advisory_result_error_and_receiver_frames():
    assert govuln.advisory_result({"ok": False, "error": "x", "messages": []}, "GO-1")["verdict"] == govuln.ERROR
    fr = {"package": "p", "receiver": "*T", "function": "M"}
    assert govuln.frame_text(fr) == "p.T.M"


@pytest.mark.parametrize("ours,theirs,expected", [
    ("REACHABLE", "REACHABLE", "AGREE"), ("NOT_REACHABLE", "NOT_REACHABLE", "AGREE"),
    ("REACHABLE", "NOT_REACHABLE", "DISAGREE"), ("NOT_REACHABLE", "REACHABLE", "DISAGREE"),
    ("CANT_DETERMINE", "REACHABLE", "NOT_COMPARABLE"), ("REACHABLE", "ERROR", "NOT_COMPARABLE"),
    ("NOT_REACHABLE", "NOT_AFFECTED", "NOT_COMPARABLE"), (None, "REACHABLE", "NOT_COMPARABLE")])
def test_agreement_never_counts_an_abstention_or_absence(ours, theirs, expected):
    assert govuln.agreement(ours, theirs) == expected


def test_run_env_is_offline_and_cgo_free():
    env = govuln.run_env(Path("/m"))
    assert (env["GOPROXY"], env["CGO_ENABLED"], env["GOTOOLCHAIN"], env["GOFLAGS"]) == ("off", "0", "local", "-mod=readonly")


# --- the runner ------------------------------------------------------------------------------------
VCASE = {**s.advisory(), "modules": [{"module": "other.example/x", "vulnerable_at": "0.1.0", "fixed_in": "0.2.0", "packages": []},
                                     {"module": s.LIB, "vulnerable_at": "1.0.0", "fixed_in": "1.0.1", "packages": []}],
         "source": {"vulndb_commit": "v" * 40}}
CASE = {"id": "app__GO-TEST-1", "advisory": "GO-TEST-1", "app_repo": "github.com/example/app", "app_tag": "v1.0.0",
        "app_commit": "c" * 40, "module": s.LIB, "version_selected": "v1.0.0", "created": "2026-01-01",
        "mains": [s.MAIN_PKG]}


def test_advisory_for_uses_the_required_module_entry():
    adv = tr.advisory_for(VCASE, s.LIB)
    assert (adv["module"], adv["vulnerable_at"], adv["fixed_in"]) == (s.LIB, "1.0.0", "1.0.1")


def test_ensure_evidence_builds_once_and_range_only_when_fix_unusable(tmp_path):
    calls = {"fix": 0, "range": 0}

    def fix(vc):
        calls["fix"] += 1
        return {**s.fix_evidence([("", "Parse", "BOTH")]), "case_id": vc["id"]}

    def rng(vc, m):
        calls["range"] += 1
        return {"case_id": vc["id"], "status": "EMPTY", "candidates": []}

    ev = tr.ensure_evidence(CASE, VCASE, tmp_path, None, fix, rng)
    tr.ensure_evidence(CASE, VCASE, tmp_path, None, fix, rng)
    assert calls == {"fix": 1, "range": 0} and ev["release_range"] is None
    assert (tmp_path / "fix_evidence" / "GO-TEST-1.json").is_file()

    def empty_fix(vc):
        return {**s.fix_evidence([], status="EMPTY"), "case_id": vc["id"]}

    other = tmp_path / "other"
    ev = tr.ensure_evidence(CASE, VCASE, other, None, empty_fix, rng)
    assert calls["range"] == 1 and ev["release_range"]["status"] == "EMPTY"


def _runners(vta_result="PATH_FOUND", linker="PRESENT"):
    path = s.GOOD_PATH
    vta = s.FakeMethod("vta", {(s.MAIN_PKG, s.LIB, "Parse"): (vta_result, {"paths": [path]} if vta_result == "PATH_FOUND" else {})})
    lk = s.FakeMethod("linker", {(s.MAIN_PKG, s.LIB, "Parse"): (linker, {})})
    return s.runners(vta, lk, inspect=s.fake_inspect(mains=(s.MAIN_PKG,)), verifier_ctx=lambda info, inc: s.good_ctx())


def _fix(vc):
    return {**s.fix_evidence([("", "Parse", "BOTH")]), "case_id": vc["id"]}


def test_run_case_reachable_with_govulncheck_agreement(tmp_path):
    gv = _run(_finding("GO-TEST-1", SYM))
    row, v = tr.run_case(CASE, VCASE, evidence_dir=tmp_path, app_dir=tmp_path, app_error=None, runners=_runners(),
                         binary=None, gv=gv, vulndb_commit="v" * 40, repo_commit="abc", build_fix=_fix)
    assert v["verdict"] == "REACHABLE" and row["verdict"] == "REACHABLE"
    assert validation_errors("verdict", v) == [] and row["schema_errors"] == []
    assert row["mode"] == "FIX" and row["fix_evidence_status"] == "AVAILABLE"
    assert row["reachable_symbols"] == [f"{s.LIB}.Parse"]
    assert row["govulncheck"]["verdict"] == "REACHABLE" and row["govulncheck"]["agreement"] == "AGREE"
    assert v["target_app"]["commit"] == CASE["app_commit"]                    # the pinned app commit is recorded
    assert row["cluster_key"] == CASE["app_repo"]


def test_run_case_not_reachable_disagreement_is_recorded_not_resolved(tmp_path):
    gv = _run(_finding("GO-TEST-1", SYM))
    row, v = tr.run_case(CASE, VCASE, evidence_dir=tmp_path, app_dir=tmp_path, app_error=None,
                         runners=_runners("NO_PATH", "ABSENT"), binary=None, gv=gv, vulndb_commit="v" * 40,
                         repo_commit=None, build_fix=_fix)
    assert v["verdict"] == "NOT_REACHABLE"
    assert row["govulncheck"]["agreement"] == "DISAGREE"
    summ = tr.summarise([row])
    assert summ["govulncheck"]["disagreements"] == [{"id": CASE["id"], "ours": "NOT_REACHABLE", "govulncheck": "REACHABLE",
                                                    "level": "SYMBOL"}]


def test_run_case_without_app_tree_is_counted_not_dropped(tmp_path):
    row, v = tr.run_case(CASE, VCASE, evidence_dir=tmp_path, app_dir=None, app_error="go mod download: boom",
                         runners=_runners(), binary=None, gv=None, vulndb_commit="v" * 40, repo_commit=None, build_fix=_fix)
    assert v is None and row["verdict"] is None and row["app_prep_error"] == "go mod download: boom"
    summ = tr.summarise([row])
    assert summ["not_triaged"] == [{"id": CASE["id"], "reason": "go mod download: boom"}] and summ["triaged"] == 0
    row2, _ = tr.run_case(CASE, None, evidence_dir=tmp_path, app_dir=tmp_path, app_error=None, runners=_runners(),
                          binary=None, gv=None, vulndb_commit="v", repo_commit=None)
    assert row2["harness_error"] and row2["verdict"] is None


def test_summarise_counts_and_cant_determine_reasons():
    rows = [{"id": "a", "app_repo": "r1", "verdict": "REACHABLE", "reason_codes": [], "case_seconds": 3.0, "seconds": 2.0},
            {"id": "b", "app_repo": "r1", "verdict": "CANT_DETERMINE", "reason_codes": ["METHOD_DISAGREEMENT"], "case_seconds": 5.0},
            {"id": "c", "app_repo": "r2", "verdict": "CANT_DETERMINE", "reason_codes": ["VERIFIER_REJECTED", "ANALYSIS_FAILED"]},
            {"id": "d", "app_repo": "r2", "verdict": None, "app_prep_error": "x"}]
    sm = tr.summarise(rows)
    assert sm["verdicts"] == {"REACHABLE": 1, "NOT_REACHABLE": 0, "CANT_DETERMINE": 2}
    assert sm["cant_determine_reasons"] == {"METHOD_DISAGREEMENT": 1, "ANALYSIS_FAILED+VERIFIER_REJECTED": 1}
    assert sm["per_app"] == {"r1": {"REACHABLE": 1, "CANT_DETERMINE": 1}, "r2": {"CANT_DETERMINE": 1}}
    assert sm["seconds_per_case"]["n"] == 2


def test_sanitise_rewrites_module_cache_and_goroot_paths(tmp_path):
    mc = tmp_path / "gomod"
    v = {"a": f"{mc}/github.com/x/y@v1.0.0/f.go", "b": "/usr/local/go/src/net/http/server.go", "c": "cmd/a/main.go"}
    out = tr.sanitise(v, mc, "/usr/local/go")
    assert out == {"a": "$GOMODCACHE/github.com/x/y@v1.0.0/f.go", "b": "$GOROOT/src/net/http/server.go", "c": "cmd/a/main.go"}
