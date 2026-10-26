"""Evidence the agent's tools need beyond CP3/CP4's (CP6 deliverable 1): `python -m vulntrace agent prepare`.

- **Commit diffs** (`show_commit`): for every commit of a D4 case's release range, its diff of Go
  files against its first parent, read from the git cache `dataset materialize` filled
  (`git show`, no external diff or textconv drivers; vendored code left out; non-test files first,
  then tests). Read-only git, no Go needed.
- **Neighbour tables** (`callers` / `callees`, arm A3): one-hop callers and callees of every
  candidate that exists in the vulnerable release, from the CP5b helper modes on the VTA call graph
  of the module at the range's `from` commit (library mode; the walk stays inside the module).
  Needs Go, the helper and the Go module proxy. Nothing from the analysed code is executed:
  sources come from `git archive`, dependencies from `go mod tidy -e`, `GOTOOLCHAIN=local`,
  `CGO_ENABLED=0`.

Both are written per case as gzipped JSON under `<data-dir>/agent/` (gitignored: they contain
third-party code text and names). A small per-case summary (status, counts, content hash, no code)
is written to `--summary-out`, so that a table rebuilt on another machine can be compared.
A case whose evidence cannot be built gets a status and the first error line; it is counted,
never dropped, and its agent run goes on without that tool.
"""

import concurrent.futures as cf
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import datasets, git_fetch
from vulntrace.eval import lift_eval as le
from vulntrace.eval import lift_prep
from vulntrace.methods import lift as lift_method

SCHEMA_VERSION = "1.0"
DIFFS_SUBDIR, GRAPH_SUBDIR = "agent/commit_diffs", "agent/graph"
DIFF_STORE_CAP = 30000          # characters of one commit's diff kept on disk (the tool shows far less)
GIT_TIMEOUT_S = 120
NEIGHBOUR_MAX_RESULTS = 200     # per candidate and direction (the helper's max_results)
READY, NO_RANGE, FAILED = "READY", "NO_RANGE", "FAILED"
EVIDENCE_STATUSES = ("AVAILABLE", "TRUNCATED")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def write_gz(path: Path, obj: Any) -> str:
    """Write gzipped JSON (fixed mtime, so identical content gives identical bytes); returns its sha256."""
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    with open(tmp, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(data)
    os.replace(tmp, path)
    return hashlib.sha256(data).hexdigest()


def read_gz(path: Path) -> Any:
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def diffs_path(data_dir: Path, case_id: str) -> Path:
    return Path(data_dir) / DIFFS_SUBDIR / f"{case_id}.json.gz"


def graph_path(data_dir: Path, case_id: str) -> Path:
    return Path(data_dir) / GRAPH_SUBDIR / f"{case_id}.json.gz"


# --- commit diffs ----------------------------------------------------------------------------------
GIT_SHOW = ["git", "-c", "core.quotepath=off", "show", "--format=", "--no-color", "--no-ext-diff", "--no-textconv",
            "--diff-merges=first-parent"]
NON_TEST = ["*.go", ":(exclude)*_test.go", ":(exclude)vendor/*", ":(exclude)*/vendor/*"]
TESTS = ["*_test.go", ":(exclude)vendor/*", ":(exclude)*/vendor/*"]


def commit_diff(repo_dir: Path, sha: str, runner=subprocess.run) -> dict[str, Any]:
    parts = []
    for spec in (NON_TEST, TESTS):
        try:
            p = runner(GIT_SHOW + [sha, "--"] + spec, cwd=repo_dir, capture_output=True, timeout=GIT_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return {"diff": None, "error": f"git show timed out after {GIT_TIMEOUT_S}s", "chars": 0, "cut": False}
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace") if isinstance(p.stderr, bytes) else p.stderr
            return {"diff": None, "error": "git show: " + lift_prep.first_line(err), "chars": 0, "cut": False}
        out = p.stdout.decode("utf-8", "replace") if isinstance(p.stdout, bytes) else p.stdout
        if out.strip():
            parts.append(out.rstrip("\n"))
    text = "\n".join(parts)
    return {"diff": text[:DIFF_STORE_CAP], "error": None, "chars": len(text), "cut": len(text) > DIFF_STORE_CAP}


def build_commit_diffs(case: dict[str, Any], rr: dict[str, Any], repo_cache: Path | None,
                       runner=subprocess.run) -> dict[str, Any]:
    fc = case["fix_commits"][0]
    repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], repo_cache)
    doc = {"schema_version": SCHEMA_VERSION, "case_id": case["id"], "range": [rr["from"]["commit"], rr["to"]["commit"]],
           "commits": {}}
    if not repo_dir.is_dir():
        doc.update(status=FAILED, reason=f"no git cache for {fc['owner']}/{fc['repo']} (run `dataset materialize --set d4`)")
        return doc
    for c in rr["commits"]:
        doc["commits"][c["sha"]] = commit_diff(repo_dir, c["sha"], runner)
    errors = [v["error"] for v in doc["commits"].values() if v["error"]]
    doc.update(status=READY if not errors or len(errors) < len(doc["commits"]) else FAILED,
               reason=errors[0] if errors else None)
    return doc


def diffs_summary(doc: dict[str, Any], sha256: str | None) -> dict[str, Any]:
    vals = list(doc.get("commits", {}).values())
    return {"status": doc["status"], "reason": doc.get("reason"), "commits": len(vals),
            "with_diff": sum(1 for v in vals if v["error"] is None),
            "errors": sum(1 for v in vals if v["error"]), "cut": sum(1 for v in vals if v.get("cut")),
            "sha256": sha256}


# --- neighbour tables ------------------------------------------------------------------------------
def _edge(e: dict[str, Any], nodes: dict[tuple[str, str], str]) -> dict[str, Any]:
    other = e["other"]
    site = e.get("call_site") or {}
    return {"package": other["package"], "symbol": other["symbol"],
            "candidate_id": nodes.get((other["package"], other["symbol"])), "file": site.get("file"),
            "line": site.get("line"), "kind": e.get("kind")}


def table_from_records(nodes: dict[tuple[str, str], str], records: dict[str, list[dict[str, Any]]]) -> dict[str, dict]:
    """{candidate id: {status, callers, callees, truncated}} from the helper's per-direction records,
    which are in the order of `nodes`."""
    out: dict[str, dict] = {}
    statuses: dict[str, list[str]] = {}
    keys = list(nodes)
    for direction, recs in records.items():
        for key, rec in zip(keys, recs):
            cid = nodes[key]
            entry = out.setdefault(cid, {"status": None, "callers": [], "callees": [], "truncated": {}})
            if rec["result"] in ("FOUND", "NONE"):
                entry[direction] = [_edge(e, nodes) for e in rec["edges"] if e.get("hop", 1) == 1]
                entry["truncated"][direction] = bool(rec["truncated"])
                statuses.setdefault(cid, []).append("FOUND" if entry[direction] else "NONE")
            else:
                err = rec.get("error") or {}
                statuses.setdefault(cid, []).append(rec["result"] if rec["result"] != "ERROR"
                                                    else f"ERROR {err.get('code', '?')}")
    for cid, sts in statuses.items():
        problems = [s for s in sts if s not in ("FOUND", "NONE")]
        # a problem in either direction wins (the tool then says there is no information); else FOUND beats NONE
        out[cid]["status"] = problems[0] if problems else ("FOUND" if "FOUND" in sts else "NONE")
    return out


def build_graph_table(case: dict[str, Any], rr: dict[str, Any], *, repo_cache: Path | None, work_dir: Path,
                      gomodcache: Path, binary: Path | None, timeout: float,
                      neighbours: Callable = lift_method.run_neighbors) -> dict[str, Any]:
    fc = case["fix_commits"][0]
    repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], repo_cache)
    module = datasets.pick_d4_module(case)
    doc: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "case_id": case["id"], "module": module["module"],
                           "from_commit": rr["from"]["commit"], "candidates": {}}
    started = time.monotonic()
    try:
        prep = lift_prep.prepare_case(repo_dir, rr["from"]["commit"], module["module"], work_dir, gomodcache,
                                      repo_prefix=f"{fc['host']}/{fc['owner']}/{fc['repo']}")
        doc["prep"] = {k: prep.get(k) for k in ("status", "reason", "module_rel", "synthesized_go_mod", "vendored")}
        if prep["status"] != lift_prep.READY:
            doc.update(status=prep["status"], reason=prep["reason"])
            return doc
        nodes: dict[tuple[str, str], str] = {}
        for c in rr["candidates"]:
            if c["side"] in ("OLD", "BOTH"):
                pkg = le.import_path_for(module["module"], prep["module_rel"] or "", c["package_dir"])
                if pkg is not None:
                    nodes.setdefault((pkg, c["symbol"]), c["candidate_id"])
        doc["n_nodes"] = len(nodes)
        if not nodes:
            doc.update(status="NO_NODES", reason="no candidate of the vulnerable release lies inside the module")
            return doc
        targets = [{"package": p, "symbol": s} for p, s in nodes]
        recs = {d: neighbours(d, Path(prep["module_dir"]), targets, hops=1, max_results=NEIGHBOUR_MAX_RESULTS,
                              timeout=timeout, binary=binary) for d in ("callers", "callees")}
        load_errors = [r["error"] for rs in recs.values() for r in rs
                       if r["result"] == "ERROR" and (r.get("error") or {}).get("code") in
                       ("LOAD_FAILED", "TIMEOUT", "HELPER_MISSING", "BAD_RESPONSE", "CONTRACT_MISMATCH", "TYPE_ERRORS")]
        if load_errors and len(load_errors) == sum(len(rs) for rs in recs.values()):
            e = load_errors[0]
            doc.update(status=e["code"], reason=f"{e['code']}: {e['message']}"[:300])
            return doc
        doc["candidates"] = table_from_records(nodes, recs)
        any_rec = next((r for rs in recs.values() for r in rs if r.get("details", {}).get("toolchain")), None)
        doc["toolchain"] = any_rec["details"]["toolchain"] if any_rec else None
        doc.update(status=READY, reason=None)
        return doc
    finally:
        doc["seconds"] = round(time.monotonic() - started, 1)
        shutil.rmtree(work_dir, ignore_errors=True)


def graph_summary(doc: dict[str, Any], sha256: str | None) -> dict[str, Any]:
    vals = list(doc.get("candidates", {}).values())
    by: dict[str, int] = {}
    for v in vals:
        by[v["status"]] = by.get(v["status"], 0) + 1
    return {"status": doc["status"], "reason": doc.get("reason"), "nodes": doc.get("n_nodes", 0), "by_status": by,
            "caller_edges": sum(len(v["callers"]) for v in vals), "callee_edges": sum(len(v["callees"]) for v in vals),
            "truncated": sum(1 for v in vals if any(v.get("truncated", {}).values())),
            "seconds": doc.get("seconds"), "sha256": sha256,
            "go_version": (doc.get("toolchain") or {}).get("go_version")}


# --- driver ------------------------------------------------------------------------------------------
def prepare_all(case_list: dict[str, Any], cases_by_id: dict[str, dict], data_dir: Path, *, diffs: bool, graph: bool,
                repo_cache: Path | None, gomodcache: Path | None, binary: Path | None, jobs: int, timeout: float,
                rerun: bool = False, limit: int | None = None) -> dict[str, Any]:
    entries = sorted(case_list["cases"], key=lambda c: c["id"])[: limit or None]
    summary: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "commit_diffs": {}, "graph": {}}
    todo_graph = []
    for i, e in enumerate(entries, start=1):
        cid = e["id"]
        rr_p = Path(data_dir) / "release_range" / f"{cid}.json"
        rr = json.loads(rr_p.read_text(encoding="utf-8")) if rr_p.is_file() else None
        usable = rr is not None and rr["status"] in EVIDENCE_STATUSES and rr["candidates"]
        if diffs:
            if not usable:
                summary["commit_diffs"][cid] = {"status": NO_RANGE, "reason": "no usable release range", "sha256": None}
            else:
                p = diffs_path(data_dir, cid)
                if p.is_file() and not rerun:
                    doc = read_gz(p)
                    sha = hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                else:
                    doc = build_commit_diffs(cases_by_id[cid], rr, repo_cache)
                    sha = write_gz(p, doc)
                summary["commit_diffs"][cid] = diffs_summary(doc, sha)
                _log(f"  diffs {i}/{len(entries)} {cid} {doc['status']} ({summary['commit_diffs'][cid]['with_diff']} of "
                     f"{summary['commit_diffs'][cid]['commits']} commits)")
        if graph:
            if not usable:
                summary["graph"][cid] = {"status": NO_RANGE, "reason": "no usable release range", "sha256": None}
            else:
                todo_graph.append((cid, rr))
    if graph:
        def work(item):
            cid, rr = item
            p = graph_path(data_dir, cid)
            if p.is_file() and not rerun:
                doc = read_gz(p)
                return cid, doc, hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            doc = build_graph_table(cases_by_id[cid], rr, repo_cache=repo_cache, work_dir=Path(data_dir) / "agent_work" / cid,
                                    gomodcache=gomodcache, binary=binary, timeout=timeout)
            return cid, doc, write_gz(p, doc)

        done = 0
        with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            for fut in cf.as_completed([pool.submit(work, it) for it in todo_graph]):
                cid, doc, sha = fut.result()
                summary["graph"][cid] = graph_summary(doc, sha)
                done += 1
                s = summary["graph"][cid]
                _log(f"  graph {done}/{len(todo_graph)} {cid} {s['status']} nodes={s['nodes']} in {s['seconds']}s"
                     + (f" - {str(s['reason'])[:140]}" if s["reason"] else ""))
        summary["graph"] = dict(sorted(summary["graph"].items()))
    for key in ("commit_diffs", "graph"):
        counts: dict[str, int] = {}
        for v in summary[key].values():
            counts[v["status"]] = counts.get(v["status"], 0) + 1
        summary[f"{key}_status_counts"] = dict(sorted(counts.items()))
    return summary


def load_case_extras(data_dir: Path, case_id: str) -> tuple[dict | None, str | None, dict | None, str | None]:
    """(commit diffs by sha or None, why missing, neighbour table by candidate or None, why missing)."""
    diffs, dnote, table, gnote = None, None, None, None
    p = diffs_path(data_dir, case_id)
    if p.is_file():
        doc = read_gz(p)
        if doc["status"] == READY:
            diffs = doc["commits"]
        else:
            dnote = f"{doc['status']}: {doc.get('reason')}"
    else:
        dnote = "commit diffs not prepared (run `agent prepare --diffs`)"
    g = graph_path(data_dir, case_id)
    if g.is_file():
        doc = read_gz(g)
        if doc["status"] == READY:
            table = doc["candidates"]
        else:
            gnote = f"{doc['status']}: {doc.get('reason')}"
    else:
        gnote = "neighbour table not prepared (run `agent prepare --graph`)"
    return diffs, dnote, table, gnote
