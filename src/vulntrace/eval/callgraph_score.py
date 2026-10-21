"""Score VTA (R3), the naive control (R1) and the combined verdict (R4) on the synthetic suite.

For single methods, PATH_FOUND is scored as a REACHABLE prediction and NO_PATH as
NOT_REACHABLE, for scoring only. The combined method produces real Verdict objects.
"""

from pathlib import Path
from typing import Any

from vulntrace.eval.fixture_score import AGREE, ERROR, FALSE_NOT_REACHABLE, FALSE_REACHABLE, load_manifest
from vulntrace.methods.callgraph import METHOD as VTA_METHOD
from vulntrace.methods.callgraph import run_vta_method
from vulntrace.methods.helper import DEFAULT_TIMEOUT_S
from vulntrace.methods.linker import METHOD as LINKER_METHOD
from vulntrace.methods.linker import NO_INLINE_FLAGS, run_linker_method
from vulntrace.methods.naive import METHOD as NAIVE_METHOD
from vulntrace.methods.naive import run_naive_method
from vulntrace.verdict import CANT_DETERMINE, build_verdict

SCHEMA_VERSION = "1.0"
COMBINED = "COMBINED"


def predict_callgraph(results: list[dict[str, Any]]) -> str:
    """Case-level prediction: any PATH_FOUND -> REACHABLE; else any ERROR -> ERROR; else NOT_REACHABLE."""
    states = [r["result"] for r in results]
    if "PATH_FOUND" in states:
        return "REACHABLE"
    if "ERROR" in states:
        return "ERROR"
    return "NOT_REACHABLE"


def outcome(truth: str, predicted: str) -> str:
    if predicted == "ERROR":
        return ERROR
    if predicted == CANT_DETERMINE:
        return CANT_DETERMINE
    if predicted == truth:
        return AGREE
    return FALSE_NOT_REACHABLE if truth == "REACHABLE" else FALSE_REACHABLE



def counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cases": len(cases),
        "agreements": sum(c["outcome"] == AGREE for c in cases),
        "false_not_reachable": sum(c["outcome"] == FALSE_NOT_REACHABLE for c in cases),
        "false_reachable": sum(c["outcome"] == FALSE_REACHABLE for c in cases),
        "cant_determine": sum(c["outcome"] == CANT_DETERMINE for c in cases),
        "errors": sum(c["outcome"] == ERROR for c in cases),
    }


def _environment(method_results: list[dict[str, Any]]) -> dict[str, Any]:
    for r in method_results:
        tc = r["details"].get("toolchain")
        if tc:
            return dict(tc)
    return {"go_version": None, "goos": None, "goarch": None, "x_tools_version": None}


def score_callgraph(fixtures_dir: Path, method: str, binary: Path | None = None,
                    timeout: float = DEFAULT_TIMEOUT_S, runner=None) -> dict[str, Any]:
    """method: CALLGRAPH_VTA or CALLGRAPH_NAIVE."""
    run = {VTA_METHOD: run_vta_method, NAIVE_METHOD: run_naive_method}[method]
    kwargs = {"binary": binary, "timeout": timeout, **({"runner": runner} if runner else {})}
    cases, all_results = [], []
    for case in load_manifest(fixtures_dir)["cases"]:
        res = run(fixtures_dir, case["main_package"], case["targets"], **kwargs)
        all_results += res
        pred = predict_callgraph(res)
        cases.append({"id": case["id"], "category": case["category"], "truth": case["truth"],
                      "predicted": pred, "outcome": outcome(case["truth"], pred), "method_results": res})
    return {
        "schema_version": SCHEMA_VERSION,
        "method": method,
        "scoring_note": "PATH_FOUND scored as REACHABLE and NO_PATH as NOT_REACHABLE, for scoring only; not a verdict.",
        "environment": _environment(all_results),
        "counts": counts(cases),
        "cases": cases,
    }


def score_combined(fixtures_dir: Path, binary: Path | None = None, timeout: float = DEFAULT_TIMEOUT_S,
                   vta_runner=None, linker_runner=None, created_at: str | None = None) -> dict[str, Any]:
    """Verdict rule over VTA + linker presence (R4)."""
    vkw = {"binary": binary, "timeout": timeout, **({"runner": vta_runner} if vta_runner else {})}
    lkw = {"runner": linker_runner} if linker_runner else {}
    manifest = load_manifest(fixtures_dir)
    module = _module_name(fixtures_dir)
    cases, all_vta = [], []
    for case in manifest["cases"]:
        vta = run_vta_method(fixtures_dir, case["main_package"], case["targets"], **vkw)
        linker = run_linker_method(fixtures_dir, case["main_package"], case["targets"], NO_INLINE_FLAGS, **lkw)
        all_vta += vta
        app = {"path": manifest["module_dir"], "module": module, "commit": None, "main_package": case["main_package"]}
        verdict = build_verdict(case["id"], app, case["targets"], vta, linker, created_at=created_at)
        cases.append({"id": case["id"], "category": case["category"], "truth": case["truth"],
                      "predicted": verdict["verdict"], "outcome": outcome(case["truth"], verdict["verdict"]),
                      "reason_codes": verdict["reason_codes"], "verdict": verdict,
                      "method_results": {VTA_METHOD: vta, LINKER_METHOD: linker}})
    c = counts(cases)
    by_reason: dict[str, int] = {}
    for case in cases:
        for code in case["reason_codes"]:
            by_reason[code] = by_reason.get(code, 0) + 1
    c["cant_determine_by_reason"] = dict(sorted(by_reason.items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "method": COMBINED,
        "scoring_note": ("Verdict rule (SYSTEM_ARCHITECTURE.md) over CALLGRAPH_VTA and LINKER_PRESENCE "
                         f"(build flags {' '.join(NO_INLINE_FLAGS)}). Verifier not run in CP2 (verification NOT_RUN)."),
        "environment": _environment(all_vta),
        "counts": c,
        "confusion": confusion(cases),
        "cases": cases,
    }


def confusion(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """truth -> output -> count (3x3 without the impossible CANT_DETERMINE truth row)."""
    out = {t: {o: 0 for o in ("REACHABLE", "NOT_REACHABLE", CANT_DETERMINE)} for t in ("REACHABLE", "NOT_REACHABLE")}
    for c in cases:
        out[c["truth"]][c["predicted"]] += 1
    return out


def _module_name(fixtures_dir: Path) -> str | None:
    gomod = Path(fixtures_dir) / "go.mod"
    if not gomod.is_file():
        return None
    for line in gomod.read_text(encoding="utf-8").splitlines():
        if line.startswith("module "):
            return line.split()[1]
    return None


def _results_cell(results: list[dict[str, Any]]) -> str:
    return ",".join(r["result"] + (f" ({r['error']['code']})" if r["error"] else "") for r in results)


def render_markdown(report: dict[str, Any]) -> str:
    c, env = report["counts"], report["environment"]
    lines = [f"# {report['method']} on the synthetic suite", "",
             f"Go `{env.get('go_version')}` {env.get('goos')}/{env.get('goarch')}, "
             f"x/tools `{env.get('x_tools_version')}`. {report['scoring_note']}", ""]
    if report["method"] == COMBINED:
        lines += ["| Case | Category | Truth | VTA | Linker | Verdict | Reason codes | Outcome |",
                  "|---|---|---|---|---|---|---|---|"]
        for case in report["cases"]:
            mr = case["method_results"]
            lines.append(f"| {case['id']} | {case['category']} | {case['truth']} | {_results_cell(mr[VTA_METHOD])} | "
                         f"{_results_cell(mr[LINKER_METHOD])} | {case['predicted']} | "
                         f"{', '.join(case['reason_codes']) or '-'} | {case['outcome']} |")
    else:
        lines += ["| Case | Category | Truth | Result | Scored as | Outcome |", "|---|---|---|---|---|---|"]
        for case in report["cases"]:
            lines.append(f"| {case['id']} | {case['category']} | {case['truth']} | {_results_cell(case['method_results'])} | "
                         f"{case['predicted']} | {case['outcome']} |")
    lines += ["", f"Cases: {c['cases']}. False NOT_REACHABLE: {c['false_not_reachable']}. "
                  f"False REACHABLE: {c['false_reachable']}. Agreements: {c['agreements']}. "
                  f"CANT_DETERMINE: {c['cant_determine']}. Errors: {c['errors']}."]
    return "\n".join(lines) + "\n"


STEMS = {VTA_METHOD: "vta_score", NAIVE_METHOD: "naive_score", COMBINED: "combined_score"}


def write_score(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    import json

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = STEMS[report["method"]]
    jp, mp = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(render_markdown(report), encoding="utf-8")
    return jp, mp
