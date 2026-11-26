"""`python -m vulntrace cp10 run --set fixtures|d3|d3b|d3c` (CP10 deliverables 1 and 3).

D3 / D3b / D3c: the CP7b runner (`d3.triage_run.eval_d3`) runs every case twice with the same inputs
and the CP10 pipeline (filter on, N = 20 examined paths, evidence stage on): once with the CP10 target
hygiene and once with `--legacy-targets`. The two runs share the application trees and the evidence
(`<data>/shared`) and keep separate outputs (`<data>/hygiene`, `<data>/legacy`). govulncheck (source
mode, `-scan symbol`, the main packages as roots, `GOPROXY=off`, the pinned vulndb snapshot) runs in
both; it is a reference, never truth. For D3 and D3b the legacy run is compared with the committed
CP9 verdicts (filter on) after removing CP10's additive evidence keys: acceptance criterion 1.

Fixtures: the CP7 fixture suite with the legacy targets and the filter off (the CP7 pipeline plus
the CP10 evidence stage) is compared row by row with the committed CP7 results, and the suite is run
again with the hygiene targets (truth known by construction).

Committed: one compact file per set (`<set>_verdicts.json`, a row per case with both verdicts, the
stratum, what hygiene changed, govulncheck's answer at its level, the shown route's evidence level)
and the full verdicts of both runs (`verdicts_hygiene/`, `verdicts_legacy/`), local paths rewritten.
"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from vulntrace.d3 import govuln
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import evidence as ev
from vulntrace.pipeline import symbols as sy
from vulntrace.verdict import CANT_DETERMINE, NOT_REACHABLE, REACHABLE

SCHEMA_VERSION = "1.0"
RESULTS = REPO_ROOT / "docs" / "results" / "cp10"
CP9 = REPO_ROOT / "docs" / "results" / "cp9"
CP7B = REPO_ROOT / "docs" / "results" / "cp7b"
POLICIES = ((sy.POLICY_HYGIENE, "hygiene"), (sy.POLICY_LEGACY, "legacy"))
IN_SAMPLE = {"d3": "IN-SAMPLE for CP10: the target-hygiene rules were written after reading the CP7b adjudication "
                   "of these D3 cases.",
             "d3b": "IN-SAMPLE for CP10: the target-hygiene rules were written after reading the CP9 adjudication "
                    "of these D3b cases."}


def case_paths(set_name: str) -> Path:
    return {"d3": CP7B / "d3_cases.json", "d3b": CP9 / "d3b" / "d3_cases.json",
            "d3c": RESULTS / "d3c" / "d3c_cases.json"}[set_name]


def committed_cp9_verdicts(set_name: str) -> Path | None:
    return {"d3": CP9 / "d3" / "verdicts_on", "d3b": CP9 / "d3b" / "verdicts_on"}.get(set_name)


# --- per case --------------------------------------------------------------------------------------
def stratum_for(case: dict[str, Any], vcase: dict[str, Any] | None) -> str | None:
    if case.get("stratum"):
        return case["stratum"]
    if vcase is None:
        return None
    return sy.stratum_of(vcase, case["module"])


def deciding_reachable(v: dict[str, Any] | None) -> list[str]:
    if not v:
        return []
    return sorted({f"{e['target']['package']}.{e['target']['symbol']}" for e in v["per_symbol"]
                   if e["result"] == REACHABLE and e.get("decides_verdict", True)})


def govulncheck_view(g: dict[str, Any] | None, stratum: str | None) -> dict[str, Any] | None:
    """govulncheck's answer at its own level, and the claim it is scored as (CP10 deliverable 5):
    stratum S: REACHABLE only at symbol level (the advisory's curated symbols are called);
    stratum N: any finding (symbol, package or module level) is its REACHABLE claim, because
    without curated symbols "package imported" or "module required" is all it can say."""
    if not g:
        return None
    level, verdict = g.get("level"), g.get("verdict")
    if verdict == govuln.ERROR:
        claim = None
    elif stratum == sy.STRATUM_N:
        claim = REACHABLE if level in (govuln.LEVEL_SYMBOL, govuln.LEVEL_PACKAGE, govuln.LEVEL_MODULE) else NOT_REACHABLE
    else:
        claim = REACHABLE if level == govuln.LEVEL_SYMBOL else NOT_REACHABLE
    return {"verdict": verdict, "level": level, "claim": claim, "symbols": g.get("symbols") or [],
            "trace": g.get("trace"), "error": g.get("error"), "fixed_version": g.get("fixed_version"),
            "not_affected": verdict == govuln.NOT_AFFECTED}


def case_row(case: dict[str, Any], vcase: dict[str, Any] | None, hyg_row: dict[str, Any] | None,
             leg_row: dict[str, Any] | None, hyg: dict[str, Any] | None, leg: dict[str, Any] | None) -> dict[str, Any]:
    st = stratum_for(case, vcase)
    pe = (hyg or {}).get("path_evidence") or {}
    tp = (hyg or {}).get("target_policy") or {}
    row = {"id": case["id"], "app_repo": case["app_repo"], "app_tag": case["app_tag"], "advisory": case["advisory"],
           "module": case["module"], "version_selected": case.get("version_selected"), "stratum": st,
           "review_status": (vcase or {}).get("review_status"), "cluster_key": case["app_repo"],
           "mode": (hyg or {}).get("mode"),
           "hygiene": {"verdict": (hyg or {}).get("verdict"), "reason_codes": (hyg or {}).get("reason_codes"),
                       "deciding_reachable": deciding_reachable(hyg), "target_policy": tp or None,
                       "evidence_level": pe.get("evidence_level"), "dynamic_steps": pe.get("dynamic_steps"),
                       "dynamic_kinds": pe.get("dynamic_kinds"), "route_passes_filter": pe.get("passes_filter")},
           "legacy": {"verdict": (leg or {}).get("verdict"), "reason_codes": (leg or {}).get("reason_codes"),
                      "deciding_reachable": deciding_reachable(leg)},
           "govulncheck": govulncheck_view((hyg_row or {}).get("govulncheck"), st),
           "govulncheck_legacy_run": govulncheck_view((leg_row or {}).get("govulncheck"), st),
           "harness_error": (hyg_row or {}).get("harness_error") or (hyg_row or {}).get("app_prep_error")}
    h, lg = row["hygiene"]["verdict"], row["legacy"]["verdict"]
    row["hygiene_changed"] = h is not None and lg is not None and (h, row["hygiene"]["reason_codes"]) != \
        (lg, row["legacy"]["reason_codes"])
    row["hygiene_made_not_reachable"] = h == NOT_REACHABLE and lg != NOT_REACHABLE
    return row


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def by(rs, key):
        return dict(Counter(key(r) for r in rs))
    out: dict[str, Any] = {"cases": len(rows), "by_stratum": by(rows, lambda r: r["stratum"])}
    for st in ("S", "N", "ALL"):
        rs = [r for r in rows if st == "ALL" or r["stratum"] == st]
        out[st] = {"cases": len(rs),
                   "hygiene": by(rs, lambda r: r["hygiene"]["verdict"]), "legacy": by(rs, lambda r: r["legacy"]["verdict"]),
                   "govulncheck_claim": by(rs, lambda r: (r["govulncheck"] or {}).get("claim")),
                   "govulncheck_level": by(rs, lambda r: (r["govulncheck"] or {}).get("level")),
                   "hygiene_changed": [r["id"] for r in rs if r["hygiene_changed"]],
                   "hygiene_made_not_reachable": [r["id"] for r in rs if r["hygiene_made_not_reachable"]],
                   "evidence_levels": by([r for r in rs if r["hygiene"]["verdict"] == REACHABLE],
                                         lambda r: r["hygiene"]["evidence_level"])}
    out["govulncheck_runs_agree"] = all(r["govulncheck"] == r["govulncheck_legacy_run"] for r in rows)
    return out


def stable(v: dict[str, Any]) -> Any:
    """What a reproduction must keep (CP9's `feasibility_real.stable`, with the verification status):
    verdict, reasons, and per entry the main package, target, result, reason, method results and
    verified path, after CP10's additive evidence keys are removed."""
    v = ev.strip_cp10_evidence(v)
    return [v["verdict"], v["reason_codes"], (v.get("verification") or {}).get("status"),
            [[e.get("main_package"), e["target"], e["result"], e["reason_code"], e["methods"], e.get("verified_path")]
             for e in v["per_symbol"]]]


def reproduce_cp9(set_name: str, legacy: dict[str, dict[str, Any]], sanitise=lambda v: v) -> dict[str, Any] | None:
    """`legacy`: this run's legacy verdicts; `sanitise` rewrites their local paths exactly as the
    committed copies were rewritten (`d3.triage_run.sanitise`), so module-cache files compare equal."""
    from vulntrace.eval.feasibility_real import read_verdicts

    d = committed_cp9_verdicts(set_name)
    if d is None:
        return None
    committed = read_verdicts(d)
    out: dict[str, Any] = {"against": str(d.relative_to(REPO_ROOT)), "compared": 0, "identical": [], "different": [],
                           "missing": []}
    for cid, cv in sorted(committed.items()):
        if cid not in legacy:
            out["missing"].append(cid)
            continue
        out["compared"] += 1
        a, b = stable(sanitise(legacy[cid])), stable(cv)
        if a == b:
            out["identical"].append(cid)
        else:
            out["different"].append({"id": cid, "legacy": a[:3], "cp9": b[:3], "entries_differ": a[3] != b[3]})
    out["all_identical"] = not out["different"] and not out["missing"] and out["compared"] > 0
    return out


# --- the run ---------------------------------------------------------------------------------------
def _link(shared: Path, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in ("apps", "evidence"):
        (shared / name).mkdir(parents=True, exist_ok=True)
        link = run_dir / name
        if not link.exists():
            os.symlink(shared / name, link)


def run_set(set_name: str, case_doc: dict[str, Any], cases_by_id: dict[str, dict], *, data_dir: Path,
            gomodcache: Path, factory, binary, gv_exe, gv_db, only=None, rerun=False, log=print) -> tuple[dict, dict, dict]:
    from vulntrace.d3 import triage_run as tr
    from vulntrace.dataset import vulndb
    from vulntrace.pipeline.cli import repo_commit

    docs, verdicts = {}, {}
    for policy, label in POLICIES:
        run_dir = data_dir / label
        _link(data_dir / "shared", run_dir)
        log(f"== {set_name}: targets {label}")
        docs[label], verdicts[label] = tr.eval_d3(
            case_doc, cases_by_id=cases_by_id, data_dir=run_dir, gomodcache=gomodcache, cache_root=gomodcache.parent,
            base=factory(), binary=binary, vulndb_commit=vulndb.pinned_commit(), repo_commit=repo_commit(),
            gv_exe=gv_exe, gv_db=gv_db, only=only, rerun=rerun, log=log, target_policy=policy, set_name=set_name)
    rows_h = {r["id"]: r for r in docs["hygiene"]["rows"]}
    rows_l = {r["id"]: r for r in docs["legacy"]["rows"]}
    rows = [case_row(c, cases_by_id.get(c["advisory"]), rows_h.get(c["id"]), rows_l.get(c["id"]),
                     verdicts["hygiene"].get(c["id"]), verdicts["legacy"].get(c["id"]))
            for c in case_doc["cases"] if not only or c["id"] in only]
    root = tr.goroot()
    doc = {"schema_version": SCHEMA_VERSION, "set": set_name, "rows": rows, "summary": summary(rows),
           "pipeline": {"feasibility_filter": "on (N = 20 examined paths)", "evidence_stage": "on",
                        "runs": ["hygiene (CP10 target hygiene)", "legacy (--legacy-targets)"]},
           "toolchain": {label: docs[label]["summary"]["toolchain"] for _, label in POLICIES},
           "env": docs["hygiene"]["env"], "max_mains": docs["hygiene"]["max_mains"],
           "seconds_per_case": {label: docs[label]["summary"]["seconds_per_case"] for _, label in POLICIES},
           "verdict_provenance": {label: docs[label]["verdict_provenance"] for _, label in POLICIES},
           "govulncheck": ({"module": govuln.GOVULNCHECK_MODULE, "version": govuln.GOVULNCHECK_VERSION,
                            "db": f"pinned vulndb snapshot {vulndb.pinned_commit()} data/osv (flat directory)",
                            "mode": "source, -scan symbol, main packages as roots, GOPROXY=off",
                            "scoring": "stratum S: REACHABLE claim = a symbol-level finding; stratum N: REACHABLE "
                                       "claim = any finding (symbol, package or module level)"}
                           if gv_exe else {"skipped": True}),
           "statement": "REACHABLE means reachable in the call graph from a main package, not exploitable. govulncheck "
                        "is a reference, not truth; truth comes from the adjudication sheets."}
    if set_name in IN_SAMPLE:
        doc["label"] = IN_SAMPLE[set_name]
    sanitised = {label: {cid: tr.sanitise(v, gomodcache, root) for cid, v in verdicts[label].items()}
                 for _, label in POLICIES}
    if set_name in IN_SAMPLE:
        doc["cp9_reproduction"] = reproduce_cp9(set_name, sanitised["legacy"])
    if only:
        doc["partial_run"] = {"only": only}
    return tr.sanitise(doc, gomodcache, root), sanitised["hygiene"], sanitised["legacy"]


def write_set(set_name: str, doc: dict[str, Any], hyg: dict[str, dict], leg: dict[str, dict], out_dir: Path,
              write) -> None:
    from vulntrace.eval.feasibility_real import compact_for_commit, write_verdict

    base = out_dir / set_name
    gz = []
    for label, vs in (("hygiene", hyg), ("legacy", leg)):
        for cid, v in sorted(vs.items()):
            name = write_verdict(base / f"verdicts_{label}", cid, compact_for_commit(v))
            if name.endswith(".gz"):
                gz.append(f"verdicts_{label}/{name}")
    doc["verdict_files_gzipped"] = gz
    write(base / f"{set_name}_verdicts.json", doc)


# --- fixtures --------------------------------------------------------------------------------------
def run_fixtures(factory_legacy, factory_hygiene, work_dir: Path, binary, log=print) -> dict[str, Any]:
    from vulntrace.eval import feasibility_eval as fe
    from vulntrace.eval import triage_eval as te

    committed = json.loads(fe.CP7_FIXTURES.read_text(encoding="utf-8"))
    log("CP2/CP7 fixtures, legacy targets, filter off, evidence stage on (reproduction of the committed CP7 results)")
    legacy = te.eval_fixtures(factory_legacy, work_dir / "legacy", binary, log=log, target_policy=sy.POLICY_LEGACY)
    log("CP2/CP7 fixtures, CP10 target hygiene")
    hygiene = te.eval_fixtures(factory_hygiene, work_dir / "hygiene", binary, log=log, target_policy=sy.POLICY_HYGIENE)
    changes = []
    for x, y in zip(legacy["rows"], hygiene["rows"]):
        if (x["verdict"], x["reason_codes"]) != (y["verdict"], y["reason_codes"]):
            changes.append({"id": x["id"], "mode": x["mode"], "truth": x["truth"], "legacy": x["verdict"],
                            "hygiene": y["verdict"], "reason_codes_hygiene": y["reason_codes"]})
    return {"schema_version": SCHEMA_VERSION, "set": "fixtures",
            "cp7_reproduction": fe.compare_cp7(legacy, committed),
            "hygiene_changes": changes,
            "hygiene_false_not_reachable": [c for c in changes if c["truth"] == REACHABLE and c["hygiene"] == NOT_REACHABLE],
            "hygiene_summary": {m: hygiene["summary"][m]["final"] for m in hygiene["summary"]},
            "legacy_summary": {m: legacy["summary"][m]["final"] for m in legacy["summary"]},
            "statement": "Fixture truth is about each case's target symbol. Mode 1 on fixtures uses synthetic "
                         "advisories without curated symbols (stratum N), so hygiene can only exclude context-only "
                         "targets there."}


__all__ = ["run_set", "write_set", "run_fixtures", "case_row", "summary", "govulncheck_view", "stable",
           "reproduce_cp9", "CANT_DETERMINE"]
