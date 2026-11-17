"""CP9 deliverable 4, D1/D4: how many REACHABLE verdicts the filter downgrades, by pattern (the cost
of the filter; no truth exists for these modules).

The filter is downgrade-only (proved by tests), so only cases whose CP7 verdict was REACHABLE can
change. Those cases are re-run with CP7's own runner (`triage_eval.eval_real`, unchanged), twice:
filter off (which must reproduce the CP7 verdict) and filter on. Evidence comes from the
materialised `data/` directory (`dataset materialize --set d1|d4 --cases <the filtered list>`); each
run has its own output directory under `data/cp9/<set>/`.
"""

import gzip
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from vulntrace.dataset import build as dataset_build
from vulntrace.dataset import datasets
from vulntrace.eval import triage_eval as te
from vulntrace.eval.feasibility_real import entry_facts
from vulntrace.eval.lift_cli import default_gomodcache
from vulntrace.eval.triage_cli import EXIT_MISSING_PREREQUISITE, EXIT_OK, _log, _write
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import feasibility as fz
from vulntrace.verdict import CANT_DETERMINE, PATHS_INFEASIBLE, REACHABLE

SCHEMA_VERSION = "1.0"
CP7 = REPO_ROOT / "docs" / "results" / "cp7"
EVIDENCE_SUBDIRS = ("fix_evidence", "release_range", "candidate_code")


def reachable_ids(dataset: str) -> list[str]:
    rows = json.loads((CP7 / f"{dataset}.json").read_text(encoding="utf-8"))["rows"]
    return sorted(r["id"] for r in rows if r.get("verdict") == REACHABLE)


def filtered_case_list(dataset: str) -> dict[str, Any]:
    name = "D1_cases.json" if dataset == "d1" else "D4_cases.json"
    full = json.loads((dataset_build.RESULTS_DATASETS_DIR / name).read_text(encoding="utf-8"))
    keep = set(reachable_ids(dataset))
    return {**full, "cases": [c for c in full["cases"] if c["id"] in keep],
            "cp9_note": f"the {len(keep)} cases whose CP7 verdict was REACHABLE (only these can change)"}


def _read_gz(p: Path) -> Any:
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def compare(dataset: str, off_doc: dict[str, Any], on_doc: dict[str, Any], run_dirs: dict[str, Path]) -> dict[str, Any]:
    cp7 = {r["id"]: r for r in json.loads((CP7 / f"{dataset}.json").read_text(encoding="utf-8"))["rows"]}
    off = {r["id"]: r for r in off_doc["rows"]}
    on = {r["id"]: r for r in on_doc["rows"]}
    rows = []
    for cid in sorted(off):
        a, b, c = off[cid], on.get(cid) or {}, cp7.get(cid) or {}
        vp = run_dirs["on"] / "triage" / dataset / f"{cid}.verdict.json.gz"
        facts = entry_facts(_read_gz(vp)) if vp.is_file() else []
        rows.append({"id": cid, "cluster_key": a.get("cluster_key"), "mode": a.get("mode"),
                     "verdict_cp7": c.get("verdict"), "reason_codes_cp7": c.get("reason_codes"),
                     "verdict_off": a.get("verdict"), "reason_codes_off": a.get("reason_codes"),
                     "verdict_on": b.get("verdict"), "reason_codes_on": b.get("reason_codes"),
                     "reproduces_cp7": (a.get("verdict"), a.get("reason_codes")) == (c.get("verdict"), c.get("reason_codes")),
                     "downgraded": a.get("verdict") == REACHABLE and b.get("verdict") == CANT_DETERMINE
                     and PATHS_INFEASIBLE in (b.get("reason_codes") or []),
                     "filter_statuses": dict(Counter(x["status"] for x in facts)),
                     "deciding_patterns": dict(Counter(x["deciding_pattern"] for x in facts if x["status"] == fz.INFEASIBLE)),
                     "undecided_reasons": dict(Counter(x["undecided_reason"] for x in facts if x["status"] == fz.UNDECIDED)),
                     "error": a.get("harness_error") or b.get("harness_error")})
    reach_off = [r for r in rows if r["verdict_off"] == REACHABLE]
    down = [r for r in rows if r["downgraded"]]
    return {"rows": rows, "summary": {
        "cp7_reachable_cases": len(cp7 and [1 for r in cp7.values() if r.get("verdict") == REACHABLE]),
        "rerun": len(rows), "reproduced_cp7": sum(r["reproduces_cp7"] for r in rows),
        "not_reproduced": [{"id": r["id"], "cp7": r["verdict_cp7"], "off": r["verdict_off"], "error": r["error"]}
                           for r in rows if not r["reproduces_cp7"]],
        "reachable_off": len(reach_off), "downgraded": len(down),
        "downgraded_ids": [r["id"] for r in down],
        "downgraded_by_case_pattern": dict(Counter(p for r in down for p in r["deciding_patterns"])),
        "entry_statuses": dict(sum((Counter(r["filter_statuses"]) for r in rows), Counter())),
        "entry_deciding_patterns": dict(sum((Counter(r["deciding_patterns"]) for r in rows), Counter())),
        "undecided_reasons": dict(sum((Counter(r["undecided_reasons"]) for r in rows), Counter()))}}


def cmd(args, argv, binary, off_factory, on_factory, feas, env, out_dir: Path) -> int:
    dataset = args.dataset_set
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    evidence_root = dataset_build.DATA_DIR
    case_list = filtered_case_list(dataset)
    missing = [c["id"] for c in case_list["cases"]
               if not (evidence_root / ("fix_evidence" if dataset == "d1" else "release_range") / f"{c['id']}.json").is_file()]
    list_path = Path(args.data_dir or dataset_build.DATA_DIR / "cp9" / dataset) / "cases.json"
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text(json.dumps(case_list, indent=1), encoding="utf-8")
    if missing:
        print(f"missing prerequisite: evidence for {len(missing)} case(s); run `python -m vulntrace dataset materialize "
              f"--set {dataset} --cases {list_path}`")
        return EXIT_MISSING_PREREQUISITE
    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    gomodcache.mkdir(parents=True, exist_ok=True)
    os.environ["GOMODCACHE"] = str(gomodcache)
    os.environ["GOCACHE"] = str(gomodcache.parent / (gomodcache.name + "-gocache"))
    os.environ["GOWORK"] = "off"
    docs, run_dirs = {}, {}
    for label, factory in (("off", off_factory), ("on", on_factory)):
        run_dir = list_path.parent / label
        run_dir.mkdir(parents=True, exist_ok=True)
        for sub in EVIDENCE_SUBDIRS:
            link = run_dir / sub
            if not link.exists() and (evidence_root / sub).is_dir():
                os.symlink((evidence_root / sub).resolve(), link)
        _log(f"== {dataset}: filter {label} ({len(case_list['cases'])} cases)")
        docs[label] = te.eval_real(dataset, case_list, {c["id"]: c for c in cases}, run_dir, base_factory=factory,
                                   repo_cache=Path(args.repo_cache) if args.repo_cache else None, gomodcache=gomodcache,
                                   jobs=1, max_mains=te.EVAL_MAX_MAINS, only=args.only, rerun=args.rerun, log=_log)
        run_dirs[label] = run_dir
    doc = {"schema_version": SCHEMA_VERSION, "set": dataset, "feasibility_settings": feas, "environment": env,
           "note": "Distribution only, no truth: these are library modules analysed as their own app (CP7). Only the "
                   "cases whose CP7 verdict was REACHABLE are re-run, because the filter can change nothing else.",
           **compare(dataset, docs["off"], docs["on"], run_dirs)}
    _write(out_dir / f"{dataset}_feasibility.json", doc)
    return EXIT_OK
