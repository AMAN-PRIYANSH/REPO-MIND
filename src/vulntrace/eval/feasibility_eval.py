"""CP9 evaluation of the path-feasibility filter on fixtures (truth by construction).

`python -m vulntrace eval feasibility --set fixtures` runs, with the same helper binary:

1. the 16 CP9 fixtures (fixtures/feasibility, TARGETS mode), with the filter on and off: every
   INFEASIBLE case must be downgraded (CANT_DETERMINE, PATHS_INFEASIBLE) and every feasible
   look-alike and out-of-scope case must stay REACHABLE;
2. the CP2/CP7 fixture evaluation (`eval triage --set fixtures`: 22 cases x 3 modes), once with the
   filter off and once on: the off run must reproduce the committed CP7 results
   (`docs/results/cp7/fixtures.json`) exactly, apart from timings; every verdict the filter changes
   in the on run is listed (a change of a truly REACHABLE case is a false downgrade).

Nothing here judges D3 or D3b; see `feasibility_real`.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from vulntrace.eval import triage_eval as te
from vulntrace.paths import FEASIBILITY_FIXTURES_DIR, REPO_ROOT
from vulntrace.pipeline import feasibility as fz, triage
from vulntrace.verdict import CANT_DETERMINE, PATHS_INFEASIBLE, REACHABLE

SCHEMA_VERSION = "1.0"
CP7_FIXTURES = REPO_ROOT / "docs" / "results" / "cp7" / "fixtures.json"
VOLATILE_ROW_KEYS = ("seconds",)


def _cp9_row(case: dict[str, Any], off: dict[str, Any], on: dict[str, Any]) -> dict[str, Any]:
    e_on = on["per_symbol"][0] if on["per_symbol"] else {}
    f = e_on.get("feasibility") or {}
    expected_verdict = (CANT_DETERMINE if case["expected_filter"] == fz.INFEASIBLE else REACHABLE)
    row = {
        "id": case["id"], "pattern": case["pattern"], "kind": case["kind"], "truth": case["truth"],
        "expected_filter": case["expected_filter"],
        "verdict_off": off["verdict"], "verdict_on": on["verdict"], "reason_codes_on": on["reason_codes"],
        "filter_status": f.get("status"), "deciding_pattern": fz.deciding_pattern(e_on),
        "first_patterns": fz.first_patterns(e_on), "examined": len(f.get("examined") or []),
        "evidence_source": f.get("evidence_source"), "undecided_reason": f.get("undecided_reason"),
        "verification_on": on["verification"]["status"],
        "verified_path_is_evidence": bool(e_on.get("verified_path")) and e_on.get("verified_path") == f.get("evidence_path"),
        "infeasible_steps": [{"pattern": ex["first_infeasible"]["pattern"], "reason": ex["first_infeasible"]["reason"],
                              "site": ex["first_infeasible"]["edge"]["call_site"]}
                             for ex in (f.get("examined") or []) if ex.get("first_infeasible")][:3],
        "seconds_on": (on.get("timing") or {}).get("total_seconds"),
    }
    row["as_expected"] = (row["filter_status"] == case["expected_filter"] and on["verdict"] == expected_verdict
                          and off["verdict"] == REACHABLE
                          and (on["verdict"] != CANT_DETERMINE or on["reason_codes"] == [PATHS_INFEASIBLE]))
    row["false_downgrade"] = case["truth"] == REACHABLE and on["verdict"] != off["verdict"]
    return row


def eval_cp9_fixtures(factory_off: Callable[[], triage.Runners], factory_on: Callable[[], triage.Runners],
                      log=print) -> dict[str, Any]:
    manifest = json.loads((FEASIBILITY_FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    off_r, on_r = te.memo_runners(factory_off()), te.memo_runners(factory_on())
    rows = []
    for case in manifest["cases"]:
        reqs = [triage.TriageRequest(case_id=f"cp9:{case['id']}", app=FEASIBILITY_FIXTURES_DIR, mode="targets",
                                     targets=case["targets"], mains=[case["main_package"]], max_mains=1) for _ in (0, 1)]
        off, on = triage.run_triage(reqs[0], off_r), triage.run_triage(reqs[1], on_r)
        row = _cp9_row(case, off, on)
        row["schema_errors_on"] = te._check_schema(on)[:3]
        rows.append(row)
        log(f"cp9 fixture {case['id']:<28} truth={case['truth']:<14} off={off['verdict']:<14} on={on['verdict']:<14} "
            f"filter={row['filter_status']} pattern={row['deciding_pattern']} ok={row['as_expected']}")
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows:
        k = by_kind.setdefault(r["kind"], Counter())
        k["cases"] += 1
        k["downgraded"] += int(r["verdict_on"] == CANT_DETERMINE and r["reason_codes_on"] == [PATHS_INFEASIBLE])
        k["as_expected"] += int(r["as_expected"])
    per_pattern = {p: {"infeasible_cases": sum(1 for r in rows if r["pattern"] == p and r["kind"] == "INFEASIBLE"),
                       "downgraded": sum(1 for r in rows if r["pattern"] == p and r["kind"] == "INFEASIBLE"
                                         and r["verdict_on"] == CANT_DETERMINE),
                       "lookalikes": sum(1 for r in rows if r["pattern"] == p and r["kind"] == "FEASIBLE_LOOKALIKE"),
                       "lookalikes_downgraded": sum(1 for r in rows if r["pattern"] == p and r["kind"] == "FEASIBLE_LOOKALIKE"
                                                    and r["verdict_on"] != REACHABLE)}
                   for p in fz.PATTERNS}
    return {"rows": rows, "by_kind": {k: dict(v) for k, v in sorted(by_kind.items())}, "per_pattern": per_pattern,
            "false_downgrades": [r["id"] for r in rows if r["false_downgrade"]],
            "not_as_expected": [r["id"] for r in rows if not r["as_expected"]],
            "method_calls": {"vta": off_r.vta.calls + on_r.vta.calls}}


def _strip(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in VOLATILE_ROW_KEYS}


def compare_cp7(off_doc: dict[str, Any], committed: dict[str, Any]) -> dict[str, Any]:
    """Row-by-row comparison of a filter-off fixture run with the committed CP7 results (timings and
    the run environment excluded; everything else must be equal)."""
    a, b = off_doc["rows"], committed["rows"]
    diffs = []
    for i, (x, y) in enumerate(zip(a, b)):
        sx, sy = _strip(x), _strip(y)
        if sx != sy:
            keys = sorted(k for k in set(sx) | set(sy) if sx.get(k) != sy.get(k))
            diffs.append({"row": i, "id": x.get("id"), "mode": x.get("mode"), "keys": keys})
    probe_equal = off_doc["corruption_probe"] == committed["corruption_probe"]
    summary_equal = all(
        {k: v for k, v in off_doc["summary"][m].items() if k != "seconds"} ==
        {k: v for k, v in committed["summary"][m].items() if k != "seconds"} for m in committed["summary"])
    return {"rows_compared": min(len(a), len(b)), "row_count_equal": len(a) == len(b), "differences": diffs,
            "corruption_probe_equal": probe_equal, "summary_equal_except_seconds": summary_equal,
            "stability_equal": off_doc["stability"]["unstable"] == committed["stability"]["unstable"],
            "committed_environment": committed.get("environment"),
            "identical": len(a) == len(b) and not diffs and probe_equal and summary_equal}


def old_fixture_changes(off_doc: dict[str, Any], on_doc: dict[str, Any]) -> dict[str, Any]:
    """What the filter changed on the CP2/CP7 fixtures (all modes)."""
    changes = []
    for x, y in zip(off_doc["rows"], on_doc["rows"]):
        if (x["verdict"], x["reason_codes"]) != (y["verdict"], y["reason_codes"]):
            changes.append({"id": x["id"], "mode": x["mode"], "truth": x["truth"], "off": x["verdict"], "on": y["verdict"],
                            "reason_codes_on": y["reason_codes"]})
    reachable_truth_rows = [x for x in off_doc["rows"] if x["truth"] == REACHABLE and x["verdict"] == REACHABLE]
    return {"rows": len(off_doc["rows"]), "changed": changes,
            "false_downgrades": [c for c in changes if c["truth"] == REACHABLE],
            "true_reachable_rows_checked": len(reachable_truth_rows),
            "on_summary": {m: on_doc["summary"][m]["final"] for m in on_doc["summary"]}}


def eval_all_fixtures(factory_off, factory_on, work_dir: Path, binary, log=print) -> dict[str, Any]:
    cp9 = eval_cp9_fixtures(factory_off, factory_on, log=log)
    log("CP2/CP7 fixtures, filter off (reproduction of the committed CP7 results)")
    off_doc = te.eval_fixtures(factory_off, work_dir / "off", binary, log=log)
    log("CP2/CP7 fixtures, filter on")
    on_doc = te.eval_fixtures(factory_on, work_dir / "on", binary, log=log)
    committed = json.loads(CP7_FIXTURES.read_text(encoding="utf-8"))
    return {"schema_version": SCHEMA_VERSION, "set": "fixtures", "cp9_fixtures": cp9,
            "cp7_reproduction": compare_cp7(off_doc, committed),
            "cp7_fixtures_with_filter": old_fixture_changes(off_doc, on_doc)}
