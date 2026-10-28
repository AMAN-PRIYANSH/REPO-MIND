"""`python -m vulntrace d3 ...` (CP7b): `select` (deliverable 1). The triage run is
`python -m vulntrace eval triage --set d3`."""

import json
import os
import sys
from pathlib import Path

from vulntrace.paths import REPO_ROOT

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 1, 2, 3
RESULTS_DIR = REPO_ROOT / "docs" / "results" / "cp7b"
DATA_DIR = REPO_ROOT / "data"
MAX_RESULT_BYTES = 512 * 1024


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def default_cache() -> Path:
    from vulntrace.dataset import git_fetch

    return git_fetch.default_cache_root().parent


def default_gomodcache() -> Path:
    from vulntrace.eval.lift_cli import default_gomodcache as d

    return d()


def add_parser(sub) -> None:
    d3 = sub.add_parser("d3", help="CP7b: real applications (D3)")
    dsub = d3.add_subparsers(dest="d3_command", required=True)
    sel = dsub.add_parser("select", help="apply the written D3 selection rules to the fixed candidate list "
                                         "(uses the network: git, Go module proxy)")
    sel.add_argument("--candidates", default=None, help="candidate list (default: docs/evaluation/d3_candidates.json)")
    sel.add_argument("--out", default=None, help="results directory (default: docs/results/cp7b)")
    sel.add_argument("--cache", default=None, help="cache root for git repositories (default: $VULNTRACE_CACHE)")
    sel.add_argument("--vulndb-cache", default=None, help="vulndb cache directory")
    sel.add_argument("--work", default=None, help="where application trees are extracted (default: data/d3/apps)")
    sel.add_argument("--gomodcache", default=None, help="Go module cache (default: <cache>/gomod)")


def write_result(path: Path, obj) -> int:
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    n = len(text.encode("utf-8"))
    if n > MAX_RESULT_BYTES:
        raise SystemExit(f"error: {path} would be {n} bytes, over the 512 KiB limit for committed results")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _log(f"wrote {path} ({n} bytes)")
    return n


def cmd_select(args, argv) -> int:
    from vulntrace.d3 import select as sl
    from vulntrace.dataset import vulndb
    from vulntrace.eval.run_info import run_info

    cfg_path = Path(args.candidates) if args.candidates else sl.CANDIDATES_PATH
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    cache = Path(args.cache) if args.cache else default_cache()
    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    work = Path(args.work) if args.work else DATA_DIR / "d3" / "apps"
    vcache = Path(args.vulndb_cache) if args.vulndb_cache else None
    if not vulndb.is_up_to_date(vcache):
        _log("error: the pinned vulndb snapshot is missing; run `python -m vulntrace dataset fetch` first")
        return EXIT_MISSING_PREREQUISITE
    probe = sl.Probe(cache_root=cache, work_root=work, gomodcache=gomodcache, log=_log)
    toolchain = probe.toolchain()
    if not toolchain:
        _log("error: `go env GOVERSION` failed; Go is needed")
        return EXIT_MISSING_PREREQUISITE
    _log(f"toolchain {toolchain}; vulndb {vulndb.pinned_commit()[:12]}; {len(config['candidates'])} candidates")
    index = sl.advisory_index(vcache)
    _log(f"V1: {sum(len(v) for v in index.values())} module entries of D1-eligible advisories over {len(index)} modules")
    res = sl.select(config, index, probe, toolchain, log=_log)
    note = sl.diversity_note(res["kept"])
    _log("diversity: " + note)
    out = Path(args.out) if args.out else RESULTS_DIR
    info = run_info(argv)
    common = {"schema_version": sl.SCHEMA_VERSION, "rules": sl.RULES_DOC, "candidates_file": cfg_path.name,
              "toolchain": toolchain, "vulndb_commit": vulndb.pinned_commit(), "run": info,
              "env": {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOFLAGS": "-mod=readonly"}}
    counts: dict[str, int] = {}
    for r in res["records"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    write_result(out / "d3_selection.json", {**common, "seed": config["seed"], "pin_cutoff": config["pin_cutoff"],
                                             "status_counts": counts, "diversity_note": note,
                                             "advisory_index": {"modules": len(index),
                                                                "entries": sum(len(v) for v in index.values())},
                                             "candidates": res["records"]})
    cases = sl.case_list(res["kept"])
    write_result(out / "d3_cases.json", {**common, "apps": len(res["kept"]), "case_count": len(cases), "cases": cases})
    print(json.dumps({"status_counts": counts, "apps": [r["repo"] for r in res["kept"]], "cases": len(cases),
                      "diversity": note}, indent=1))
    return EXIT_OK


def dispatch(args, argv) -> int:
    if args.d3_command == "select":
        return cmd_select(args, argv)
    return EXIT_INVALID_INPUT
