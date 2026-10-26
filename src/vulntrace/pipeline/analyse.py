"""Two independent reachability methods per target symbol and main package, combined by the
rule table (`vulntrace.verdict.symbol_verdict`, verifier column not yet applied).

Method 1: linker presence (CP1) - build the main package with inlining off and look for the
symbol in the binary. Method 2: VTA call graph (CP2) - the Go helper's `reach` mode, roots
`main` and `init`. Builds use GOTOOLCHAIN=local and CGO_ENABLED=0; the built binary is only
read by `go tool nm` and deleted, never run.
"""

import subprocess
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from vulntrace.methods.callgraph import DEFAULT_LIMITS, run_vta_method
from vulntrace.methods.helper import DEFAULT_TIMEOUT_S
from vulntrace.methods.linker import run_linker_method
from vulntrace.verdict import symbol_verdict

# (module_dir, main_package, targets) -> one MethodResult per target, in target order
MethodFn = Callable[[Path, str, list[dict[str, str]]], list[dict[str, Any]]]

LOAD_ERROR_CODES = frozenset({"LOAD_FAILED", "TYPE_ERRORS", "BUILD_FAILED"})
DEFAULT_BUILD_TIMEOUT_S = 600.0


def _timed_run(timeout: float, *args, **kwargs):
    return subprocess.run(*args, timeout=timeout, **kwargs)


def default_vta(timeout: float = DEFAULT_TIMEOUT_S, limits: dict[str, int] | None = None, binary=None) -> MethodFn:
    return partial(run_vta_method, timeout=timeout, limits=limits or DEFAULT_LIMITS, binary=binary)


def default_linker(timeout: float = DEFAULT_BUILD_TIMEOUT_S) -> MethodFn:
    def run(module_dir: Path, main: str, targets: list[dict[str, str]]) -> list[dict[str, Any]]:
        started = time.monotonic()
        try:
            return run_linker_method(module_dir, main, targets, runner=partial(_timed_run, timeout))
        except subprocess.TimeoutExpired:
            ms = int((time.monotonic() - started) * 1000)
            return [{"schema_version": "1.0", "method": "LINKER_PRESENCE", "target": dict(t), "main_package": main,
                     "result": "ERROR", "details": {"matched_binary_symbols": []},
                     "error": {"code": "TIMEOUT", "message": f"build or nm exceeded {timeout:g}s"},
                     "duration_ms": ms} for t in targets]
    return run


def _check(results: list[dict[str, Any]], targets: list[dict[str, str]], method: str) -> None:
    got = [(r["target"]["package"], r["target"]["symbol"]) for r in results]
    want = [(t["package"], t["symbol"]) for t in targets]
    if got != want:
        raise ValueError(f"{method} returned results for {got}, expected {want}")


def make_entry(symbol: dict[str, Any], main: str, vta: dict[str, Any], linker: dict[str, Any],
               evidence_level: str) -> dict[str, Any]:
    """One per_symbol entry (verdict schema) from the two MethodResults; rule table without the verifier."""
    result, code = symbol_verdict(vta["result"], linker["result"], None)
    errors = {m: r["error"]["code"] for m, r in (("CALLGRAPH_VTA", vta), ("LINKER_PRESENCE", linker)) if r["error"]}
    d = vta.get("details") or {}
    return {
        "target": {"package": symbol["package"], "symbol": symbol["symbol"]},
        "result": result, "reason_code": code,
        "methods": {"CALLGRAPH_VTA": vta["result"], "LINKER_PRESENCE": linker["result"]},
        "method_errors": errors,
        "verified_path": None,
        "main_package": main,
        "origin": symbol["origin"], "rank": symbol.get("rank"), "score": symbol.get("score"),
        "candidate_id": symbol.get("candidate_id"),
        "decides_verdict": bool(symbol.get("decides_verdict", True)),
        "evidence_level": evidence_level,
        "pre_verifier_result": result,
        "paths": list(d.get("paths") or []),
        "paths_omitted": d.get("paths_omitted"),
        "package_not_in_program": bool(d.get("package_not_in_program")),
        "linker_matched": list((linker.get("details") or {}).get("matched_binary_symbols") or []),
        "verifier_failures": [],
    }


def analyse(module_dir: Path, mains: list[str], symbols: list[dict[str, Any]], evidence_level: str,
            vta_fn: MethodFn, linker_fn: MethodFn) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(entries, facts). Entries are ordered by main package, then symbol order. `facts` holds,
    per main package, the toolchain the methods reported, their durations and load errors."""
    entries: list[dict[str, Any]] = []
    facts: dict[str, Any] = {"per_main": {}, "toolchain": {}}
    if not symbols:
        return entries, facts
    targets = [{"package": s["package"], "symbol": s["symbol"]} for s in symbols]
    for main in mains:
        t0 = time.monotonic()
        vta = vta_fn(module_dir, main, targets)
        t1 = time.monotonic()
        linker = linker_fn(module_dir, main, targets)
        t2 = time.monotonic()
        _check(vta, targets, "CALLGRAPH_VTA")
        _check(linker, targets, "LINKER_PRESENCE")
        for s, v, ln in zip(symbols, vta, linker):
            entries.append(make_entry(s, main, v, ln, evidence_level))
        codes = sorted({r["error"]["code"] for r in vta + linker if r["error"]})
        load_failed = any(r["error"] and r["error"]["code"] in LOAD_ERROR_CODES for r in vta) or \
            any(r["error"] and r["error"]["code"] in LOAD_ERROR_CODES for r in linker)
        first_err = next((r["error"]["message"].splitlines()[0][:300] for r in vta + linker
                          if r["error"] and r["error"]["message"]), None)
        facts["per_main"][main] = {"vta_seconds": round(t1 - t0, 2), "linker_seconds": round(t2 - t1, 2),
                                   "error_codes": codes, "load_failed": load_failed, "first_error": first_err}
        vd = (vta[0].get("details") or {}) if vta else {}
        ld = (linker[0].get("details") or {}) if linker else {}
        if vd.get("toolchain"):
            facts["toolchain"].setdefault("helper", vd["toolchain"])
        if ld.get("go_version") and ld["go_version"] != "unknown":
            facts["toolchain"].setdefault("linker", {"go_version": ld["go_version"], "goos": ld.get("goos"),
                                                     "goarch": ld.get("goarch"), "build_flags": ld.get("build_flags")})
    return entries, facts
