"""One triage run: advisory + app -> one verdict object (schemas/verdict.schema.json).

Stages: mode choice -> target symbols (Mode 1: every changed non-test function; Mode 2: the
retriever's top-k) -> optional lifting (extra, non-deciding seeds) -> two methods per symbol and
main package -> rule table -> evidence verifier (downgrade-only) -> case verdict -> Mode 2
policy -> output. A data problem (no evidence, no candidate, app does not load) is a
CANT_DETERMINE verdict with a reason code, never an exception.
"""

import copy
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vulntrace import __version__
from vulntrace.methods.helper import CONTRACT_VERSION
from vulntrace.pipeline import aggregate, analyse as an, app as app_mod, symbols as sy
from vulntrace.verdict import (APP_LOAD_FAILED, CANT_DETERMINE, NO_FIX_EVIDENCE, NO_RELEASE_EVIDENCE,
                               NO_TARGET_SYMBOLS, REACHABLE, SCHEMA_VERSION, STATEMENT, UNSUPPORTED_TARGET)

MODE_FIX, MODE_RELEASE, MODE_TARGETS = "FIX", "RELEASE", "TARGETS"
REQ_AUTO = "AUTO"
LEVEL = {MODE_FIX: "CHANGED_FUNCTION_LEVEL", MODE_RELEASE: "CANDIDATE_LEVEL", MODE_TARGETS: "TARGET_LEVEL"}
USABLE_FIX_STATUSES = ("AVAILABLE",)
USABLE_RANGE_STATUSES = ("AVAILABLE", "TRUNCATED")  # TRUNCATED caps the commit walk, not the two-tree diff

# mode_selection.reason values
R_TARGETS_GIVEN = "TARGETS_GIVEN"
R_REQUESTED = "REQUESTED"
R_FIX_COMMIT_KNOWN = "FIX_COMMIT_KNOWN"
R_NO_FIX_COMMIT = "NO_FIX_COMMIT"
R_FIX_EVIDENCE_UNUSABLE = "FIX_EVIDENCE_UNUSABLE_FALLBACK_TO_RELEASE"

ENV_FLAGS = {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOPROXY": "off"}

BASE_LIMITATIONS = [
    "Reachability only: a call path from main or init to a symbol does not show that the vulnerable behaviour "
    "can be triggered or exploited.",
    "Analysed for this machine's GOOS/GOARCH with CGO_ENABLED=0 and no build tags; other build configurations "
    "can differ.",
    "Calls made only through reflect or unsafe can be missed by the call graph; a NOT_REACHABLE needs the linker "
    "method to agree (symbol absent from the binary), which guards against that (CP2).",
]


@dataclass
class Runners:
    """Every external effect of a triage run, injectable for tests."""
    vta: an.MethodFn
    linker: an.MethodFn
    verifier_ctx: Callable[[app_mod.AppInfo, bool], Any] | None = None   # (app, incomplete) -> VerifyContext
    inspect: Callable[..., app_mod.AppInfo] = app_mod.inspect_app
    lift: Callable[[Path, list[dict[str, str]], str], list[dict[str, Any]]] | None = None
    rank: Callable[..., Any] | None = None                                 # retrieve.rank_candidates


@dataclass
class TriageRequest:
    case_id: str
    app: Path
    mode: str = "auto"                              # auto | fix | release | targets
    advisory: dict[str, Any] | None = None          # VulnCase-like: id, summary, details, module, fix_commits, ...
    fix_evidence: dict[str, Any] | None = None
    release_range: dict[str, Any] | None = None
    candidate_code: dict[str, Any] | None = None
    targets: list[dict[str, str]] | None = None
    target_origin: str = sy.USER
    module_rel: str | None = None                   # the advisory module's directory in the fix repository
    mains: list[str] | None = None
    max_mains: int = app_mod.DEFAULT_MAX_MAINS
    commit: str | None = None                       # the commit an extracted tree came from
    k: int | None = None
    retriever: str = "fixed"
    lift_rule: str | None = None                    # None (off), NEAREST or ALL
    mode2_policy: str = aggregate.MODE2_POLICY_DOWNGRADE
    run_verifier: bool = True
    vulndb_commit: str | None = None
    repo_commit: str | None = None
    created_at: str | None = None
    extra_limitations: list[str] = field(default_factory=list)


def _fix_usable(fe: dict[str, Any] | None) -> bool:
    return bool(fe) and fe.get("status") in USABLE_FIX_STATUSES and bool(fe.get("candidates"))


def _range_usable(rr: dict[str, Any] | None) -> bool:
    return bool(rr) and rr.get("status") in USABLE_RANGE_STATUSES


def choose_mode(req: TriageRequest) -> dict[str, str]:
    """mode_selection: requested, chosen, reason, explanation."""
    requested = req.mode.upper()
    if requested not in (REQ_AUTO, MODE_FIX, MODE_RELEASE, MODE_TARGETS):
        raise ValueError(f"unknown mode {req.mode!r}")
    if requested == MODE_TARGETS or (requested == REQ_AUTO and req.targets):
        return {"requested": requested, "chosen": MODE_TARGETS, "reason": R_TARGETS_GIVEN,
                "explanation": "target symbols were given directly"}
    if requested in (MODE_FIX, MODE_RELEASE):
        return {"requested": requested, "chosen": requested, "reason": R_REQUESTED,
                "explanation": f"mode {requested} was requested"}
    has_fix = bool((req.advisory or {}).get("fix_commits"))
    if has_fix and _fix_usable(req.fix_evidence):
        return {"requested": REQ_AUTO, "chosen": MODE_FIX, "reason": R_FIX_COMMIT_KNOWN,
                "explanation": "the advisory names a fix commit and its diff is available: Mode 1 analyses every "
                               "changed non-test function"}
    if has_fix and _range_usable(req.release_range):
        status = (req.fix_evidence or {}).get("status", "MISSING")
        return {"requested": REQ_AUTO, "chosen": MODE_RELEASE, "reason": R_FIX_EVIDENCE_UNUSABLE,
                "explanation": f"the advisory names a fix commit but its evidence is not usable ({status}); Mode 2 "
                               "on the release range instead"}
    if has_fix:
        return {"requested": REQ_AUTO, "chosen": MODE_FIX, "reason": R_FIX_COMMIT_KNOWN,
                "explanation": "the advisory names a fix commit, but neither its diff nor a release range is usable"}
    return {"requested": REQ_AUTO, "chosen": MODE_RELEASE, "reason": R_NO_FIX_COMMIT,
            "explanation": "the advisory names no fix commit: Mode 2 on the release range"}


def _fix_commit(req: TriageRequest) -> dict[str, str] | None:
    fcs = (req.advisory or {}).get("fix_commits") or []
    return fcs[0] if fcs else None


def _module_rel(req: TriageRequest) -> str:
    if req.module_rel is not None:
        return req.module_rel
    return sy.module_rel_for((req.advisory or {}).get("module") or "", _fix_commit(req))


def select_symbols(req: TriageRequest, mode: str, runners: Runners) -> tuple[list[dict], list[dict], list[str], dict | None]:
    """(targets, not covered, blocking reason codes, retrieval summary)."""
    if mode == MODE_TARGETS:
        return sy.given_symbols(req.targets or [], req.target_origin), [], ([] if req.targets else [NO_TARGET_SYMBOLS]), None
    module = (req.advisory or {}).get("module")
    if mode == MODE_FIX:
        if not _fix_usable(req.fix_evidence) or not module:
            return [], [], [NO_FIX_EVIDENCE], None
        t, nc = sy.mode1_symbols(req.fix_evidence, module, _module_rel(req))
        return t, nc, ([] if t else [NO_TARGET_SYMBOLS]), None
    if not _range_usable(req.release_range) or req.candidate_code is None or not module:
        return [], [], [NO_RELEASE_EVIDENCE], None
    if not req.release_range.get("candidates"):
        return [], [], [NO_TARGET_SYMBOLS], None
    fc = _fix_commit(req) or {"owner": "", "repo": ""}
    from vulntrace.pipeline import retrieve

    rank = runners.rank or retrieve.rank_candidates
    ranking = rank(req.advisory, req.release_range, req.candidate_code, fc["owner"], fc["repo"],
                   config=req.retriever, k=req.k)
    t, nc = sy.mode2_symbols(req.release_range, ranking.ranked, ranking.k, module, _module_rel(req))
    return t, nc, ([] if t else [NO_TARGET_SYMBOLS]), ranking.summary()


def lifted_symbols(req: TriageRequest, info: app_mod.AppInfo, targets: list[dict], runners: Runners) -> tuple[list[dict], dict]:
    """Extra, non-deciding LIFTED seeds (CP5b: a widening aid only). Run only when the app is the
    vulnerable module itself, because lifting walks that module's own callers."""
    note: dict[str, Any] = {"rule": req.lift_rule, "run": False, "reason": None, "added": 0}
    module = (req.advisory or {}).get("module")
    if not req.lift_rule:
        note["reason"] = "off"
        return [], note
    if runners.lift is None or info.module != module:
        note["reason"] = "lifting needs the vulnerable module's own source as the app; not run"
        return [], note
    records = runners.lift(info.module_dir, [{"package": t["package"], "symbol": t["symbol"]} for t in targets], req.lift_rule)
    have = {(t["package"], t["symbol"]) for t in targets}
    out: dict[tuple[str, str], dict] = {}
    for rec in records:
        for ent in ((rec.get("rules") or {}).get(req.lift_rule) or {}).get("entries", []):
            k = (ent["package"], ent["symbol"])
            if k in have:
                continue
            s = out.setdefault(k, {"package": ent["package"], "symbol": ent["symbol"], "origin": sy.LIFTED, "rank": None,
                                   "score": None, "candidate_id": None, "side": None, "lifted_from": [],
                                   "decides_verdict": False})
            if rec["target"]["symbol"] not in s["lifted_from"]:
                s["lifted_from"].append(rec["target"]["symbol"])
    note.update(run=True, added=len(out), errors=sum(1 for r in records if r.get("error")))
    return list(out.values()), note


def _limitations(mode: str, req: TriageRequest, info: app_mod.AppInfo, not_covered: list[dict], entries: list[dict],
                 retrieval: dict | None, lift_note: dict) -> list[str]:
    out = list(BASE_LIMITATIONS)
    if mode == MODE_FIX:
        out.append("Mode 1 checks every function the fix changed (CHANGED_FUNCTION_LEVEL): a reachable changed function "
                   "need not be the vulnerable one.")
    if mode == MODE_RELEASE:
        k = (retrieval or {}).get("k")
        out.append(f"Mode 2 checks only the retriever's top {k} candidates (CANDIDATE_LEVEL): REACHABLE means one of "
                   "them is reachable, not that the vulnerable function is; the candidate list missed the root cause "
                   "in about 16-19% of D4 cases (CP4-CP6).")
        if (retrieval or {}).get("fallback"):
            out.append(f"The fixed retriever {retrieval['config_requested']} was not available "
                       f"({retrieval['fallback_reason']}); candidates were ranked with {retrieval['config_used']}.")
    by_reason: dict[str, int] = {}
    for nc in not_covered:
        by_reason[nc["reason"]] = by_reason.get(nc["reason"], 0) + 1
    for reason, n in sorted(by_reason.items()):
        out.append(f"{n} candidate function(s) not analysed: {reason}.")
    if info.mains_skipped:
        out.append(f"{len(info.mains_skipped)} main package(s) over the limit of {req.max_mains} were not analysed, so "
                   "NOT_REACHABLE cannot be concluded for this app.")
    if info.dirty:
        out.append("The app's git work tree had uncommitted changes; files were checked as analysed on disk.")
    dyn = sum(1 for e in entries if e["result"] == REACHABLE and e.get("verified_path")
              for ed in e["verified_path"]["edges"] if ed["kind"] == "DYNAMIC")
    if dyn:
        out.append(f"{dyn} edge(s) of the verified path(s) are DYNAMIC (interface or function-value calls resolved by "
                   "VTA), which can over-approximate.")
    if lift_note.get("run"):
        out.append("LIFTED symbols are reported for context only and never decide the verdict.")
    out += req.extra_limitations
    return out


def run_triage(req: TriageRequest, runners: Runners) -> dict[str, Any]:
    t_start = time.monotonic()
    timing: dict[str, float] = {}
    sel = choose_mode(req)
    mode = sel["chosen"]
    level = LEVEL[mode]

    t0 = time.monotonic()
    targets, not_covered, blocking, retrieval = select_symbols(req, mode, runners)
    timing["symbols_seconds"] = round(time.monotonic() - t0, 2)

    t0 = time.monotonic()
    info = runners.inspect(req.app, mains=req.mains, max_mains=req.max_mains, commit=req.commit)
    timing["inspect_seconds"] = round(time.monotonic() - t0, 2)
    if not blocking:
        if info.list_error:
            blocking = [APP_LOAD_FAILED]
        elif not info.mains:
            blocking = [UNSUPPORTED_TARGET]

    lift_note: dict[str, Any] = {"rule": req.lift_rule, "run": False, "reason": "not reached", "added": 0}
    lifted: list[dict] = []
    if not blocking and req.lift_rule:
        t0 = time.monotonic()
        lifted, lift_note = lifted_symbols(req, info, targets, runners)
        timing["lift_seconds"] = round(time.monotonic() - t0, 2)
    all_symbols = targets + lifted

    entries: list[dict] = []
    facts: dict[str, Any] = {"per_main": {}, "toolchain": {}}
    if not blocking:
        t0 = time.monotonic()
        entries, facts = an.analyse(info.module_dir, info.mains, all_symbols, level, runners.vta, runners.linker)
        timing["methods_seconds"] = round(time.monotonic() - t0, 2)
    incomplete = bool(info.mains_skipped)
    verdict, reasons = aggregate.case_result(entries, blocking, incomplete)
    if entries and info.mains and all(m["load_failed"] for m in facts["per_main"].values()) and verdict == CANT_DETERMINE:
        reasons = sorted(set(reasons) | {APP_LOAD_FAILED})

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": req.case_id,
        "target_app": info.target_app(),
        "verdict": verdict,
        "reason_codes": reasons,
        "per_symbol": entries,
        "verification": {"status": "NOT_RUN", "checks_run": 0, "failures": []},
        "statement": STATEMENT,
        "provenance": {"pipeline_version": __version__, "helper_contract": CONTRACT_VERSION,
                       "vulndb_commit": req.vulndb_commit, "repo_commit": req.repo_commit,
                       "created_at": req.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "mode": mode,
        "mode_selection": sel,
        "evidence_level": level,
        "advisory": _advisory_summary(req),
        "symbols": all_symbols,
        "retrieval": retrieval,
        "coverage": {
            "main_packages": info.mains, "main_packages_skipped": info.mains_skipped, "max_mains": req.max_mains,
            "complete": not incomplete, "app_list_error": info.list_error, "package_errors": info.package_errors[:20],
            "package_errors_total": len(info.package_errors),
            "symbols_analysed": len(targets), "symbols_lifted": len(lifted), "not_covered": not_covered,
            "per_main": facts["per_main"], "lifting": lift_note,
            "fix_evidence_status": (req.fix_evidence or {}).get("status") if req.fix_evidence is not None else None,
            "release_range_status": (req.release_range or {}).get("status") if req.release_range is not None else None,
        },
        "toolchain": {**facts["toolchain"], "env": dict(ENV_FLAGS)},
    }
    pre_verifier = copy.deepcopy(out)
    if req.run_verifier and entries and runners.verifier_ctx is not None:
        from vulntrace.verifier.verify import verify

        t0 = time.monotonic()
        out = verify(out, runners.verifier_ctx(info, incomplete))
        timing["verifier_seconds"] = round(time.monotonic() - t0, 2)

    out["pre_policy_verdict"], out["pre_policy_reason_codes"] = out["verdict"], list(out["reason_codes"])
    if mode == MODE_RELEASE:
        v, r, applied = aggregate.apply_mode2_policy(out["verdict"], out["reason_codes"], req.mode2_policy)
        out["verdict"], out["reason_codes"] = v, r
        out["policy"] = {"name": aggregate.MODE2_POLICY_NAME, "applied": applied,
                         "rule": aggregate.MODE2_POLICY_RULE if req.mode2_policy == aggregate.MODE2_POLICY_DOWNGRADE
                         else "KEEP: a Mode 2 NOT_REACHABLE is reported as it is."}
    aggregate.assert_downgrade_only(pre_verifier, out)
    out["limitations"] = _limitations(mode, req, info, not_covered, out["per_symbol"], retrieval, lift_note)
    timing["total_seconds"] = round(time.monotonic() - t_start, 2)
    out["timing"] = timing
    return out


def _advisory_summary(req: TriageRequest) -> dict[str, Any]:
    a = req.advisory or {}
    return {"id": a.get("id", req.case_id), "module": a.get("module"), "vulnerable_at": a.get("vulnerable_at"),
            "fixed_in": a.get("fixed_in"),
            "fix_commits": [{k: fc.get(k) for k in ("host", "owner", "repo", "sha")} for fc in a.get("fix_commits") or []],
            "source": a.get("_source", "vulndb")}
