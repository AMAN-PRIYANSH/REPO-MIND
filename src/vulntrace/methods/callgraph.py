"""Call-graph reachability (VTA, CP2) through the Go helper's `reach` mode.

PATH_FOUND / NO_PATH / ERROR are method results, not verdicts. Every failure, on the helper
side or in Python (TIMEOUT, HELPER_MISSING, ...), becomes an ERROR result with its code.
"""

import time
from pathlib import Path
from typing import Any

from vulntrace.methods.helper import CONTRACT_VERSION, DEFAULT_TIMEOUT_S, HelperError, run_helper
from vulntrace.methods.linker import normalize_import_path

METHOD = "CALLGRAPH_VTA"
SCHEMA_VERSION = "1.0"
DEFAULT_LIMITS = {"max_paths_per_target": 3, "max_path_length": 40}


def build_request(mode: str, module_dir: Path, main_package: str, targets: list[dict[str, str]],
                  limits: dict[str, int] | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": mode,
        "module_dir": Path(module_dir).resolve().as_posix(),
        "main_packages": [normalize_import_path(main_package)],
        "targets": [{"package": t["package"], "symbol": t["symbol"]} for t in targets],
        "build": {"tags": list(tags or []), "goos": None, "goarch": None},
        "limits": dict(limits or DEFAULT_LIMITS),
    }


def _empty_details(toolchain=None, stats=None) -> dict[str, Any]:
    return {"path": None, "paths": [], "shortest_length": None, "paths_omitted": None,
            "matched_functions": [], "toolchain": toolchain, "stats": stats,
            "package_not_in_program": False}


def to_method_results(method: str, main_package: str, targets: list[dict[str, str]],
                      response: dict[str, Any] | None, error: HelperError | None,
                      duration_ms: int) -> list[dict[str, Any]]:
    """Map a helper response (or a Python-side failure) to one MethodResult per target."""

    def make(target, result, details, err):
        return {
            "schema_version": SCHEMA_VERSION, "method": method,
            "target": {"package": target["package"], "symbol": target["symbol"]},
            "main_package": main_package, "result": result, "details": details,
            "error": err, "duration_ms": duration_ms,
        }

    if error is None and response is not None and not response["ok"]:
        error = HelperError(response["error"]["code"], response["error"]["message"])
    if error is not None:
        return [make(t, "ERROR", _empty_details(), {"code": error.code, "message": error.message}) for t in targets]

    results = response["results"]
    if [r["target"] for r in results] != [{"package": t["package"], "symbol": t["symbol"]} for t in targets]:
        bad = {"code": "BAD_RESPONSE", "message": "helper results do not match the requested targets"}
        return [make(t, "ERROR", _empty_details(), bad) for t in targets]
    out = []
    for t, r in zip(targets, results):
        details = _empty_details(response["toolchain"], response["stats"])
        details.update(paths=r["paths"], path=r["paths"][0] if r["paths"] else None,
                       shortest_length=r["shortest_length"], paths_omitted=r["paths_omitted"],
                       matched_functions=r["matched_functions"],
                       package_not_in_program=r["package_not_in_program"])
        out.append(make(t, r["result"], details, r["error"]))
    return out


def run_callgraph(module_dir: Path, main_package: str, targets: list[dict[str, str]], *,
                  mode: str = "reach", method: str = METHOD, timeout: float = DEFAULT_TIMEOUT_S,
                  limits: dict[str, int] | None = None, binary: Path | None = None,
                  runner=None) -> list[dict[str, Any]]:
    started = time.monotonic()
    response, error = None, None
    try:
        request = build_request(mode, module_dir, main_package, targets, limits)
        response = run_helper(mode, request, binary=binary, timeout=timeout, runner=runner)
    except HelperError as exc:
        error = exc
    duration_ms = int((time.monotonic() - started) * 1000)
    return to_method_results(method, main_package, targets, response, error, duration_ms)


def run_vta_method(module_dir: Path, main_package: str, targets: list[dict[str, str]], **kwargs) -> list[dict[str, Any]]:
    """One CALLGRAPH_VTA MethodResult per target."""
    return run_callgraph(module_dir, main_package, targets, mode="reach", method=METHOD, **kwargs)
