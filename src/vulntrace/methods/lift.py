"""Lifting and caller/callee queries (CP5b) through the Go helper's `lift`, `callers` and
`callees` modes.

`lift` walks callers upward from a seed to exported entry points under two stopping rules
(`NEAREST`, `ALL`; open question Q4). `callers` / `callees` are read-only call-graph queries for
the CP6 agent. Every failure, helper-side or Python-side (TIMEOUT, HELPER_MISSING, LOAD_FAILED),
becomes a per-target ERROR record with its code, so a module that cannot be loaded is counted
and reported, never dropped.
"""

import time
from pathlib import Path
from typing import Any

from vulntrace.methods.helper import CONTRACT_VERSION, DEFAULT_TIMEOUT_S, HelperError, run_helper
from vulntrace.methods.linker import normalize_import_path

LIFT_METHOD = "LIFT_VTA"
NEIGHBOR_METHOD = "CALLGRAPH_NEIGHBORS"
SCHEMA_VERSION = "1.0"
RULES = ("NEAREST", "ALL")
DEFAULT_MAX_LIFT_DEPTH = 10

# Lift statuses (helper) plus the Python-side view of a failed helper run.
STATUS_LIFTED, STATUS_ALREADY, STATUS_ROOT_ONLY = "LIFTED", "ALREADY_EXPORTED", "ROOT_ONLY"
STATUS_NOT_IN_PROGRAM, STATUS_ERROR = "PACKAGE_NOT_IN_PROGRAM", "ERROR"
LIFT_OK_STATUSES = (STATUS_LIFTED, STATUS_ALREADY)


def build_query_request(mode: str, module_dir: Path, targets: list[dict[str, str]], *,
                        packages: list[str] | None = None, main_packages: list[str] | None = None,
                        rules: list[str] | None = None, limits: dict[str, int] | None = None,
                        external: bool = False, tags: list[str] | None = None) -> dict[str, Any]:
    """A lift / callers / callees request. Without `main_packages` the module is loaded as a
    library (`packages`, default ./...); with them, as an application (roots are main and init)."""
    req: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION, "mode": mode,
        "module_dir": Path(module_dir).resolve().as_posix(),
        "targets": [{"package": t["package"], "symbol": t["symbol"]} for t in targets],
        "build": {"tags": list(tags or []), "goos": None, "goarch": None},
        "limits": dict(limits or {}),
    }
    if main_packages:
        req["main_packages"] = [normalize_import_path(p) for p in main_packages]
    if packages:
        req["packages"] = list(packages)
    if mode == "lift":
        req["lift_rules"] = list(rules or RULES)
        req["limits"].setdefault("max_lift_depth", DEFAULT_MAX_LIFT_DEPTH)
    if mode in ("callers", "callees") and external:
        req["external"] = True
    return req


def _error_record(method: str, target: dict[str, str], err: dict[str, str], duration_ms: int, status_key: str,
                  status: str, extra: dict[str, Any]) -> dict[str, Any]:
    rec = {"schema_version": SCHEMA_VERSION, "method": method,
           "target": {"package": target["package"], "symbol": target["symbol"]},
           status_key: status, "error": err, "duration_ms": duration_ms,
           "details": {"toolchain": None, "stats": None, "load": None, "matched_functions": []}}
    rec.update(extra)
    return rec


def to_lift_records(targets: list[dict[str, str]], response: dict[str, Any] | None, error: HelperError | None,
                    duration_ms: int) -> list[dict[str, Any]]:
    """One record per seed: status, the NEAREST and ALL entry lists, and the error if any."""
    if error is None and response is not None and not response["ok"]:
        error = HelperError(response["error"]["code"], response["error"]["message"])
    if error is not None:
        return [_error_record(LIFT_METHOD, t, {"code": error.code, "message": error.message}, duration_ms,
                              "status", STATUS_ERROR, {"rules": {}}) for t in targets]
    results = response["results"]
    if [r["target"] for r in results] != [{"package": t["package"], "symbol": t["symbol"]} for t in targets]:
        bad = {"code": "BAD_RESPONSE", "message": "helper results do not match the requested seeds"}
        return [_error_record(LIFT_METHOD, t, bad, duration_ms, "status", STATUS_ERROR, {"rules": {}})
                for t in targets]
    out = []
    for r in results:
        out.append({
            "schema_version": SCHEMA_VERSION, "method": LIFT_METHOD, "target": r["target"], "status": r["status"],
            "rules": r["rules"], "error": r["error"], "duration_ms": duration_ms,
            "details": {"toolchain": response["toolchain"], "stats": response["stats"],
                        "load": response.get("load"), "matched_functions": r["matched_functions"],
                        "package_not_in_program": r["package_not_in_program"]},
        })
    return out


def to_neighbor_records(mode: str, targets: list[dict[str, str]], response: dict[str, Any] | None,
                        error: HelperError | None, duration_ms: int) -> list[dict[str, Any]]:
    if error is None and response is not None and not response["ok"]:
        error = HelperError(response["error"]["code"], response["error"]["message"])
    extra = {"query": mode, "edges": [], "truncated": False}
    if error is not None:
        return [_error_record(NEIGHBOR_METHOD, t, {"code": error.code, "message": error.message}, duration_ms,
                              "result", "ERROR", dict(extra)) for t in targets]
    results = response["results"]
    if [r["target"] for r in results] != [{"package": t["package"], "symbol": t["symbol"]} for t in targets]:
        bad = {"code": "BAD_RESPONSE", "message": "helper results do not match the requested targets"}
        return [_error_record(NEIGHBOR_METHOD, t, bad, duration_ms, "result", "ERROR", dict(extra)) for t in targets]
    return [{
        "schema_version": SCHEMA_VERSION, "method": NEIGHBOR_METHOD, "query": mode, "target": r["target"],
        "result": r["result"], "edges": r["edges"], "truncated": r["truncated"], "error": r["error"],
        "duration_ms": duration_ms,
        "details": {"toolchain": response["toolchain"], "stats": response["stats"], "load": response.get("load"),
                    "matched_functions": r["matched_functions"],
                    "package_not_in_program": r["package_not_in_program"]},
    } for r in results]


def _run(mode: str, request: dict[str, Any], timeout: float, binary: Path | None, runner) -> tuple[Any, Any, int]:
    started = time.monotonic()
    response, error = None, None
    try:
        response = run_helper(mode, request, binary=binary, timeout=timeout, runner=runner)
    except HelperError as exc:
        error = exc
    return response, error, int((time.monotonic() - started) * 1000)


def run_lift(module_dir: Path, targets: list[dict[str, str]], *, packages: list[str] | None = None,
             main_packages: list[str] | None = None, rules: list[str] | None = None,
             limits: dict[str, int] | None = None, timeout: float = DEFAULT_TIMEOUT_S,
             binary: Path | None = None, runner=None) -> list[dict[str, Any]]:
    request = build_query_request("lift", module_dir, targets, packages=packages, main_packages=main_packages,
                                  rules=rules, limits=limits)
    response, error, ms = _run("lift", request, timeout, binary, runner)
    return to_lift_records(targets, response, error, ms)


def run_neighbors(mode: str, module_dir: Path, targets: list[dict[str, str]], *, hops: int = 1,
                  max_results: int = 200, packages: list[str] | None = None,
                  main_packages: list[str] | None = None, external: bool = False,
                  timeout: float = DEFAULT_TIMEOUT_S, binary: Path | None = None,
                  runner=None) -> list[dict[str, Any]]:
    if mode not in ("callers", "callees"):
        raise ValueError(f"mode must be 'callers' or 'callees', got {mode!r}")
    request = build_query_request(mode, module_dir, targets, packages=packages, main_packages=main_packages,
                                  limits={"max_hops": hops, "max_results": max_results}, external=external)
    response, error, ms = _run(mode, request, timeout, binary, runner)
    return to_neighbor_records(mode, targets, response, error, ms)


def run_callers(module_dir: Path, targets: list[dict[str, str]], **kwargs) -> list[dict[str, Any]]:
    return run_neighbors("callers", module_dir, targets, **kwargs)


def run_callees(module_dir: Path, targets: list[dict[str, str]], **kwargs) -> list[dict[str, Any]]:
    return run_neighbors("callees", module_dir, targets, **kwargs)


def lifted_symbols(record: dict[str, Any], rule: str) -> set[str]:
    """The set of lifted entry-point symbols a record holds for one rule (empty on failure)."""
    return {e["symbol"] for e in record.get("rules", {}).get(rule, {}).get("entries", [])}
