"""CP9 evaluation on real applications: D3 (in-sample), D3b (held-out), D1/D4 (distributions).

D3 / D3b: the CP7b runner (`d3.triage_run.eval_d3`, unchanged) runs every case twice with the same
inputs, once with the filter off (`--no-feasibility`, the CP7b pipeline) and once on. The two runs
share the application trees and the evidence (`<data>/shared`) and keep separate outputs
(`<data>/off`, `<data>/on`), so neither resumes the other. Committed: one compact file per set with
a row per case (verdicts before and after, the filter's answer per REACHABLE entry, patterns, the
first infeasible steps with file, line and reason, the evidence path's length) and the full
verdicts of both runs, local paths rewritten as in CP7b.

D3 was the design set of the filter's patterns, so its before/after is labelled IN-SAMPLE and is no
evidence of generalisation. For D3 the filter-off run is also compared with the committed CP7b
verdicts (acceptance criterion 7).

D1 / D4: see `eval_distribution` (only the cases whose CP7 verdict was REACHABLE can change).
"""

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from vulntrace.dataset import build as dataset_build
from vulntrace.dataset import datasets
from vulntrace.eval import triage_eval as te
from vulntrace.eval.triage_cli import EXIT_MISSING_PREREQUISITE, EXIT_OK, _log, _write
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import feasibility as fz
from vulntrace.verdict import CANT_DETERMINE, PATHS_INFEASIBLE, REACHABLE

SCHEMA_VERSION = "1.0"
CP7B = REPO_ROOT / "docs" / "results" / "cp7b"
IN_SAMPLE_LABEL = ("IN-SAMPLE: the filter's patterns F1-F3 were designed from these D3 cases (the CP7b reviewers' "
                   "notes), so this before/after is not evidence that the filter generalises. Only D3b is.")
MAX_STEPS_PER_ENTRY = 3
COMMITTED_EXAMINED = 3   # committed verdict copies keep this many examined paths per entry (the full list stays in data/)


def compact_for_commit(v: dict[str, Any], off: dict[str, Any] | None = None) -> dict[str, Any]:
    """A committed copy small enough for the 512 KiB limit: each entry's `feasibility.examined` keeps its
    first COMMITTED_EXAMINED paths (shortest first) and records how many there were; for a filter-on verdict
    whose method paths are identical to the filter-off verdict's (`off`, committed next to it), the method
    paths are left out and the top-level `feasibility.committed_copy` says so. Status, evidence path,
    results, reasons and verified paths are unchanged."""
    import copy

    v = copy.deepcopy(v)
    for e in v.get("per_symbol") or []:
        f = e.get("feasibility")
        if f and len(f.get("examined") or []) > COMMITTED_EXAMINED:
            f["examined_total"] = len(f["examined"])
            f["examined"] = f["examined"][:COMMITTED_EXAMINED]
            f["examined_committed"] = COMMITTED_EXAMINED
    if off is not None and v.get("feasibility") is not None:
        same = [a.get("paths") for a in v["per_symbol"]] == [b.get("paths") for b in off.get("per_symbol") or []]
        if same:
            for e in v["per_symbol"]:
                e.pop("paths", None)
        v["feasibility"]["committed_copy"] = {
            "examined_per_entry": COMMITTED_EXAMINED,
            "method_paths": "left out: identical to the filter-off verdict committed beside this file" if same
            else "kept (they differ from the filter-off verdict)"}
    return v


def _steps(e: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for ex in (e.get("feasibility") or {}).get("examined") or []:
        st = ex.get("first_infeasible")
        if st and len(out) < MAX_STEPS_PER_ENTRY:
            out.append({"path_length": ex["length"], "pattern": st["pattern"], "edge_index": st["edge_index"],
                        "caller": st["edge"]["caller"], "callee": st["edge"]["callee"], "site": st["edge"]["call_site"],
                        "context_sites": [c["call_site"] for c in st["context_edges"]], "reason": st["reason"]})
    return out


def write_verdict(directory: Path, cid: str, v: dict[str, Any]) -> str:
    """`<cid>.json`, or, when that would be over 512 KiB, the same content as `<cid>.json.gz` (which must be
    under 512 KiB). Nothing is dropped. Returns the file name written."""
    import gzip

    from vulntrace.eval.triage_cli import MAX_RESULT_BYTES

    v = te.example_verdict(v)
    text = json.dumps(v, indent=1, sort_keys=True) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    for stale in (directory / f"{cid}.json", directory / f"{cid}.json.gz"):
        stale.unlink(missing_ok=True)
    if len(text.encode("utf-8")) <= MAX_RESULT_BYTES:
        (directory / f"{cid}.json").write_text(text, encoding="utf-8")
        return f"{cid}.json"
    data = gzip.compress(text.encode("utf-8"), mtime=0)
    if len(data) > MAX_RESULT_BYTES:
        raise SystemExit(f"error: {directory / cid}.json.gz is {len(data)} bytes, over the 512 KiB limit")
    (directory / f"{cid}.json.gz").write_bytes(data)
    _log(f"wrote {directory / cid}.json.gz ({len(data)} bytes; {len(text)} bytes uncompressed)")
    return f"{cid}.json.gz"


def read_verdicts(directory: Path) -> dict[str, dict[str, Any]]:
    import gzip

    out = {}
    for p in sorted(directory.glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    for p in sorted(directory.glob("*.json.gz")):
        out[p.name[: -len(".json.gz")]] = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    return out


def entry_facts(v: dict[str, Any]) -> list[dict[str, Any]]:
    """The filter's answer for every entry the rule table made REACHABLE."""
    out = []
    for e in v.get("per_symbol") or []:
        if e.get("pre_feasibility_result") != REACHABLE:
            continue
        f = e.get("feasibility") or {}
        ev = f.get("evidence_path")
        out.append({"symbol": f"{e['target']['package']}.{e['target']['symbol']}", "main": e.get("main_package"),
                    "status": f.get("status"), "result": e["result"], "reason_code": e["reason_code"],
                    "examined": len(f.get("examined") or []), "examined_truncated": f.get("examined_truncated"),
                    "first_patterns": fz.first_patterns(e), "deciding_pattern": fz.deciding_pattern(e),
                    "undecided_reason": f.get("undecided_reason"), "evidence_source": f.get("evidence_source"),
                    "evidence_length": len(ev["edges"]) if ev else None,
                    "evidence_dynamic_edges": sum(1 for x in ev["edges"] if x["kind"] == "DYNAMIC") if ev else None,
                    "steps": _steps(e)})
    return out


def case_row(case_id: str, off: dict[str, Any] | None, on: dict[str, Any] | None,
             off_row: dict[str, Any] | None, on_row: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {"id": case_id}
    for k in ("advisory", "app_repo", "app_tag", "app_commit", "module", "version_selected", "cluster_key"):
        row[k] = (off_row or on_row or {}).get(k)
    row["verdict_off"] = off["verdict"] if off else None
    row["reason_codes_off"] = off["reason_codes"] if off else None
    row["verdict_on"] = on["verdict"] if on else None
    row["reason_codes_on"] = on["reason_codes"] if on else None
    row["mode"] = (on or off or {}).get("mode")
    row["changed"] = bool(off and on and (off["verdict"], off["reason_codes"]) != (on["verdict"], on["reason_codes"]))
    row["downgraded_by_filter"] = bool(off and on and off["verdict"] == REACHABLE and on["verdict"] == CANT_DETERMINE
                                       and PATHS_INFEASIBLE in on["reason_codes"])
    row["filter"] = (on or {}).get("feasibility")
    row["reachable_entries"] = entry_facts(on) if on else []
    row["filter_statuses"] = dict(Counter(x["status"] for x in row["reachable_entries"]))
    row["seconds_off"] = (off_row or {}).get("case_seconds")
    row["seconds_on"] = (on_row or {}).get("case_seconds")
    row["harness_error"] = (off_row or {}).get("harness_error") or (off_row or {}).get("app_prep_error") or \
        (on_row or {}).get("harness_error") or (on_row or {}).get("app_prep_error")
    return row


def stable(v: dict[str, Any]) -> Any:
    """What must be equal for a reproduction: verdict, reasons and every entry's result, reason,
    method results and verified path (timings, provenance and the run environment excluded)."""
    return [v["verdict"], v["reason_codes"],
            [[e.get("main_package"), e["target"], e["result"], e["reason_code"], e["methods"], e.get("verified_path")]
             for e in v["per_symbol"]]]


def reproduce_cp7b(off_verdicts: dict[str, dict[str, Any]], gomodcache: Path, goroot: str | None) -> dict[str, Any]:
    from vulntrace.d3 import triage_run as tr

    out = {"compared": 0, "identical": [], "different": [], "missing": []}
    for p in sorted((CP7B / "verdicts").glob("*.json")):
        cid = p.stem
        committed = json.loads(p.read_text(encoding="utf-8"))
        if cid not in off_verdicts:
            out["missing"].append(cid)
            continue
        out["compared"] += 1
        mine = tr.sanitise(off_verdicts[cid], gomodcache, goroot)
        if stable(mine) == stable(committed):
            out["identical"].append(cid)
        else:
            a, b = stable(mine), stable(committed)
            out["different"].append({"id": cid, "off": a[:2], "committed": b[:2],
                                     "entries_differ": a[2] != b[2]})
    out["all_identical"] = not out["different"] and not out["missing"] and out["compared"] > 0
    return out


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ran = [r for r in rows if r["verdict_off"] and r["verdict_on"]]
    entries = [x for r in ran for x in r["reachable_entries"]]
    return {
        "cases": len(rows), "triaged_both": len(ran),
        "verdicts_off": dict(Counter(r["verdict_off"] for r in ran)),
        "verdicts_on": dict(Counter(r["verdict_on"] for r in ran)),
        "reachable_off": sum(1 for r in ran if r["verdict_off"] == REACHABLE),
        "downgraded_cases": [r["id"] for r in ran if r["downgraded_by_filter"]],
        "other_changes": [r["id"] for r in ran if r["changed"] and not r["downgraded_by_filter"]],
        "reachable_entries": len(entries),
        "entry_statuses": dict(Counter(x["status"] for x in entries)),
        "deciding_patterns_of_infeasible_entries": dict(Counter(x["deciding_pattern"] for x in entries
                                                                if x["status"] == fz.INFEASIBLE)),
        "patterns_on_examined_paths": dict(Counter(p for x in entries for p in x["first_patterns"])),
        "undecided_reasons": dict(Counter(x["undecided_reason"] for x in entries if x["status"] == fz.UNDECIDED)),
    }


def _link(shared: Path, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in ("apps", "evidence"):
        (shared / name).mkdir(parents=True, exist_ok=True)
        link = run_dir / name
        if not link.exists():
            os.symlink(shared / name, link)


def run_d3_both(args, binary, off_factory, on_factory, feas, env, set_name: str, case_path: Path,
                data_dir: Path) -> tuple[dict[str, Any], dict[str, dict], dict[str, dict]]:
    from vulntrace.d3 import triage_run as tr
    from vulntrace.dataset import vulndb
    from vulntrace.eval.lift_cli import default_gomodcache
    from vulntrace.pipeline.cli import repo_commit

    case_doc = json.loads(case_path.read_text(encoding="utf-8"))
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    tr.setup_env(gomodcache)
    by_id = {c["id"]: c for c in cases}
    docs, verdicts = {}, {}
    for label, factory in (("off", off_factory), ("on", on_factory)):
        run_dir = data_dir / label
        _link(data_dir / "shared", run_dir)
        _log(f"== {set_name}: filter {label}")
        docs[label], verdicts[label] = tr.eval_d3(
            case_doc, cases_by_id=by_id, data_dir=run_dir, gomodcache=gomodcache, cache_root=gomodcache.parent,
            base=factory(), binary=binary, vulndb_commit=vulndb.pinned_commit(), repo_commit=repo_commit(),
            gv_exe=None, gv_db=None, only=args.only, rerun=args.rerun, log=_log)
    off_rows = {r["id"]: r for r in docs["off"]["rows"]}
    on_rows = {r["id"]: r for r in docs["on"]["rows"]}
    rows = [case_row(c["id"], verdicts["off"].get(c["id"]), verdicts["on"].get(c["id"]), off_rows.get(c["id"]),
                     on_rows.get(c["id"])) for c in case_doc["cases"] if not args.only or c["id"] in args.only]
    root = tr.goroot()
    doc = {"schema_version": SCHEMA_VERSION, "set": set_name, "feasibility_settings": feas, "rows": rows,
           "summary": summary(rows), "environment": env,
           "toolchain": {"off": docs["off"]["summary"]["toolchain"], "on": docs["on"]["summary"]["toolchain"]},
           "env": docs["on"]["env"], "max_mains": docs["on"]["max_mains"], "mode2_policy": docs["on"]["mode2_policy"],
           "seconds_per_case": {"off": docs["off"]["summary"]["seconds_per_case"],
                                "on": docs["on"]["summary"]["seconds_per_case"]},
           "verdict_provenance": {"off": docs["off"]["verdict_provenance"], "on": docs["on"]["verdict_provenance"]},
           "govulncheck": "not run in CP9 (reference only; CP7b recorded it for D3)",
           "statement": "REACHABLE means reachable in the call graph from a main package, not exploitable. The filter "
                        "only turns REACHABLE into CANT_DETERMINE (PATHS_INFEASIBLE)."}
    if set_name == "d3":
        doc["label"] = IN_SAMPLE_LABEL
        doc["cp7b_reproduction"] = reproduce_cp7b(verdicts["off"], gomodcache, root)
        doc["cp7b_adjudication"] = _cp7b_adjudication()
    if args.only:
        doc["partial_run"] = {"only": args.only}
    sanitised = {label: {cid: tr.sanitise(v, gomodcache, root) for cid, v in verdicts[label].items()}
                 for label in verdicts}
    return tr.sanitise(doc, gomodcache, root), sanitised["off"], sanitised["on"]


def _cp7b_adjudication() -> dict[str, Any]:
    sheet = json.loads((CP7B / "adjudication" / "adjudication.json").read_text(encoding="utf-8"))
    return {c["id"]: {"adjudication": c.get("adjudication"), "truth": c.get("truth")} for c in sheet["cases"]}


def cmd(args, argv, binary, off_factory, on_factory, feas, env, out_dir: Path) -> int:
    from vulntrace.dataset import vulndb

    if not vulndb.is_up_to_date(Path(args.cache) if args.cache else None):
        print("missing prerequisite: the pinned vulndb snapshot (run `python -m vulntrace dataset fetch`)")
        return EXIT_MISSING_PREREQUISITE
    if args.dataset_set in ("d3", "d3b"):
        if args.dataset_set == "d3":
            case_path = Path(args.cases) if args.cases else CP7B / "d3_cases.json"
        else:
            case_path = Path(args.cases) if args.cases else out_dir / "d3b" / "d3_cases.json"
        if not case_path.is_file():
            print(f"missing prerequisite: {case_path}")
            return EXIT_MISSING_PREREQUISITE
        data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR / "cp9" / args.dataset_set
        doc, off_v, on_v = run_d3_both(args, binary, off_factory, on_factory, feas, env, args.dataset_set,
                                       case_path, data_dir)
        base = out_dir / args.dataset_set
        gz = []
        for label, vs in (("off", off_v), ("on", on_v)):
            for cid, v in sorted(vs.items()):
                name = write_verdict(base / f"verdicts_{label}", cid,
                                     compact_for_commit(v, off_v.get(cid) if label == "on" else None))
                if name.endswith(".gz"):
                    gz.append(f"verdicts_{label}/{name}")
        doc["verdict_files_gzipped"] = gz
        _write(base / f"{args.dataset_set}_feasibility.json", doc)
        return EXIT_OK
    from vulntrace.eval import feasibility_dist as fd

    return fd.cmd(args, argv, binary, off_factory, on_factory, feas, env, out_dir)
