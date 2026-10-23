"""D4 ceiling measurement for graph expansion (CP5b, measurement only - no pipeline change).

CP3 and CP4 found that for some D4 cases the labelled (core) symbol is not among the functions
the release range changed, so no ranking of the candidates can find it. For those cases this
asks: does the core symbol lie within 1 or 2 caller or callee hops of some candidate in the call
graph of the vulnerable version? If so, expanding the candidate pool along the graph (the CP6
agent's `callers` / `callees` tools) could reach it; if not, it cannot.

The call graph is the helper's VTA graph of the module at the range's `from` commit, in library
mode. Only candidates that exist at that commit (side OLD or BOTH) are nodes. A hop count is the
number of call edges between the core symbol and the candidate, in either direction.
"""

import concurrent.futures as cf
import os
import platform
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from vulntrace.dataset import baselines, datasets, git_fetch
from vulntrace.dataset import build as dataset_build
from vulntrace.eval import lift_eval as le
from vulntrace.eval import lift_prep
from vulntrace.eval.run_info import run_info
from vulntrace.methods import lift as lift_method
from vulntrace.methods.helper import HelperError, ensure_helper

MAX_HOPS = 2
SIZE_BUCKETS = (("<=10", 0, 10), ("11-100", 11, 100), (">100", 101, 10**9))
EXIT_OK, EXIT_MISSING_PREREQUISITE = 0, 3


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def size_bucket(n: int) -> str:
    return next(label for label, lo, hi in SIZE_BUCKETS if lo <= n <= hi)


def ceiling_case(case: dict[str, Any], rr: dict[str, Any]) -> bool:
    """True if no core symbol is among the range's candidates (name-level, as everywhere)."""
    return not (baselines.core_symbols(case) & {c["symbol"] for c in rr["candidates"]})


def candidate_nodes(rr: dict[str, Any], module_path: str, module_rel: str) -> dict[tuple[str, str], str]:
    """{(import path, symbol): candidate id} for candidates that exist at the `from` commit."""
    out = {}
    for c in rr["candidates"]:
        if c["side"] not in ("OLD", "BOTH"):
            continue
        pkg = le.import_path_for(module_path, module_rel, c["package_dir"])
        if pkg is not None:
            out[(pkg, c["symbol"])] = c["candidate_id"]
    return out


def distances(records: dict[str, list[dict[str, Any]]], nodes: dict[tuple[str, str], str]) -> dict[str, dict[str, int]]:
    """{direction: {candidate id: smallest hop count}} from per-direction neighbor records of one core symbol."""
    out: dict[str, dict[str, int]] = {}
    for direction, recs in records.items():
        best: dict[str, int] = {}
        for rec in recs:
            for e in rec.get("edges", []):
                cid = nodes.get((e["other"]["package"], e["other"]["symbol"]))
                if cid is not None and e["hop"] < best.get(cid, 99):
                    best[cid] = e["hop"]
        out[direction] = best
    return out


def run_case(case: dict[str, Any], rr: dict[str, Any], *, repo_cache: Path | None, work_dir: Path, gomodcache: Path,
             binary: Path | None, timeout: float, keep_tree: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    fc = case["fix_commits"][0]
    repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], repo_cache)
    module = datasets.pick_d4_module(case)
    art: dict[str, Any] = {"schema_version": le.SCHEMA_VERSION, "case_id": case["id"], "module": module["module"],
                           "from_commit": rr["from"]["commit"], "n_candidates": len(rr["candidates"])}
    prep = lift_prep.prepare_case(repo_dir, rr["from"]["commit"], module["module"], work_dir, gomodcache,
                                  repo_prefix=f"{fc['host']}/{fc['owner']}/{fc['repo']}")
    art["prep"] = {k: prep.get(k) for k in ("status", "reason", "module_rel", "synthesized_go_mod")}
    core = [{"package": p["package"], "symbol": s} for p in module["packages"] for s in p["core_symbols"]]
    art["core"] = core
    art["neighbors"] = {}
    if prep["status"] == lift_prep.READY and core:
        nodes = candidate_nodes(rr, module["module"], prep["module_rel"] or "")
        art["n_candidate_nodes"] = len(nodes)
        for direction, fn in (("callers", lift_method.run_callers), ("callees", lift_method.run_callees)):
            recs = fn(Path(prep["module_dir"]), core, hops=MAX_HOPS, max_results=5000, timeout=timeout, binary=binary)
            art["neighbors"][direction] = recs
        art["distances"] = {}
        for i, t in enumerate(core):
            per_dir = {d: [art["neighbors"][d][i]] for d in art["neighbors"]}
            art["distances"][f"{t['package']}::{t['symbol']}"] = distances(per_dir, nodes)
    if not keep_tree:
        shutil.rmtree(work_dir / "tree", ignore_errors=True)
    art["seconds"] = round(time.monotonic() - started, 1)
    return art


def classify(art: dict[str, Any]) -> dict[str, Any]:
    """Per case: did the graph load, were the core symbols found, and the smallest hop count to any candidate."""
    out: dict[str, Any] = {"prep": art["prep"]["status"], "synthesized_go_mod": bool(art["prep"].get("synthesized_go_mod")),
                           "loaded": False, "core_found": False, "min_hops": None, "min_hops_by_direction": {"callers": None, "callees": None},
                           "candidates_within": {"1": 0, "2": 0}, "detail": art["prep"]["reason"]}
    if art["prep"]["status"] != lift_prep.READY:
        return out
    results = [r for d in art["neighbors"].values() for r in d]
    errs = [r["error"] for r in results if r["error"]]
    out["loaded"] = not any(e["code"] in ("LOAD_FAILED", "TIMEOUT", "HELPER_MISSING", "BAD_RESPONSE", "CONTRACT_MISMATCH") for e in errs)
    if not out["loaded"]:
        out["detail"] = f"{errs[0]['code']}: {errs[0]['message']}"[:300]
        return out
    out["core_found"] = any(r["result"] in ("FOUND", "NONE") for r in results)
    if not out["core_found"]:
        out["detail"] = "; ".join(sorted({f"{r['error']['code'] if r['error'] else r['result']}" for r in results}))[:300]
        return out
    within: dict[int, set] = {1: set(), 2: set()}
    for per_sym in art.get("distances", {}).values():
        for direction, best in per_sym.items():
            for cid, hop in best.items():
                cur = out["min_hops_by_direction"][direction]
                out["min_hops_by_direction"][direction] = hop if cur is None else min(cur, hop)
                for k in (1, 2):
                    if hop <= k:
                        within[k].add(cid)
    hops = [h for h in out["min_hops_by_direction"].values() if h is not None]
    out["min_hops"] = min(hops) if hops else None
    out["candidates_within"] = {"1": len(within[1]), "2": len(within[2])}
    return out


def summarize(rows: list[dict[str, Any]], n_all: int, n_nonavailable: int) -> dict[str, Any]:
    """Counts with the denominator named next to every rate."""
    n = len(rows)
    loaded = [r for r in rows if r["loaded"] and r["core_found"]]
    def rate(k, sub):
        return {"count": k, "of": len(sub), "rate": k / len(sub) if sub else float("nan")}
    hit = lambda r, k: r["min_hops"] is not None and r["min_hops"] <= k  # noqa: E731
    out: dict[str, Any] = {
        "d4_cases": n_all, "without_evidence": n_nonavailable, "ceiling_cases": n,
        "prepared": sum(1 for r in rows if r["prep"] == lift_prep.READY), "loaded_with_core_found": len(loaded),
        "synthesized_go_mod": sum(1 for r in rows if r["synthesized_go_mod"]),
        "failure_counts": dict(sorted(Counter(r["failure"] for r in rows if not (r["loaded"] and r["core_found"])).items())),
        "within_1": rate(sum(hit(r, 1) for r in loaded), loaded), "within_2": rate(sum(hit(r, 2) for r in loaded), loaded),
        "within_1_of_all_ceiling_cases": rate(sum(hit(r, 1) for r in loaded), rows),
        "within_2_of_all_ceiling_cases": rate(sum(hit(r, 2) for r in loaded), rows),
        "by_direction": {d: {"within_1": rate(sum(1 for r in loaded if (r["min_hops_by_direction"][d] or 99) <= 1), loaded),
                             "within_2": rate(sum(1 for r in loaded if (r["min_hops_by_direction"][d] or 99) <= 2), loaded)}
                         for d in ("callers", "callees")},
        "by_size": {}, "expanded_candidates_median": None,
    }
    for label, _lo, _hi in SIZE_BUCKETS:
        sub = [r for r in loaded if r["size_bucket"] == label]
        out["by_size"][label] = {"n": len(sub), "within_1": rate(sum(hit(r, 1) for r in sub), sub),
                                 "within_2": rate(sum(hit(r, 2) for r in sub), sub)}
    sizes = sorted(r["candidates_within"]["2"] for r in loaded if hit(r, 2))
    if sizes:
        out["expanded_candidates_median"] = sizes[len(sizes) // 2]
    return out


def cmd_ceiling(args, argv) -> int:
    started = time.monotonic()
    try:
        binary = ensure_helper()
    except HelperError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    from vulntrace.eval.lift_cli import _read, default_gomodcache

    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    gomodcache.mkdir(parents=True, exist_ok=True)
    os.environ["GOMODCACHE"], os.environ["GOWORK"] = str(gomodcache), "off"
    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D4_cases.json"
    case_list = _read(case_list_path)
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    cases_by_id = {c["id"]: c for c in cases}
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
    rrs, missing = {}, 0
    for e in case_list["cases"]:
        p = data_dir / "release_range" / f"{e['id']}.json"
        if p.is_file():
            rrs[e["id"]] = _read(p)
        else:
            missing += 1
    if missing:
        print(f"error: {missing} D4 case(s) have no release_range evidence in {data_dir}; run `dataset materialize --set d4`", file=sys.stderr)
        return 2
    ceiling = [e["id"] for e in case_list["cases"] if rrs[e["id"]]["status"] in ("AVAILABLE", "TRUNCATED")
               and rrs[e["id"]]["candidates"] and ceiling_case(cases_by_id[e["id"]], rrs[e["id"]])]
    n_noev = sum(1 for e in case_list["cases"] if rrs[e["id"]]["status"] not in ("AVAILABLE", "TRUNCATED") or not rrs[e["id"]]["candidates"])
    if args.limit:
        ceiling = ceiling[: args.limit]
    out_dir = data_dir / "lift" / "d4"
    out_dir.mkdir(parents=True, exist_ok=True)
    arts, todo = {}, []
    for cid in ceiling:
        p = out_dir / f"{cid}.json"
        if p.is_file() and not args.rerun:
            arts[cid] = _read(p)
        else:
            todo.append(cid)
    _log(f"d4 ceiling: {len(ceiling)} cases whose core symbol is not a candidate (of {len(case_list['cases'])}; "
         f"{n_noev} have no candidates at all), {len(todo)} to run with {args.jobs} job(s)")
    repo_cache = Path(args.repo_cache) if args.repo_cache else None

    def work(cid):
        art = run_case(cases_by_id[cid], rrs[cid], repo_cache=repo_cache, work_dir=data_dir / "lift_work" / cid,
                       gomodcache=gomodcache, binary=binary, timeout=args.timeout, keep_tree=args.keep_trees)
        le.write_json(out_dir / f"{cid}.json", art)
        return cid, art

    done = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for fut in cf.as_completed([pool.submit(work, cid) for cid in todo]):
            cid, art = fut.result()
            arts[cid] = art
            done += 1
            c = classify(art)
            _log(f"  {done}/{len(todo)} {cid} min_hops={c['min_hops']} loaded={c['loaded']} in {art['seconds']}s"
                 + ("" if c["loaded"] else f" - {str(c['detail'])[:140]}"))
    rows = []
    for cid in ceiling:
        art, c = arts[cid], classify(arts[cid])
        failure = None if (c["loaded"] and c["core_found"]) else (
            c["prep"] if c["prep"] != lift_prep.READY else ("LOAD_FAILED" if not c["loaded"] else "CORE_NOT_IN_GRAPH"))
        rows.append({"id": cid, "n_candidates": art["n_candidates"], "size_bucket": size_bucket(art["n_candidates"]),
                     "core": sorted({t["symbol"] for t in art["core"]}), "failure": failure, **c})
    summary = summarize(rows, len(case_list["cases"]), n_noev)
    wall = round(time.monotonic() - started, 1)
    doc = {"schema_version": le.SCHEMA_VERSION, "experiment": "LIFT_D4_CEILING", "dataset": "D4",
           "environment": {**run_info(argv), "machine": f"{platform.machine()} {os.cpu_count()} cpu", "jobs": args.jobs,
                           "wall_seconds_this_invocation": wall,
                           "per_case_seconds_total": round(sum(a.get("seconds", 0) for a in arts.values()), 1)},
           "settings": {"max_hops": MAX_HOPS, "graph": "helper VTA call graph, library mode, module at the range's `from` commit; "
                                                        "closures folded into their enclosing function; only candidates that exist at "
                                                        "that commit (side OLD or BOTH) are nodes; callers/callees limited to the module",
                        "definition": "ceiling case = no core symbol among the range's candidates (name-level)"},
           "summary": summary, "rows": rows}
    out = Path(args.out) if args.out else Path("results/cp5b")
    le.write_json(out / "lift_d4_ceiling.json", doc)
    print(f"d4 ceiling: {summary['ceiling_cases']} cases; graph loaded with core symbol found: {summary['loaded_with_core_found']}; "
          f"within 1 hop: {summary['within_1']['count']}; within 2 hops: {summary['within_2']['count']}")
    print(f"wrote {out / 'lift_d4_ceiling.json'} in {wall}s")
    return EXIT_OK
