"""Verdict rule (C5): combine VTA and linker presence per target symbol, then per case.

Implements the rule table in docs/architecture/SYSTEM_ARCHITECTURE.md exactly. The verifier
(C6) arrives in CP7; until then `verification.status` is NOT_RUN and the "verifier passes"
column is treated as not yet applicable, so PATH_FOUND + PRESENT gives REACHABLE.
"""

from datetime import datetime, timezone
from typing import Any

from vulntrace import __version__
from vulntrace.methods.helper import CONTRACT_VERSION

SCHEMA_VERSION = "1.0"
STATEMENT = "Reachability only. This verdict does not assess exploitability."

REACHABLE, NOT_REACHABLE, CANT_DETERMINE = "REACHABLE", "NOT_REACHABLE", "CANT_DETERMINE"

NO_TARGET_SYMBOLS = "NO_TARGET_SYMBOLS"
METHOD_DISAGREEMENT = "METHOD_DISAGREEMENT"
ANALYSIS_FAILED = "ANALYSIS_FAILED"
VERIFIER_REJECTED = "VERIFIER_REJECTED"

VTA_RESULTS = ("PATH_FOUND", "NO_PATH", "ERROR")
LINKER_RESULTS = ("PRESENT", "ABSENT", "ERROR")
VERIFIER_STATES = (None, "PASSED", "FAILED")  # None: not run / not applicable


def symbol_verdict(vta: str, linker: str, verifier: str | None = None) -> tuple[str, str | None]:
    """One row of the rule table: (result, reason_code)."""
    if vta not in VTA_RESULTS or linker not in LINKER_RESULTS or verifier not in VERIFIER_STATES:
        raise ValueError(f"unknown method results: vta={vta!r} linker={linker!r} verifier={verifier!r}")
    if vta == "ERROR" or linker == "ERROR":
        return CANT_DETERMINE, ANALYSIS_FAILED
    if vta == "PATH_FOUND" and linker == "PRESENT":
        if verifier == "FAILED":
            return CANT_DETERMINE, VERIFIER_REJECTED
        return REACHABLE, None
    if vta == "NO_PATH" and linker == "ABSENT":
        return NOT_REACHABLE, None
    # NO_PATH + PRESENT, or PATH_FOUND + ABSENT (the anomaly)
    return CANT_DETERMINE, METHOD_DISAGREEMENT


def case_verdict(symbol_results: list[tuple[str, str | None]]) -> tuple[str, list[str]]:
    """REACHABLE if any symbol is; NOT_REACHABLE only if all are; otherwise CANT_DETERMINE."""
    if not symbol_results:
        return CANT_DETERMINE, [NO_TARGET_SYMBOLS]
    results = [r for r, _ in symbol_results]
    if REACHABLE in results:
        return REACHABLE, []
    if all(r == NOT_REACHABLE for r in results):
        return NOT_REACHABLE, []
    return CANT_DETERMINE, sorted({code for r, code in symbol_results if r == CANT_DETERMINE and code})


def _key(target: dict[str, str]) -> tuple[str, str]:
    return target["package"], target["symbol"]


def build_verdict(case_id: str, target_app: dict[str, Any], targets: list[dict[str, str]],
                  vta_results: list[dict[str, Any]], linker_results: list[dict[str, Any]],
                  created_at: str | None = None) -> dict[str, Any]:
    """Verdict object (schemas/verdict.schema.json) from one MethodResult per target and method."""
    vta = {_key(r["target"]): r for r in vta_results}
    linker = {_key(r["target"]): r for r in linker_results}
    per_symbol, pairs = [], []
    for t in targets:
        v, ln = vta.get(_key(t)), linker.get(_key(t))
        if v is None or ln is None:
            raise ValueError(f"missing method result for target {t}")
        result, code = symbol_verdict(v["result"], ln["result"], None)
        pairs.append((result, code))
        errors = {m: r["error"]["code"] for m, r in (("CALLGRAPH_VTA", v), ("LINKER_PRESENCE", ln)) if r["error"]}
        per_symbol.append({
            "target": {"package": t["package"], "symbol": t["symbol"]},
            "result": result,
            "reason_code": code,
            "methods": {"CALLGRAPH_VTA": v["result"], "LINKER_PRESENCE": ln["result"]},
            "method_errors": errors,
            "verified_path": None,  # nothing is verified before CP7
        })
    verdict, reasons = case_verdict(pairs)
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "target_app": target_app,
        "verdict": verdict,
        "reason_codes": reasons,
        "per_symbol": per_symbol,
        "verification": {"status": "NOT_RUN", "checks_run": 0, "failures": []},
        "statement": STATEMENT,
        "provenance": {
            "pipeline_version": __version__,
            "helper_contract": CONTRACT_VERSION,
            "vulndb_commit": None,
            "created_at": created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
