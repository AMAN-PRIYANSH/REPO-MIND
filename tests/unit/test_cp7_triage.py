"""CP7 pipeline with fake methods: mode choice, symbols, failure as a result, Mode 2 labels and
policy, verifier wiring, schema validity. No Go, git, network or model."""

import ast
from pathlib import Path

import pytest

from tests.unit.cp7_support import (APP, LIB, LOCATED, FakeMethod, advisory, ctx, fake_inspect, fix_evidence, path,
                                    release_range, runners)
from vulntrace.models.fakes import FakeEmbedder
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import aggregate, retrieve, triage
from vulntrace.schemas import validation_errors
from vulntrace.verdict import CANT_DETERMINE as CD, NOT_REACHABLE as NR, REACHABLE as R

MAIN = "example.com/app/cmd/a"


def req(**kw):
    kw.setdefault("case_id", "GO-TEST-1")
    kw.setdefault("app", APP)
    kw.setdefault("created_at", "2026-10-26T00:00:00Z")
    return triage.TriageRequest(**kw)


def run(r, vta=None, linker=None, **rkw):
    v = triage.run_triage(r, runners(vta or FakeMethod("vta"), linker or FakeMethod("linker", default=("ABSENT", {})), **rkw))
    errs = validation_errors("verdict", v)
    assert not errs, errs
    return v


def reachable_world(symbol="Parse", pkg=f"{LIB}/a"):
    t = {"package": pkg, "symbol": symbol}
    p = path(MAIN, t, [(f"{pkg}.{symbol}", "cmd/a/main.go", 4)])
    files = {"cmd/a/main.go": "package main\n\nfunc main() {\n\tx()\n}\n", "/m/a.go": f"package a\n\nfunc {symbol}() {{\n}}\n"}
    edges = {(f"{MAIN}.main", f"{pkg}.{symbol}", "cmd/a/main.go", 4)}
    from vulntrace.verifier import verify as vf

    located = {pkg: vf.PackageLocation(vf.FOUND, files=["/m/a.go"])}
    return (FakeMethod("vta", {(MAIN, pkg, symbol): ("PATH_FOUND", {"paths": [p]})}),
            FakeMethod("linker", {(MAIN, pkg, symbol): ("PRESENT", {})}, default=("ABSENT", {})),
            lambda info, incomplete: ctx(files, edges, located, incomplete=incomplete))


# --- mode choice ------------------------------------------------------------------------------------
def test_auto_with_fix_commit_and_evidence_is_mode1():
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")])))
    assert v["mode"] == "FIX" and v["mode_selection"]["reason"] == "FIX_COMMIT_KNOWN"
    assert v["evidence_level"] == "CHANGED_FUNCTION_LEVEL"


def test_auto_without_fix_commit_is_mode2():
    rr, code = release_range([("a", "Parse", "BOTH")])
    v = run(req(advisory=advisory(fix=False), release_range=rr, candidate_code=code))
    assert v["mode"] == "RELEASE" and v["mode_selection"]["reason"] == "NO_FIX_COMMIT"


def test_auto_falls_back_to_mode2_when_fix_evidence_is_unusable():
    rr, code = release_range([("a", "Parse", "BOTH")])
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([], status="EMPTY"), release_range=rr, candidate_code=code))
    assert v["mode"] == "RELEASE" and v["mode_selection"]["reason"] == "FIX_EVIDENCE_UNUSABLE_FALLBACK_TO_RELEASE"


def test_targets_mode():
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "Parse"}], target_origin="FIXTURE", advisory=advisory()))
    assert v["mode"] == "TARGETS" and v["symbols"][0]["origin"] == "FIXTURE"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        triage.choose_mode(req(mode="guess"))


# --- Mode 1 analyses every changed non-test function ---------------------------------------------
def test_mode1_sends_every_changed_function_to_both_methods():
    vta, linker = FakeMethod("vta"), FakeMethod("linker", default=("ABSENT", {}))
    fe = fix_evidence([("a", "F", "BOTH"), ("a", "T.M", "OLD"), ("b", "G", "BOTH"), ("a", "New", "NEW")])
    v = run(req(advisory=advisory(), fix_evidence=fe), vta, linker)
    want = [{"package": f"{LIB}/a", "symbol": "F"}, {"package": f"{LIB}/a", "symbol": "T.M"}, {"package": f"{LIB}/b", "symbol": "G"}]
    assert vta.calls == [(MAIN, want)] and linker.calls == [(MAIN, want)]
    assert v["coverage"]["not_covered"][0]["reason"] == "ADDED_BY_FIX"
    assert v["verdict"] == NR and len(v["per_symbol"]) == 3


def test_no_llm_or_agent_on_the_verdict_path():
    """Static: nothing under pipeline/ or verifier/ imports the LLM, agent or LLM-model modules."""
    banned = ("vulntrace.llm", "vulntrace.agent", "vulntrace.models.llm", "langgraph", "openai", "anthropic")
    for d in ("pipeline", "verifier"):
        for f in (REPO_ROOT / "src" / "vulntrace" / d).glob("*.py"):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for n in names:
                    assert not n.startswith(banned), f"{f.name} imports {n}"


# --- the rule table through the pipeline ------------------------------------------------------------
@pytest.mark.parametrize("vta,linker,result,code", [
    ("PATH_FOUND", "ABSENT", CD, "METHOD_DISAGREEMENT"),
    ("NO_PATH", "PRESENT", CD, "METHOD_DISAGREEMENT"),
    ("NO_PATH", "ABSENT", NR, None),
    ("ERROR", "ABSENT", CD, "ANALYSIS_FAILED"),
    ("NO_PATH", "ERROR", CD, "ANALYSIS_FAILED"),
])
def test_two_method_agreement(vta, linker, result, code):
    kw_v = {"code": "TYPE_ERRORS"} if vta == "ERROR" else {}
    kw_l = {"code": "UNSUPPORTED_SYMBOL_FORM"} if linker == "ERROR" else {}
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "F"}]),
            FakeMethod("vta", default=(vta, kw_v)), FakeMethod("linker", default=(linker, kw_l)))
    e = v["per_symbol"][0]
    assert (e["result"], e["reason_code"]) == (result, code)


def test_reachable_has_a_verified_path():
    vta, linker, vctx = reachable_world()
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")])), vta, linker, verifier_ctx=vctx)
    assert v["verdict"] == R and v["verification"]["status"] == "PASSED"
    assert all(e["verified_path"] for e in v["per_symbol"] if e["result"] == R)


def test_unverifiable_reachable_is_downgraded():
    vta, linker, _ = reachable_world()
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")])), vta, linker,
            verifier_ctx=lambda info, inc: ctx({}, set(), LOCATED))
    assert v["verdict"] == CD and v["reason_codes"] == ["VERIFIER_REJECTED"]
    assert v["per_symbol"][0]["pre_verifier_result"] == R


# --- failure is a result ----------------------------------------------------------------------------
@pytest.mark.parametrize("kw,code", [
    ({"mode": "fix", "advisory": advisory()}, "NO_FIX_EVIDENCE"),
    ({"mode": "fix", "advisory": advisory(), "fix_evidence": fix_evidence([], status="UNAVAILABLE")}, "NO_FIX_EVIDENCE"),
    ({"mode": "release", "advisory": advisory()}, "NO_RELEASE_EVIDENCE"),
    ({"mode": "release", "advisory": advisory(), "release_range": release_range([("a", "F", "BOTH")], "TAG_NOT_FOUND")[0],
      "candidate_code": {"candidates": {}}}, "NO_RELEASE_EVIDENCE"),
    ({"mode": "release", "advisory": advisory(), "release_range": release_range([])[0],
      "candidate_code": {"candidates": {}}}, "NO_TARGET_SYMBOLS"),
    ({"mode": "fix", "advisory": advisory(), "fix_evidence": fix_evidence([("a", "New", "NEW")])}, "NO_TARGET_SYMBOLS"),
])
def test_missing_evidence_is_cant_determine(kw, code):
    vta = FakeMethod("vta")
    v = run(req(**kw), vta)
    assert (v["verdict"], v["reason_codes"]) == (CD, [code]) and vta.calls == []


def test_unloadable_app_is_cant_determine():
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "F"}]),
            inspect=fake_inspect(mains=(), list_error="go list: go.mod requires go >= 1.26"))
    assert (v["verdict"], v["reason_codes"]) == (CD, ["APP_LOAD_FAILED"])
    assert v["coverage"]["app_list_error"].startswith("go list")


def test_no_main_package_is_unsupported_target():
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "F"}]), inspect=fake_inspect(mains=()))
    assert (v["verdict"], v["reason_codes"]) == (CD, ["UNSUPPORTED_TARGET"])


def test_every_main_failing_to_load_adds_app_load_failed():
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "F"}]),
            FakeMethod("vta", default=("ERROR", {"code": "LOAD_FAILED"})),
            FakeMethod("linker", default=("ERROR", {"code": "BUILD_FAILED"})))
    assert v["verdict"] == CD and v["reason_codes"] == ["ANALYSIS_FAILED", "APP_LOAD_FAILED"]


def test_mains_over_the_limit_block_not_reachable():
    v = run(req(mode="targets", targets=[{"package": LIB, "symbol": "F"}]),
            inspect=fake_inspect(mains=(MAIN,), skipped=("example.com/app/cmd/b",)))
    assert (v["verdict"], v["reason_codes"]) == (CD, ["INCOMPLETE_COVERAGE"])
    assert any("over the limit" in x for x in v["limitations"])


def test_per_main_entries_and_any_main_reachable():
    other = "example.com/app/cmd/b"
    t = {"package": LIB, "symbol": "F"}
    p = path(other, t, [(f"{LIB}.F", "cmd/b/main.go", 4)])
    vta = FakeMethod("vta", {(other, LIB, "F"): ("PATH_FOUND", {"paths": [p]})})
    linker = FakeMethod("linker", {(other, LIB, "F"): ("PRESENT", {})}, default=("ABSENT", {}))
    v = run(req(mode="targets", targets=[t], run_verifier=False), vta, linker, inspect=fake_inspect(mains=(MAIN, other)))
    assert [e["main_package"] for e in v["per_symbol"]] == [MAIN, other]
    assert v["verdict"] == R


# --- Mode 2 -----------------------------------------------------------------------------------------
def _mode2_req(**kw):
    rr, code = release_range([("a", "Parse", "BOTH"), ("a", "Safe", "BOTH"), ("b", "Other", "BOTH")])
    return req(mode="release", advisory=advisory(), release_range=rr, candidate_code=code, **kw)


def test_mode2_reachable_is_candidate_level_with_rank_and_score():
    vta, linker, vctx = reachable_world("Parse")
    v = run(_mode2_req(retriever="bm25"), vta, linker, verifier_ctx=vctx)
    assert v["verdict"] == R and v["evidence_level"] == "CANDIDATE_LEVEL"
    e = next(x for x in v["per_symbol"] if x["result"] == R)
    assert e["rank"] >= 1 and isinstance(e["score"], float) and e["evidence_level"] == "CANDIDATE_LEVEL"
    assert v["retrieval"]["config_used"] == "bm25" and v["retrieval"]["top"]
    assert v["policy"]["applied"] is False


def test_mode2_not_reachable_is_downgraded_by_default():
    v = run(_mode2_req(retriever="bm25"))
    assert v["pre_policy_verdict"] == NR
    assert (v["verdict"], v["reason_codes"]) == (CD, ["MODE2_NOT_REACHABLE_DOWNGRADED"]) and v["policy"]["applied"]


def test_mode2_keep_policy():
    v = run(_mode2_req(retriever="bm25", mode2_policy=aggregate.MODE2_POLICY_KEEP))
    assert v["verdict"] == NR


def test_mode2_top_k_limits_the_analysed_candidates():
    vta = FakeMethod("vta")
    v = run(_mode2_req(retriever="bm25", k=1), vta)
    assert len(vta.calls[0][1]) == 1
    assert sorted(n["reason"] for n in v["coverage"]["not_covered"]) == ["BEYOND_TOP_K", "BEYOND_TOP_K"]


def test_fixed_retriever_falls_back_to_bm25_when_the_embedder_cannot_load(monkeypatch):
    def boom(*a, **k):
        raise OSError("model not cached")

    monkeypatch.setattr(retrieve, "make_embedder_offline", boom)
    rr, code = release_range([("a", "Parse", "BOTH"), ("a", "Safe", "BOTH")])
    rk = retrieve.rank_candidates(advisory(), rr, code, "example", "lib", config="fixed")
    assert rk.config_requested == "hybrid:bge-small" and rk.config_used == "bm25"
    assert rk.fallback == "EMBEDDER_UNAVAILABLE" and "model not cached" in rk.fallback_reason
    assert sorted(c for c, _ in rk.ranked) == ["r1", "r2"] and rk.k == 10


def test_hybrid_with_a_fake_embedder():
    rr, code = release_range([("a", "Parse", "BOTH"), ("a", "Safe", "BOTH")])
    rk = retrieve.rank_candidates(advisory(), rr, code, "example", "lib", config="hybrid:fake", embedder=FakeEmbedder())
    assert rk.config_used == "hybrid:fake" and rk.fallback is None and len(rk.ranked) == 2
    assert rk.ranked == retrieve.rank_candidates(advisory(), rr, code, "example", "lib", config="hybrid:fake",
                                                 embedder=FakeEmbedder()).ranked


def test_retrieval_query_never_sees_curated_symbols():
    """The query comes from summary and details only (CP4 leakage control)."""
    adv = advisory()
    adv["modules"] = [{"packages": [{"core_symbols": ["SECRET_GOLD"]}]}]
    rr, code = release_range([("a", "Parse", "BOTH")])
    assert retrieve.rank_candidates(adv, rr, code, "example", "lib", config="bm25").query_chars == len(adv["summary"])


# --- lifting ----------------------------------------------------------------------------------------
def test_lifted_symbols_are_reported_but_never_decide():
    lifted_pkg = f"{LIB}/api"

    def lift(module_dir, seeds, rule):
        return [{"target": s, "rules": {rule: {"entries": [{"package": lifted_pkg, "symbol": "Handle"}]}}, "error": None}
                for s in seeds]

    t = {"package": lifted_pkg, "symbol": "Handle"}
    p = path(MAIN, t, [(f"{lifted_pkg}.Handle", "cmd/a/main.go", 4)])
    vta = FakeMethod("vta", {(MAIN, lifted_pkg, "Handle"): ("PATH_FOUND", {"paths": [p]})})
    linker = FakeMethod("linker", {(MAIN, lifted_pkg, "Handle"): ("PRESENT", {})}, default=("ABSENT", {}))
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")]), lift_rule="NEAREST",
                run_verifier=False), vta, linker, lift=lift, inspect=fake_inspect(module=LIB))
    lifted = [s for s in v["symbols"] if s["origin"] == "LIFTED"]
    assert lifted and lifted[0]["decides_verdict"] is False and lifted[0]["lifted_from"] == ["Parse"]
    assert v["verdict"] == NR   # the lifted REACHABLE does not decide; the changed function is NOT_REACHABLE


def test_lifting_not_run_for_a_different_app():
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")]), lift_rule="ALL"),
            lift=lambda *a: pytest.fail("must not lift"))
    assert v["coverage"]["lifting"]["run"] is False


def test_output_records_coverage_toolchain_and_limitations():
    v = run(req(advisory=advisory(), fix_evidence=fix_evidence([("a", "Parse", "BOTH")])))
    assert v["toolchain"]["env"] == {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOPROXY": "off"}
    assert v["toolchain"]["helper"]["go_version"] == "go1.24.7"
    assert v["coverage"]["main_packages"] == [MAIN] and v["limitations"][0].startswith("Reachability only")
    assert v["statement"] == "Reachability only. This verdict does not assess exploitability."
    assert v["target_app"]["commit_source"] in ("GIT_HEAD", "EVIDENCE")
    assert Path(v["target_app"]["path"]) == APP
