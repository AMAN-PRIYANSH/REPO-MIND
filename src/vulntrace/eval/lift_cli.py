"""Command implementation for `python -m vulntrace eval lift` (CP5b).

    eval lift --set d1            lifting vs derived_symbols, and E1+L on the committed CP5 selections
    eval lift --set d4-ceiling    how often a missed core symbol is within 1 or 2 call-graph hops of a candidate

Both need source checkouts and dependencies, so they use the network (Go module proxy, GitHub via
the already materialised git cache) through Python only. Per-case evidence stays in the gitignored
`data/lift/`; the JSON written to --out is small and is what the results document is rendered from.
"""

import concurrent.futures as cf
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from vulntrace.dataset import datasets, git_fetch
from vulntrace.dataset import build as dataset_build
from vulntrace.eval import lift_eval as le
from vulntrace.eval.run_info import run_info
from vulntrace.methods import lift as lift_method
from vulntrace.methods.helper import HelperError, ensure_helper

EXIT_OK, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 2, 3
DEFAULT_OUT = "results/cp5b"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def default_gomodcache() -> Path:
    return git_fetch.default_cache_root().parent / "gomod"


def _read(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_d1_inputs(args) -> tuple[dict, dict[str, dict], dict[str, dict], Path]:
    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D1_cases.json"
    case_list = _read(case_list_path)
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    cases_by_id = {c["id"]: c for c in cases}
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
    evidence = {}
    for e in case_list["cases"]:
        p = data_dir / "fix_evidence" / f"{e['id']}.json"
        if p.is_file():
            evidence[e["id"]] = _read(p)
    return case_list, cases_by_id, evidence, data_dir


def _e1_docs(e1_dir: Path) -> dict[str, dict]:
    docs = {}
    for p in sorted(e1_dir.glob("select_fix__*.json")):
        doc = _read(p)
        docs[doc["model"]["alias"]] = doc
    return docs


def cmd_lift(args, argv) -> int:
    if args.dataset_set == "d4-ceiling":
        from vulntrace.eval import lift_ceiling

        return lift_ceiling.cmd_ceiling(args, argv)
    started = time.monotonic()
    try:
        binary = ensure_helper()
    except HelperError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    gomodcache.mkdir(parents=True, exist_ok=True)
    os.environ["GOMODCACHE"] = str(gomodcache)       # the helper and `go mod tidy` share one module cache
    os.environ["GOWORK"] = "off"
    case_list, cases_by_id, evidence, data_dir = _load_d1_inputs(args)
    e1_dir = Path(args.e1_dir) if args.e1_dir else Path("docs/results/cp5")
    e1_docs = _e1_docs(e1_dir)
    selections = le.e1_selected_ids(e1_docs)
    entries = [e for e in case_list["cases"] if e["status"] == "AVAILABLE" or le.derived_names(cases_by_id[e["id"]])]
    if args.limit:
        entries = entries[: args.limit]
    out_dir = data_dir / "lift"
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_cache = Path(args.repo_cache) if args.repo_cache else None
    arts: dict[str, dict] = {}
    todo = []
    for e in entries:
        p = out_dir / f"{e['id']}.json"
        if p.is_file() and not args.rerun:
            arts[e["id"]] = _read(p)
        else:
            todo.append(e)
    _log(f"lift: {len(entries)} cases, {len(arts)} already done, {len(todo)} to run with {args.jobs} job(s); module cache {gomodcache}")

    def work(e):
        case = cases_by_id[e["id"]]
        art = le.run_case(case, evidence.get(e["id"]), selections.get(e["id"], {}), repo_cache=repo_cache,
                          work_dir=data_dir / "lift_work" / e["id"], gomodcache=gomodcache, binary=binary,
                          timeout=args.timeout, keep_tree=args.keep_trees)
        le.write_json(out_dir / f"{e['id']}.json", art)
        return e["id"], art

    done = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for fut in cf.as_completed([pool.submit(work, e) for e in todo]):
            cid, art = fut.result()
            arts[cid] = art
            done += 1
            outc = le.case_outcome(art)
            _log(f"  {done}/{len(todo)} {cid} {'LIFTED' if outc['success'] else outc['failure']} in {art['seconds']}s"
                 + ("" if outc["success"] else f" - {str(outc['detail'])[:160]}"))
    rows = le.score_cases(cases_by_id, entries, arts)
    summary = le.summarize_lifting(rows)
    e1_blocks = _e1_plus_l(case_list, cases_by_id, evidence, e1_docs, arts)
    wall = round(time.monotonic() - started, 1)
    doc = {
        "schema_version": le.SCHEMA_VERSION, "experiment": "LIFT_D1", "dataset": "D1",
        "environment": {**run_info(argv), "machine": f"{platform.machine()} {os.cpu_count()} cpu", "jobs": args.jobs,
                        "wall_seconds_this_invocation": wall, "per_case_seconds_total": round(sum(a.get("seconds", 0) for a in arts.values()), 1),
                        "gomodcache_note": "shared module cache; first-time downloads dominate the per-case time"},
        "settings": {"rules": list(le.RULES), "max_lift_depth": le.MAX_LIFT_DEPTH, "scoring": "symbol names, not package paths",
                     "walk": "callers are followed only inside the packages the request matched (the module under study); "
                             "closures are folded into their enclosing function; interface calls and function values use the same "
                             "VTA call graph as reach",
                     "source": "vulnerable side = parent of the first fix commit; E1 selections = committed CP5 files in " + str(e1_dir)},
        "case_list": {"cases": len(case_list["cases"]), "attempted_for_lift": len(entries), "status_counts": case_list["status_counts"]},
        "lifting": summary, "examples": le.worked_examples(rows), "rows": rows,
        "e1_plus_l": e1_blocks,
    }
    out = Path(args.out) if args.out else Path(DEFAULT_OUT)
    # The per-case E1+L rows (predicted sets) go to one file per model so every committed file stays small.
    for alias, block in doc["e1_plus_l"].items():
        le.write_json(out / f"e1_plus_l__{alias}.json", {"schema_version": le.SCHEMA_VERSION, "model": block["model"], "rows": block.pop("rows")})
    le.write_json(out / "lift_d1.json", doc)
    c = summary["coverage"]
    print(f"lift D1: {summary['cases_with_derived']} cases with derived_symbols; module loaded {summary['module_loaded']}; "
          f"lifted {c['lifted_ok']} ({c['rate']:.3f}); failures {summary['failure_counts']}")
    print(f"wrote {out / 'lift_d1.json'} in {wall}s")
    return EXIT_OK


def _e1_plus_l(case_list, cases_by_id, evidence, e1_docs, arts) -> dict[str, Any]:
    from vulntrace.eval.llm_report import group_defs

    out = {}
    ids = [e["id"] for e in case_list["cases"]]
    for alias, doc in e1_docs.items():
        rows, skipped = le.e1_plus_l_rows(ids, cases_by_id, evidence, doc, arts)
        cutoff = doc["model"]["cutoff"]
        out[alias] = {"model": {k: doc["model"].get(k) for k in ("alias", "ollama_tag", "cutoff", "cutoff_source")},
                      "rows_used": len(rows), "skipped": skipped, "summary": le.summarize_e1_plus_l(rows, cutoff, group_defs),
                      "rows": rows}
    return out
