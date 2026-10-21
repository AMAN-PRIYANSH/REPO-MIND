"""Score the linker-presence method on the synthetic reachability suite.

PRESENT is scored as a REACHABLE prediction and ABSENT as NOT_REACHABLE. This
mapping is for scoring only; it is not a verdict (verdicts start in CP2).
"""

import json
from pathlib import Path
from typing import Any

from vulntrace.methods.linker import METHOD, NO_INLINE_FLAGS, run_linker_method

SCHEMA_VERSION = "1.0"

AGREE = "AGREE"
FALSE_NOT_REACHABLE = "FALSE_NOT_REACHABLE"
FALSE_REACHABLE = "FALSE_REACHABLE"
ERROR = "ERROR"


def load_manifest(fixtures_dir: Path) -> dict:
    return json.loads((Path(fixtures_dir) / "manifest.json").read_text(encoding="utf-8"))


def predict(results: list[dict[str, Any]]) -> str:
    """Case-level prediction: any PRESENT -> REACHABLE; else any ERROR -> ERROR; else NOT_REACHABLE."""
    states = [r["result"] for r in results]
    if "PRESENT" in states:
        return "REACHABLE"
    if "ERROR" in states:
        return "ERROR"
    return "NOT_REACHABLE"


def outcome(truth: str, predicted: str) -> str:
    if predicted == "ERROR":
        return ERROR
    if predicted == truth:
        return AGREE
    return FALSE_NOT_REACHABLE if truth == "REACHABLE" else FALSE_REACHABLE


def _compact(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"symbol": r["target"]["symbol"], "result": r["result"],
         "matched_binary_symbols": r["details"]["matched_binary_symbols"],
         "error_code": (r["error"] or {}).get("code")}
        for r in results
    ]


def score_linker(fixtures_dir: Path, compare_inlining: bool = False, runner=None) -> dict[str, Any]:
    kwargs = {} if runner is None else {"runner": runner}
    manifest = load_manifest(fixtures_dir)
    cases, comparison = [], []
    for case in manifest["cases"]:
        res = run_linker_method(fixtures_dir, case["main_package"], case["targets"], NO_INLINE_FLAGS, **kwargs)
        pred = predict(res)
        cases.append({
            "id": case["id"], "category": case["category"], "truth": case["truth"],
            "predicted": pred, "outcome": outcome(case["truth"], pred), "method_results": res,
        })
        if compare_inlining:
            res_inl = run_linker_method(fixtures_dir, case["main_package"], case["targets"], None, **kwargs)
            comparison.append({
                "id": case["id"], "truth": case["truth"],
                "inlining_disabled": _compact(res), "inlining_enabled": _compact(res_inl),
            })
    counts = {
        "cases": len(cases),
        "agreements": sum(c["outcome"] == AGREE for c in cases),
        "false_not_reachable": sum(c["outcome"] == FALSE_NOT_REACHABLE for c in cases),
        "false_reachable": sum(c["outcome"] == FALSE_REACHABLE for c in cases),
        "errors": sum(c["outcome"] == ERROR for c in cases),
    }
    first = cases[0]["method_results"][0]["details"] if cases else {}
    report = {
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "scoring_note": "PRESENT scored as REACHABLE and ABSENT as NOT_REACHABLE, for scoring only; not a verdict.",
        "build_flags": NO_INLINE_FLAGS,
        "environment": {k: first.get(k) for k in ("go_version", "goos", "goarch")},
        "counts": counts,
        "cases": cases,
    }
    if compare_inlining:
        report["inlining_comparison"] = comparison
    return report


def strip_timing(report: Any) -> Any:
    """Copy of a report without duration fields (for determinism checks)."""
    if isinstance(report, dict):
        return {k: strip_timing(v) for k, v in report.items() if k != "duration_ms"}
    if isinstance(report, list):
        return [strip_timing(v) for v in report]
    return report


def render_markdown(report: dict[str, Any]) -> str:
    env, c = report["environment"], report["counts"]
    lines = [
        f"# Linker presence on the synthetic suite",
        "",
        f"Go `{env['go_version']}` {env['goos']}/{env['goarch']}; build flags `{' '.join(report['build_flags'])}`.",
        "",
        "| Case | Category | Truth | Linker result | Scored as | Outcome | Matched binary symbols |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        results = ",".join(r["result"] for r in case["method_results"])
        matched = "; ".join(s for r in case["method_results"] for s in r["details"]["matched_binary_symbols"]) or "-"
        lines.append(
            f"| {case['id']} | {case['category']} | {case['truth']} | {results} | "
            f"{case['predicted']} | {case['outcome']} | {matched} |"
        )
    lines += [
        "",
        f"Cases: {c['cases']}. Agreements: {c['agreements']}. False NOT_REACHABLE: {c['false_not_reachable']}. "
        f"False REACHABLE: {c['false_reachable']}. Errors: {c['errors']}.",
    ]
    if "inlining_comparison" in report:
        lines += ["", "## Inlining comparison", "",
                  "Only the inlining-disabled column is used for scoring.", "",
                  "| Case | Truth | Inlining disabled (`-gcflags=all=-l`) | Inlining enabled (default) |",
                  "|---|---|---|---|"]
        for row in report["inlining_comparison"]:
            off = ",".join(r["result"] for r in row["inlining_disabled"])
            on = ",".join(r["result"] for r in row["inlining_enabled"])
            lines.append(f"| {row['id']} | {row['truth']} | {off} | {on} |")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = out_dir / "linker_score.json", out_dir / "linker_score.md"
    jp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(render_markdown(report), encoding="utf-8")
    return jp, mp
