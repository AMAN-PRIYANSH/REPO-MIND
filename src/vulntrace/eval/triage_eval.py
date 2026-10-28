"""`python -m vulntrace eval triage` (CP7 deliverable 4, E5-lite; no D3 yet).

- `--set fixtures` (D2, truth by construction): every fixture case in three modes - TARGETS (the
  case's own target symbol), FIX (Mode 1 on a synthetic fix commit) and RELEASE (Mode 2 on a
  synthetic release range; see `triage_fixtures`). Verdict accuracy, REACHABLE precision, false
  NOT_REACHABLE count, verifier rejections; a determinism re-run; and a corruption probe (every
  verified path of a REACHABLE verdict is corrupted three ways and must be rejected).
- `--set d1` / `--set d4`: every case with evidence; the module under study, at its vulnerable
  commit, is the app (its own main packages are the entry points). These are NOT truth-labelled
  reachability cases: the results are verdict distributions, coverage and CANT_DETERMINE reasons,
  never accuracy. For context, the same app is also analysed with the advisory's curated core
  symbols as targets (the "curated reference"); agreement with it is consistency with our own
  analysis of the curators' symbols, not correctness.

The Mode 2 NOT_REACHABLE policy is decided by `decide_mode2_policy`, whose rule is fixed in code
before any result is seen. Per-case full verdicts go to `data/triage/` (not committed); compact
rows and summaries go to `docs/results/cp7/` (each file under 512 KiB).
"""

import copy
import gzip
import json
import math
import os
import re
import shutil
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import datasets, metrics
from vulntrace.eval import lift_eval, lift_prep
from vulntrace.eval import triage_fixtures as tfx
from vulntrace.eval.run_info import run_info
from vulntrace.paths import FIXTURES_DIR, REPO_ROOT
from vulntrace.pipeline import aggregate, triage
from vulntrace.pipeline import symbols as sy
from vulntrace.schemas import validation_errors
from vulntrace.verdict import CANT_DETERMINE, NOT_REACHABLE, REACHABLE
from vulntrace.verifier import checks as ck

SCHEMA_VERSION = "1.0"
SEED = 20261026
VERDICTS = (REACHABLE, NOT_REACHABLE, CANT_DETERMINE)
EVAL_MAX_MAINS = 5
WORK_SUBDIR = "triage_work"

# --- the Mode 2 policy rule (fixed before any CP7 result was seen) ---------------------------------
POLICY_MIN_NR = 20
POLICY_MAX_UNSUPPORTED_UPPER = 0.05
POLICY_RULE_TEXT = (
    "KEEP a Mode 2 NOT_REACHABLE only if all hold: (1) on the fixtures, Mode 2 before the policy has 0 false "
    "NOT_REACHABLE; (2) on D4 there are at least 20 raw Mode 2 NOT_REACHABLE verdicts; (3) none of them is "
    "contradicted by the curated reference (curated core symbols REACHABLE in the same app); (4) the 95% Wilson "
    "upper bound of the share of raw Mode 2 NOT_REACHABLE verdicts whose analysed candidates contain no curated "
    "core symbol is at most 0.05. Otherwise DOWNGRADE to CANT_DETERMINE (MODE2_NOT_REACHABLE_DOWNGRADED).")


def wilson(k: int, n: int, z: float = 1.959964) -> dict[str, float]:
    if n == 0:
        return {"rate": 0.0, "ci_low": 0.0, "ci_high": 0.0, "k": 0, "n": 0}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"rate": p, "ci_low": max(0.0, c - h), "ci_high": min(1.0, c + h), "k": k, "n": n}


def decide_mode2_policy(fixture_rows: list[dict[str, Any]], d4_rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    fx = [r for r in fixture_rows if r["mode"] == triage.MODE_RELEASE]
    fx_false_nr = sum(1 for r in fx if r["pre_policy_verdict"] == NOT_REACHABLE and r["truth"] == REACHABLE)
    inputs: dict[str, Any] = {"fixtures_mode2_raw_false_not_reachable": fx_false_nr, "fixtures_mode2_cases": len(fx)}
    checks = {"fixtures_zero_false_nr": fx_false_nr == 0}
    if d4_rows is None:
        checks["d4_available"] = False
        decision = aggregate.MODE2_POLICY_DOWNGRADE
    else:
        nr = [r for r in d4_rows if r.get("pre_policy_verdict") == NOT_REACHABLE]
        unsupported = [r for r in nr if not r.get("gold_analysed")]
        contradicted = [r for r in nr if (r.get("reference") or {}).get("verdict") == REACHABLE]
        w = wilson(len(unsupported), len(nr))
        clusters = [r["cluster_key"] for r in nr]
        inputs.update(d4_raw_not_reachable=len(nr), d4_unsupported=len(unsupported), d4_contradicted=len(contradicted),
                      d4_unsupported_share=w,
                      d4_unsupported_share_cluster_bootstrap=metrics.cluster_bootstrap_ci(
                          [0.0 if r.get("gold_analysed") else 1.0 for r in nr], clusters, SEED) if nr else None,
                      d4_contradicted_ids=[r["id"] for r in contradicted], d4_unsupported_ids=[r["id"] for r in unsupported])
        checks.update(d4_min_count=len(nr) >= POLICY_MIN_NR, d4_none_contradicted=not contradicted,
                      d4_unsupported_upper_ok=bool(nr) and w["ci_high"] <= POLICY_MAX_UNSUPPORTED_UPPER)
        decision = aggregate.MODE2_POLICY_KEEP if all(checks.values()) else aggregate.MODE2_POLICY_DOWNGRADE
    return {"rule": POLICY_RULE_TEXT, "inputs": inputs, "checks": checks, "decision": decision}


# --- runners ---------------------------------------------------------------------------------------
class MemoMethod:
    """Memoises a method per (module dir, main package, target). On the first call for a main
    package it also asks for `extras`, so a second run over the same app (for example the curated
    reference) costs nothing. A method's result for one target does not depend on the other
    targets in the request (one call graph, one binary per main package)."""

    def __init__(self, fn, extras: list[dict[str, str]] | None = None):
        self.fn, self.extras = fn, list(extras or [])
        self.cache: dict[tuple, dict[str, Any]] = {}
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, module_dir: Path, main: str, targets: list[dict[str, str]]) -> list[dict[str, Any]]:
        key = lambda t: (str(module_dir), main, t["package"], t["symbol"])  # noqa: E731
        with self.lock:
            need = [t for t in targets if key(t) not in self.cache]
            if need:
                seen, req = set(), []
                for t in need + [e for e in self.extras if key(e) not in self.cache]:
                    if key(t) not in seen:
                        seen.add(key(t))
                        req.append({"package": t["package"], "symbol": t["symbol"]})
                self.calls += 1
                for t, r in zip(req, self.fn(module_dir, main, req)):
                    self.cache[key(t)] = r
            return [dict(self.cache[key(t)], target={"package": t["package"], "symbol": t["symbol"]}) for t in targets]


def memo_runners(base: triage.Runners, extras: list[dict[str, str]] | None = None) -> triage.Runners:
    return triage.Runners(vta=MemoMethod(base.vta, extras), linker=MemoMethod(base.linker, extras),
                          verifier_ctx=base.verifier_ctx, inspect=base.inspect, lift=base.lift, rank=base.rank)


# --- compact rows ----------------------------------------------------------------------------------
def _key(t: dict[str, str]) -> tuple[str, str]:
    return t["package"], ck.normalise_symbol(t["symbol"])


def verdict_row(v: dict[str, Any]) -> dict[str, Any]:
    """The facts of one verdict the results need (no code, no advisory text)."""
    entries = v["per_symbol"]
    cov = v.get("coverage") or {}
    ver = v["verification"]
    by_kind = ver.get("checks_by_kind") or {}
    ret = v.get("retrieval") or {}
    pm = cov.get("per_main") or {}
    return {
        "mode": v.get("mode"), "mode_reason": (v.get("mode_selection") or {}).get("reason"),
        "verdict": v["verdict"], "reason_codes": v["reason_codes"],
        "pre_verifier_verdict": pre_verifier_verdict(v),
        "pre_policy_verdict": v.get("pre_policy_verdict", v["verdict"]),
        "pre_policy_reason_codes": v.get("pre_policy_reason_codes", v["reason_codes"]),
        "evidence_level": v.get("evidence_level"),
        "symbols": len([s for s in v.get("symbols") or [] if s.get("origin") != sy.LIFTED]),
        "context_only_symbols": sum(1 for s in v.get("symbols") or [] if s.get("context_only")),
        "not_covered": dict(Counter(nc["reason"] for nc in cov.get("not_covered") or [])),
        "mains": len(cov.get("main_packages") or []), "mains_skipped": len(cov.get("main_packages_skipped") or []),
        "mains_load_failed": sum(1 for m in pm.values() if m.get("load_failed")),
        "app_list_error": (cov.get("app_list_error") or None) and cov["app_list_error"][:200],
        "entries": dict(Counter(e["result"] for e in entries)),
        "entry_reasons": dict(Counter(e["reason_code"] for e in entries if e["reason_code"])),
        "method_pairs": dict(Counter(f"{e['methods']['CALLGRAPH_VTA']}+{e['methods']['LINKER_PRESENCE']}" for e in entries)),
        "method_errors": dict(Counter(c for e in entries for c in (e.get("method_errors") or {}).values())),
        "verification": {"status": ver["status"], "checks_run": ver["checks_run"], "failures": len(ver["failures"]),
                         "downgraded": ver.get("downgraded", 0),
                         "failed_by_kind": {k: s["failed"] for k, s in by_kind.items() if s.get("failed")}},
        "verified_paths": sum(1 for e in entries if e.get("verified_path")),
        "dynamic_edges_on_verified": sum(1 for e in entries if e.get("verified_path")
                                         for ed in e["verified_path"]["edges"] if ed["kind"] == "DYNAMIC"),
        "reachable_ranks": sorted({e["rank"] for e in entries if e["result"] == REACHABLE and e.get("rank")}),
        "retrieval": {"config_used": ret.get("config_used"), "fallback": ret.get("fallback"), "k": ret.get("k"),
                      "candidates_total": ret.get("candidates_total")} if ret else None,
        "first_method_error": next((m.get("first_error") for m in pm.values() if m.get("first_error")), None),
        "seconds": (v.get("timing") or {}).get("total_seconds"),
        "go_version": ((v.get("toolchain") or {}).get("helper") or {}).get("go_version"),
    }


def pre_verifier_verdict(v: dict[str, Any]) -> str:
    """The case verdict the rule table gave before the verifier (from the entries' recorded
    pre-verifier results; a case without entries keeps its verdict)."""
    entries = v["per_symbol"]
    if not entries:
        return v.get("pre_policy_verdict", v["verdict"])
    pre = [{"result": e.get("pre_verifier_result", e["result"]),
            "reason_code": e["reason_code"] if e.get("pre_verifier_result", e["result"]) == CANT_DETERMINE else None,
            "decides_verdict": e.get("decides_verdict", True)} for e in entries]
    return aggregate.case_result(pre, incomplete=not (v.get("coverage") or {}).get("complete", True))[0]


def _check_schema(v: dict[str, Any]) -> list[str]:
    return validation_errors("verdict", v)


# --- fixtures --------------------------------------------------------------------------------------
def _fixture_requests(case: dict[str, Any], pack: dict[str, dict[str, Any]]) -> dict[str, triage.TriageRequest]:
    target = case["targets"][0]
    p = pack[target["symbol"]]
    common = dict(app=FIXTURES_DIR, mains=[case["main_package"]], max_mains=1)
    return {
        triage.MODE_TARGETS: triage.TriageRequest(case_id=f"fixture:{case['id']}", mode="targets", targets=case["targets"],
                                                  target_origin=sy.FIXTURE, advisory=p["advisory"], **common),
        triage.MODE_FIX: triage.TriageRequest(case_id=f"fixture:{case['id']}", mode="fix", advisory=p["advisory"],
                                              fix_evidence=p["fix_evidence"], module_rel="", **common),
        triage.MODE_RELEASE: triage.TriageRequest(case_id=f"fixture:{case['id']}", mode="release", advisory=p["advisory"],
                                                  release_range=p["release_range"], candidate_code=p["candidate_code"],
                                                  module_rel="", **common),
    }


def corrupt_paths(path: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Three deliberately corrupted copies of a verified path."""
    out = {}
    p = copy.deepcopy(path)
    i = next((j for j, e in enumerate(p["edges"]) if e["call_site"]["file"]), None)
    if i is not None:
        p["edges"][i]["call_site"]["line"] += 1
        out["WRONG_LINE"] = p
    p = copy.deepcopy(path)
    if p["edges"]:
        first = p["edges"][0]
        fake = "vtfixtures/vulnlib.Safe"
        p["edges"][0:1] = [dict(first, callee=fake), dict(first, caller=fake)]
        out["EDGE_NOT_IN_GRAPH"] = p
    p = copy.deepcopy(path)
    if len(p["edges"]) >= 2:
        del p["edges"][len(p["edges"]) // 2]
        out["BROKEN_CHAIN"] = p
    elif p["edges"]:
        p["edges"][-1]["callee"] = p["edges"][-1]["callee"] + "Missing"
        out["BROKEN_CHAIN"] = p
    return out


def corruption_probe(pre_verdicts: list[dict[str, Any]], verifier_ctx: Callable) -> dict[str, Any]:
    """For each REACHABLE entry of a pre-verifier verdict, replace its paths by one corrupted path
    and verify again: the entry must end CANT_DETERMINE / VERIFIER_REJECTED."""
    from vulntrace.verifier.verify import verify

    rows = []
    for pv in pre_verdicts:
        info, incomplete, verdict = pv["info"], pv["incomplete"], pv["verdict"]
        for idx, e in enumerate(verdict["per_symbol"]):
            if e["result"] != REACHABLE or not e.get("paths"):
                continue
            for kind, bad in corrupt_paths(e["paths"][0]).items():
                v = copy.deepcopy(verdict)
                v["per_symbol"][idx]["paths"] = [bad]
                after = verify(v, verifier_ctx(info, incomplete))
                ae = after["per_symbol"][idx]
                rows.append({"case": verdict["case_id"], "corruption": kind, "result": ae["result"],
                             "reason_code": ae["reason_code"], "failed_checks": sorted({f["check"] for f in ae["verifier_failures"]})})
    by = {}
    for r in rows:
        b = by.setdefault(r["corruption"], {"total": 0, "rejected": 0})
        b["total"] += 1
        b["rejected"] += int(r["result"] == CANT_DETERMINE and r["reason_code"] == "VERIFIER_REJECTED")
    return {"by_corruption": by, "total": len(rows), "rejected": sum(b["rejected"] for b in by.values()), "rows": rows}


def confusion(rows: list[dict[str, Any]], key: str = "verdict") -> dict[str, Any]:
    m = {t: {o: 0 for o in VERDICTS} for t in (REACHABLE, NOT_REACHABLE)}
    for r in rows:
        m[r["truth"]][r[key]] += 1
    n = len(rows)
    correct = sum(m[t][t] for t in m)
    answered = sum(m[t][o] for t in m for o in (REACHABLE, NOT_REACHABLE))
    pred_r = m[REACHABLE][REACHABLE] + m[NOT_REACHABLE][REACHABLE]
    pred_nr = m[REACHABLE][NOT_REACHABLE] + m[NOT_REACHABLE][NOT_REACHABLE]
    return {
        "matrix": m, "n": n,
        "false_not_reachable": m[REACHABLE][NOT_REACHABLE], "false_reachable": m[NOT_REACHABLE][REACHABLE],
        "cant_determine": sum(m[t][CANT_DETERMINE] for t in m),
        "accuracy": wilson(correct, n),
        "coverage": wilson(answered, n),
        "selective_accuracy": wilson(correct, answered),
        "reachable_precision": wilson(m[REACHABLE][REACHABLE], pred_r),
        "reachable_recall": wilson(m[REACHABLE][REACHABLE], sum(m[REACHABLE].values())),
        "not_reachable_precision": wilson(m[NOT_REACHABLE][NOT_REACHABLE], pred_nr),
    }


def _stable_view(v: dict[str, Any]) -> Any:
    return [v["verdict"], v["reason_codes"],
            [[e["main_package"], e["target"], e["result"], e["reason_code"], e["methods"], e.get("verified_path")]
             for e in v["per_symbol"]]]


def eval_fixtures(runners_factory: Callable[[], triage.Runners], work_dir: Path, binary=None, log=print) -> dict[str, Any]:
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    pack = tfx.build_pack(work_dir, binary)
    base = runners_factory()
    runners = memo_runners(base)
    rows, schema_problems, pre_for_probe, verdicts = [], [], [], {}
    repo_commit = run_info([])["repo_commit"]
    for case in manifest["cases"]:
        for mode, req in _fixture_requests(case, pack).items():
            req.repo_commit = repo_commit
            v = triage.run_triage(req, runners)
            probs = _check_schema(v)
            if probs:
                schema_problems.append({"case": case["id"], "mode": mode, "errors": probs[:3]})
            row = {"id": case["id"], "category": case["category"], "truth": case["truth"],
                   "target": case["targets"][0]["symbol"], **verdict_row(v)}
            row["mode"] = mode
            row["analysed"] = [{"symbol": e["target"]["symbol"], "result": e["result"], "reason_code": e["reason_code"],
                                "pre_verifier": e.get("pre_verifier_result"), "rank": e.get("rank"),
                                "is_target": ck.normalise_symbol(e["target"]["symbol"]) == ck.normalise_symbol(case["targets"][0]["symbol"])}
                               for e in v["per_symbol"]]
            rows.append(row)
            verdicts[(case["id"], mode)] = v
            log(f"fixture {case['id']:<30} {mode:<8} truth={case['truth']:<14} verdict={v['verdict']:<14} "
                f"pre_policy={row['pre_policy_verdict']}")
            if mode == triage.MODE_TARGETS:
                pre = copy.deepcopy(v)
                pre["verdict"] = row["pre_verifier_verdict"]
                pre["reason_codes"] = [] if pre["verdict"] != CANT_DETERMINE else sorted(
                    {e["reason_code"] for e in pre["per_symbol"] if e["pre_verifier_result"] == CANT_DETERMINE})
                for e in pre["per_symbol"]:  # the pre-verifier evidence, as the verifier received it
                    e["result"], e["reason_code"], e["verified_path"] = e["pre_verifier_result"], (
                        None if e["pre_verifier_result"] != CANT_DETERMINE else e["reason_code"]), None
                    e["verifier_failures"] = []
                pre_for_probe.append({"info": base.inspect(FIXTURES_DIR, mains=[case["main_package"]], max_mains=1),
                                      "incomplete": False, "verdict": pre})
    # determinism: TARGETS mode again, without the memo
    unstable = []
    t0 = time.monotonic()
    for case in manifest["cases"]:
        v2 = triage.run_triage(_fixture_requests(case, pack)[triage.MODE_TARGETS], runners_factory())
        if _stable_view(v2) != _stable_view(verdicts[(case["id"], triage.MODE_TARGETS)]):
            unstable.append(case["id"])
    stability = {"cases": len(manifest["cases"]), "mode": triage.MODE_TARGETS, "unstable": unstable,
                 "seconds": round(time.monotonic() - t0, 1)}
    probe = corruption_probe(pre_for_probe, base.verifier_ctx)
    summary = {}
    for mode in (triage.MODE_TARGETS, triage.MODE_FIX, triage.MODE_RELEASE):
        mr = [r for r in rows if r["mode"] == mode]
        summary[mode] = {"final": confusion(mr), "pre_policy": confusion(mr, "pre_policy_verdict"),
                         "verifier_downgrades": sum(r["verification"]["downgraded"] for r in mr),
                         # a rejection is wrong when the rule table's verdict (before the verifier) was already right
                         "verifier_rejections_on_correct": sum(r["verification"]["downgraded"] for r in mr
                                                               if r["pre_verifier_verdict"] == r["truth"]),
                         "pre_verifier": confusion(mr, "pre_verifier_verdict"),
                         "verified_paths": sum(r["verified_paths"] for r in mr),
                         "reachable_without_verified_path": sum(1 for r in mr if r["verdict"] == REACHABLE and r["verified_paths"] == 0),
                         "seconds": seconds_summary([r["seconds"] for r in mr])}
    return {"schema_version": SCHEMA_VERSION, "set": "fixtures", "rows": rows, "summary": summary,
            "pack": tfx.pack_facts(pack), "stability": stability, "corruption_probe": probe,
            "schema_problems": schema_problems,
            "method_calls": {"vta": runners.vta.calls, "linker": runners.linker.calls}}


def seconds_summary(values: list[float | None]) -> dict[str, Any]:
    v = sorted(x for x in values if x is not None)
    if not v:
        return {"n": 0}
    q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]  # noqa: E731
    return {"n": len(v), "p50": q(0.5), "p95": q(0.95), "max": v[-1], "total": round(sum(v), 1)}


# --- D1 / D4 --------------------------------------------------------------------------------------
def pick_module(case: dict[str, Any], dataset: str) -> dict[str, Any] | None:
    if dataset == "d4":
        return datasets.pick_d4_module(case)
    with_core = [m for m in case["modules"] if any(p["core_symbols"] for p in m["packages"])]
    return (with_core or case["modules"] or [None])[0]


def curated_targets(module: dict[str, Any]) -> list[dict[str, str]]:
    return [{"package": p["package"], "symbol": s} for p in module["packages"] for s in p["core_symbols"]]


def run_real_case(dataset: str, entry: dict[str, Any], case: dict[str, Any], evidence: dict[str, Any], *,
                  repo_cache: Path | None, gomodcache: Path, work_root: Path, base: triage.Runners,
                  max_mains: int, keep_tree: bool = False) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """(compact row, full verdict or None, full reference verdict or None) for one D1/D4 case."""
    t_case = time.monotonic()
    cid = case["id"]
    module = pick_module(case, dataset)
    row: dict[str, Any] = {"id": cid, "created": entry.get("created"), "cluster_key": entry.get("cluster_key") or cid,
                           "evidence_status": None, "prep": None, "reference": None}
    if dataset == "d1":
        row["evidence_status"] = (evidence["fix_evidence"] or {}).get("status", "MISSING")
    else:
        row["evidence_status"] = (evidence["release_range"] or {}).get("status", "MISSING")
    adv = dict(case)
    if module:
        adv.update(module=module["module"], vulnerable_at=module["vulnerable_at"], fixed_in=module["fixed_in"])
    fc = case["fix_commits"][0] if case["fix_commits"] else None
    work = work_root / cid
    # the vulnerable-side tree: D1 the fix commit's parent, D4 the range's from-commit
    sha, err, repo_dir = None, None, None
    if fc is None or module is None:
        err = "no fix commit or no module"
    elif dataset == "d1":
        repo_dir, sha, err = lift_eval.ensure_parent(fc, repo_cache)
    else:
        rr = evidence["release_range"] or {}
        sha = (rr.get("from") or {}).get("commit")
        repo_dir = lift_eval.git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], repo_cache)
        if not sha:
            err = f"release range {rr.get('status', 'MISSING')} has no from-commit"
    t0 = time.monotonic()
    if err:
        prep = {"status": lift_prep.NO_SOURCE, "reason": err, "module_dir": None, "module_rel": None}
    else:
        prep = lift_prep.prepare_case(repo_dir, sha, module["module"], work, gomodcache,
                                      repo_prefix=f"{fc['host']}/{fc['owner']}/{fc['repo']}")
    row["prep"] = {k: prep.get(k) for k in ("status", "reason", "module_rel", "synthesized_go_mod", "vendored", "vendor_dropped")}
    row["prep"]["seconds"] = round(time.monotonic() - t0, 1)
    row["commit"] = sha
    reference_targets = curated_targets(module) if module else []
    verdict = ref = None
    # a tree that was extracted but whose `go mod tidy` failed (most often: go.mod needs a newer Go than
    # GOTOOLCHAIN=local provides) still goes through the pipeline, which must answer CANT_DETERMINE itself
    if prep["status"] == lift_prep.READY or (prep["status"] == lift_prep.PREP_FAILED and prep.get("module_dir")):
        runners = memo_runners(base, reference_targets)
        common = dict(app=Path(prep["module_dir"]), commit=sha, module_rel=prep["module_rel"] or "", max_mains=max_mains,
                      advisory=adv, vulndb_commit=(case.get("source") or {}).get("vulndb_commit"))
        if dataset == "d1":
            req = triage.TriageRequest(case_id=cid, mode="auto", fix_evidence=evidence["fix_evidence"], **common)
        else:
            req = triage.TriageRequest(case_id=cid, mode="release", release_range=evidence["release_range"],
                                       candidate_code=evidence["candidate_code"], **common)
        verdict = triage.run_triage(req, runners)
        row.update(verdict_row(verdict))
        row["schema_errors"] = _check_schema(verdict)[:3]
        gold = {_key(t) for t in reference_targets}
        row["gold_analysed"] = any(_key(s) in gold for s in verdict.get("symbols") or [] if s.get("origin") != sy.LIFTED)
        row["gold_count"] = len(gold)
        if reference_targets:
            rreq = triage.TriageRequest(case_id=cid, mode="targets", targets=reference_targets, target_origin="CURATED_CORE",
                                        **{k: v for k, v in common.items() if k not in ("module_rel",)})
            ref = triage.run_triage(rreq, runners)
            row["reference"] = {"verdict": ref["verdict"], "reason_codes": ref["reason_codes"],
                                "entries": dict(Counter(e["result"] for e in ref["per_symbol"]))}
        row["method_calls"] = {"vta": runners.vta.calls, "linker": runners.linker.calls}
    else:
        row.update(mode=None, verdict=None, pre_policy_verdict=None, reason_codes=[], seconds=None)
    if not keep_tree:
        shutil.rmtree(work, ignore_errors=True)
    row["case_seconds"] = round(time.monotonic() - t_case, 1)
    return row, verdict, ref


DISK_MIN_FREE_GB = 10.0


class DiskGuard:
    """Real modules can need gigabytes of dependencies and build cache. Before a case starts, if the
    free space under `path` is below `min_free_gb`, wait until no case is in flight and empty this
    process's Go module and build caches (`go clean -modcache -cache`), so a run never fails for
    lack of disk and never cleans a cache another case of this process is using. Counted."""

    def __init__(self, path: Path, min_free_gb: float = DISK_MIN_FREE_GB, cleaner=None, free_gb=None, log=print):
        self.path, self.min_free_gb, self.log = Path(path), min_free_gb, log
        self.cleaner = cleaner or _clean_go_caches
        self.free_gb = free_gb or (lambda: shutil.disk_usage(self.path).free / 1e9)
        self.cond = threading.Condition()
        self.active = 0
        self.cleanups = 0

    def enter(self) -> None:
        with self.cond:
            while self.free_gb() < self.min_free_gb and self.active > 0:
                self.cond.wait(timeout=30)
            if self.free_gb() < self.min_free_gb:
                before = self.free_gb()
                self.cleaner()
                self.cleanups += 1
                self.log(f"disk guard: {before:.1f} GB free < {self.min_free_gb} GB; Go caches cleaned, now {self.free_gb():.1f} GB")
            self.active += 1

    def leave(self) -> None:
        with self.cond:
            self.active -= 1
            self.cond.notify_all()


def _clean_go_caches() -> None:
    import subprocess

    from vulntrace.env import go_env

    subprocess.run(["go", "clean", "-modcache", "-cache"], env=go_env(), capture_output=True, timeout=1800)


def _write_gz(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, sort_keys=True)
    os.replace(tmp, path)


def _read_gz(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def eval_real(dataset: str, case_list: dict[str, Any], cases_by_id: dict[str, dict], data_dir: Path, *,
              base_factory: Callable[[], triage.Runners], repo_cache: Path | None, gomodcache: Path, jobs: int = 2,
              max_mains: int = EVAL_MAX_MAINS, limit: int | None = None, only: list[str] | None = None,
              rerun: bool = False, stability: int = 0, log=print) -> dict[str, Any]:
    from vulntrace.pipeline.inputs import load_evidence

    out_dir = Path(data_dir) / "triage" / dataset
    work_root = Path(data_dir) / WORK_SUBDIR / dataset
    entries = sorted(case_list["cases"], key=lambda c: c["id"])
    if only:
        entries = [e for e in entries if e["id"] in set(only)]
    if limit:
        entries = entries[:limit]
    todo = [e for e in entries if rerun or not (out_dir / f"{e['id']}.row.json").is_file()]
    log(f"triage {dataset}: {len(entries)} cases, {len(entries) - len(todo)} done, {len(todo)} to run, {jobs} job(s)")
    base = base_factory()
    guard = DiskGuard(data_dir, log=log)

    def work(e):
        guard.enter()
        try:
            return _work(e)
        finally:
            guard.leave()

    def _work(e):
        cid = e["id"]
        case = cases_by_id.get(cid)
        if case is None:
            row = {"id": cid, "created": e.get("created"), "cluster_key": e.get("cluster_key") or cid,
                   "evidence_status": "NO_VULNCASE", "prep": None, "verdict": None, "pre_policy_verdict": None,
                   "reason_codes": [], "reference": None, "mode": None}
            v = r = None
        else:
            row, v, r = run_real_case(dataset, e, case, load_evidence(cid, data_dir), repo_cache=repo_cache,
                                      gomodcache=gomodcache, work_root=work_root, base=base, max_mains=max_mains)
        if v is not None:
            _write_gz(out_dir / f"{cid}.verdict.json.gz", v)
        if r is not None:
            _write_gz(out_dir / f"{cid}.reference.json.gz", r)
        (out_dir / f"{cid}.row.json").write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
        return row

    out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {ex.submit(work, e): e["id"] for e in todo}
        for i, f in enumerate(as_completed(futs), start=1):
            cid = futs[f]
            try:
                row = f.result()
                log(f"{i}/{len(todo)} {cid} prep={row['prep'] and row['prep']['status']} mode={row.get('mode')} "
                    f"verdict={row.get('verdict')} pre_policy={row.get('pre_policy_verdict')} reasons={row.get('reason_codes')} "
                    f"ref={(row.get('reference') or {}).get('verdict')} {row.get('case_seconds')}s")
            except Exception as exc:  # recorded, never silent
                log(f"{i}/{len(todo)} {cid} FAILED: {exc!r}")
                (out_dir / f"{cid}.row.json").write_text(json.dumps(
                    {"id": cid, "harness_error": repr(exc)[:500], "verdict": None, "pre_policy_verdict": None,
                     "reason_codes": [], "mode": None, "prep": None, "reference": None,
                     "cluster_key": next((e.get("cluster_key") for e in todo if e["id"] == cid), cid)}), encoding="utf-8")
    rows = [json.loads((out_dir / f"{e['id']}.row.json").read_text(encoding="utf-8")) for e in entries
            if (out_dir / f"{e['id']}.row.json").is_file()]
    doc = {"schema_version": SCHEMA_VERSION, "set": dataset, "rows": rows, "summary": summarize_real(dataset, rows),
           "max_mains": max_mains, "disk_guard": {"min_free_gb": guard.min_free_gb, "cache_cleanups": guard.cleanups}}
    if stability:
        doc["stability"] = stability_check(dataset, entries, rows, cases_by_id, data_dir, out_dir, stability, repo_cache=repo_cache,
                                           gomodcache=gomodcache, base=base, max_mains=max_mains, log=log)
    return doc


def stability_check(dataset, entries, rows, cases_by_id, data_dir, out_dir, n, *, repo_cache, gomodcache, base, max_mains,
                    log=print) -> dict[str, Any]:
    """Re-run the first `n` cases (by id) that produced per-symbol entries, from a fresh tree and an
    empty method cache, and compare verdict, reasons, entry results, method results and verified
    paths with the saved verdict."""
    from vulntrace.pipeline.inputs import load_evidence

    by_id = {e["id"]: e for e in entries}
    picked = [r["id"] for r in sorted(rows, key=lambda r: r["id"]) if sum((r.get("entries") or {}).values()) > 0
              and (out_dir / f"{r['id']}.verdict.json.gz").is_file()][:n]
    work_root = Path(data_dir) / WORK_SUBDIR / f"{dataset}-stability"
    differ, t0 = [], time.monotonic()
    for cid in picked:
        _, v, _ = run_real_case(dataset, by_id[cid], cases_by_id[cid], load_evidence(cid, data_dir), repo_cache=repo_cache,
                                gomodcache=gomodcache, work_root=work_root, base=base, max_mains=max_mains)
        saved = _read_gz(out_dir / f"{cid}.verdict.json.gz")
        same = v is not None and _stable_view(v) == _stable_view(saved)
        log(f"stability {cid}: {'same' if same else 'DIFFERENT'}")
        if not same:
            differ.append(cid)
    return {"cases": picked, "different": differ, "seconds": round(time.monotonic() - t0, 1)}


PSEUDO_REPLICATE_CASE = "GO-2026-6181"  # CP3 review finding 1: nine rclone advisories (GO-2026-6181..6199) share one range


LOAD_CAUSES = (  # first match wins; patterns are go command / go/packages messages
    ("GO_VERSION_TOO_OLD", ("requires go >=", "go.mod requires go", "toolchain")),
    ("MISSING_DEPENDENCY", ("no required module provides", "missing go.sum entry", "cannot find module",
                            "module lookup disabled", "unknown revision", "updates to go.mod needed")),
    ("GOPATH_STYLE_IMPORT", ("is not in std",)),
    ("CGO_OR_BUILD_CONSTRAINTS", ("build constraints exclude", "cgo", "C source files not allowed")),
    ("VENDOR_INCONSISTENT", ("inconsistent vendoring", "vendor/modules.txt")),
    ("TIMEOUT", ("exceeded", "timed out")),
    ("TYPE_ERRORS", ("TYPE_ERRORS", "undefined:", "cannot use", "not enough arguments")),
)


def load_cause(row: dict[str, Any]) -> str | None:
    """A coarse cause for a case where the app could not be listed or every main package failed to
    load or build (None otherwise). From the first error line recorded in the row."""
    codes = row.get("pre_policy_reason_codes") or []
    if "APP_LOAD_FAILED" not in codes:
        return None
    text = (row.get("app_list_error") or row.get("first_method_error") or "")
    for cause, needles in LOAD_CAUSES:
        if any(n in text for n in needles):
            return cause
    return "OTHER"


def summarize_real(dataset: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    def dist(rs, key="verdict"):
        return dict(Counter(r.get(key) or "NOT_RUN" for r in rs))

    ran = [r for r in rows if r.get("verdict")]
    out: dict[str, Any] = {
        "cases": len(rows), "harness_errors": sum(1 for r in rows if r.get("harness_error")),
        "evidence_status": dict(Counter(r.get("evidence_status") for r in rows)),
        "prep_status": dict(Counter((r.get("prep") or {}).get("status") or "NOT_PREPARED" for r in rows)),
        "triaged": len(ran),
        "mode": dict(Counter(r.get("mode") for r in ran)), "mode_reason": dict(Counter(r.get("mode_reason") for r in ran)),
        "verdict": dist(ran), "pre_policy_verdict": dist(ran, "pre_policy_verdict"),
        "reason_codes": dict(Counter(c for r in ran for c in r.get("reason_codes") or [])),
        "pre_policy_reason_codes": dict(Counter(c for r in ran for c in r.get("pre_policy_reason_codes") or [])),
        "entry_results": dict(sum((Counter(r.get("entries") or {}) for r in ran), Counter())),
        "method_pairs": dict(sum((Counter(r.get("method_pairs") or {}) for r in ran), Counter())),
        "method_errors": dict(sum((Counter(r.get("method_errors") or {}) for r in ran), Counter())),
        "not_covered": dict(sum((Counter(r.get("not_covered") or {}) for r in ran), Counter())),
        "context_only_symbols": sum(r.get("context_only_symbols") or 0 for r in ran),
        "symbols": sum(r.get("symbols") or 0 for r in ran),
        "mains_analysed": sum(r.get("mains") or 0 for r in ran), "cases_with_mains_skipped": sum(1 for r in ran if r.get("mains_skipped")),
        "cases_no_main": sum(1 for r in ran if "UNSUPPORTED_TARGET" in (r.get("pre_policy_reason_codes") or [])),
        "cases_all_mains_load_failed": sum(1 for r in ran if "APP_LOAD_FAILED" in (r.get("pre_policy_reason_codes") or [])),
        "verification": {"checks_run": sum((r.get("verification") or {}).get("checks_run", 0) for r in ran),
                         "downgraded_entries": sum((r.get("verification") or {}).get("downgraded", 0) for r in ran),
                         "cases_with_downgrade": sum(1 for r in ran if (r.get("verification") or {}).get("downgraded")),
                         "failed_by_kind": dict(sum((Counter((r.get("verification") or {}).get("failed_by_kind") or {}) for r in ran), Counter()))},
        "reachable_without_verified_path": sum(1 for r in ran if r.get("verdict") == REACHABLE and not r.get("verified_paths")),
        "dynamic_edges_on_verified": sum(r.get("dynamic_edges_on_verified") or 0 for r in ran),
        "seconds": seconds_summary([r.get("case_seconds") for r in rows]),
        "triage_seconds": seconds_summary([r.get("seconds") for r in ran]),
        "prep_seconds": seconds_summary([(r.get("prep") or {}).get("seconds") for r in rows]),
        "fallbacks": {
            "mode_fix_to_release": sum(1 for r in ran if r.get("mode_reason") == triage.R_FIX_EVIDENCE_UNUSABLE),
            "retriever": dict(Counter((r.get("retrieval") or {}).get("fallback") for r in ran if r.get("retrieval"))),
            "synthesized_go_mod": sum(1 for r in rows if (r.get("prep") or {}).get("synthesized_go_mod")),
            "vendor_dropped": sum(1 for r in rows if (r.get("prep") or {}).get("vendor_dropped")),
            "mains_over_limit": sum(1 for r in ran if r.get("mains_skipped")),
        },
        "go_versions": dict(Counter(r.get("go_version") for r in ran if r.get("go_version"))),
        "app_load_failure_causes": dict(Counter(c for c in (load_cause(r) for r in ran) if c)),
    }
    with_ref = [r for r in ran if r.get("reference")]
    out["reference"] = {
        "cases": len(with_ref),
        "verdict": dict(Counter(r["reference"]["verdict"] for r in with_ref)),
        "pairs_pre_policy": dict(Counter(f"{r['pre_policy_verdict']}|{r['reference']['verdict']}" for r in with_ref)),
        "gold_analysed": sum(1 for r in ran if r.get("gold_analysed")),
    }
    # D4 pseudo-replication: also without the rclone cluster, and the number of distinct ranges per verdict
    if dataset == "d4":
        key = next((r.get("cluster_key") for r in rows if r["id"] == PSEUDO_REPLICATE_CASE), None)
        no_rc = [r for r in ran if r.get("cluster_key") != key]
        out["without_rclone_cluster"] = {"cluster_key": key, "cases_in_cluster": sum(1 for r in rows if r.get("cluster_key") == key),
                                         "triaged": len(no_rc), "verdict": dist(no_rc), "pre_policy_verdict": dist(no_rc, "pre_policy_verdict")}
        out["distinct_ranges"] = {v: len({r["cluster_key"] for r in ran if r.get("pre_policy_verdict") == v}) for v in VERDICTS}
        flags = [1.0 if r.get("pre_policy_verdict") == REACHABLE else 0.0 for r in ran]
        out["pre_policy_reachable_share_cluster_ci"] = metrics.cluster_bootstrap_ci(flags, [r["cluster_key"] for r in ran], SEED) if ran else None
    return out


def write_json(path: Path, obj: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def replace_root(text: str, root: str, label: str) -> str:
    """Replace the local directory `root` in JSON `text` only where it begins an absolute path (not
    preceded by a path or name character, followed by a separator, the end of the string or of the
    text). A plain replace corrupted repository paths: with HOME=/root, `cmd/root.go` became
    `cmd<local>.go` (found in CP7b)."""
    root = root.rstrip("/\\") if len(root) > 1 else root
    if not root:
        return text
    pat = r"(?<![A-Za-z0-9_.~/\\-])" + re.escape(json.dumps(root)[1:-1]) + r'(?=/|\\\\|"|$)'
    return re.sub(pat, lambda m: label, text)


def example_verdict(v: Any) -> Any:
    """Anything committed (a verdict, a results file): local absolute paths become `<local>`."""
    text = json.dumps(v)
    for root in sorted({str(REPO_ROOT), tempfile.gettempdir(), str(Path.home())}, key=len, reverse=True):
        text = replace_root(text, root, "<local>")
    return json.loads(text)
