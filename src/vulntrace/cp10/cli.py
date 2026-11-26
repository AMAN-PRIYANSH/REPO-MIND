"""`python -m vulntrace cp10 select|run|sheet|report` (CP10)."""

import json
import sys
import tempfile
from pathlib import Path

from vulntrace.paths import REPO_ROOT

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 1, 2, 3
RESULTS = REPO_ROOT / "docs" / "results" / "cp10"
DATA = REPO_ROOT / "data" / "cp10"
MAX_RESULT_BYTES = 512 * 1024


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def write_result(path: Path, obj) -> int:
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    n = len(text.encode("utf-8"))
    if n > MAX_RESULT_BYTES:
        raise SystemExit(f"error: {path} would be {n} bytes, over the 512 KiB limit for committed results")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _log(f"wrote {path} ({n} bytes)")
    return n


def add_parser(sub) -> None:
    cp = sub.add_parser("cp10", help="CP10: verdict-level trust against govulncheck (D3c), target hygiene, evidence labels")
    csub = cp.add_subparsers(dest="cp10_command", required=True)
    sel = csub.add_parser("select", help="apply the written D3c rules (docs/evaluation/D3C_SELECTION_RULES.md); network")
    sel.add_argument("--candidates", default=None, help="default: docs/evaluation/d3c_candidates.json")
    sel.add_argument("--out", default=None, help="default: docs/results/cp10/d3c")
    sel.add_argument("--cache", default=None, help="cache root for git repositories")
    sel.add_argument("--vulndb-cache", default=None)
    sel.add_argument("--work", default=None, help="where application trees are extracted (default: data/cp10/d3c/shared/apps)")
    sel.add_argument("--gomodcache", default=None)
    run = csub.add_parser("run", help="triage with CP10 target hygiene and with --legacy-targets (+ govulncheck)")
    run.add_argument("--set", required=True, choices=["fixtures", "d3", "d3b", "d3c"], dest="dataset_set")
    run.add_argument("--out", default=None, help="default: docs/results/cp10")
    run.add_argument("--data-dir", default=None, help="working data (default: data/cp10/<set>)")
    run.add_argument("--cache", default=None, help="vulndb cache directory")
    run.add_argument("--gomodcache", default=None)
    run.add_argument("--only", action="append", default=None, help="only this case id (repeatable; a partial run)")
    run.add_argument("--rerun", action="store_true", help="recompute cases that already have results")
    run.add_argument("--no-govulncheck", action="store_true")
    run.add_argument("--max-examined-paths", type=int, default=20)
    run.add_argument("--timeout", type=float, default=600.0)
    run.add_argument("--build-timeout", type=float, default=900.0)
    sh = csub.add_parser("sheet", help="verdict-level adjudication sheets (D3c: every case; D3/D3b: truth-only items)")
    sh.add_argument("--out", default=None, help="default: docs/results/cp10/adjudication")
    sh.add_argument("--data-dir", default=None, help="working data (default: data/cp10), for source lines")
    sh.add_argument("--gomodcache", default=None)
    sh.add_argument("--force", action="store_true", help="overwrite a sheet that already has answers")
    rp = csub.add_parser("report", help="score the filled sheets and render docs/results/CP10_VERDICT_RESULTS.md")
    rp.add_argument("--out", default=None)
    rp.add_argument("--allow-unfilled", action="store_true",
                    help="render with blank adjudication (a preview; the headline then says the sheet is not filled)")


def _gomodcache(args) -> Path:
    from vulntrace.eval.lift_cli import default_gomodcache

    return Path(args.gomodcache) if getattr(args, "gomodcache", None) else default_gomodcache()


def cmd_select(args, argv) -> int:
    from vulntrace.d3 import select as sl
    from vulntrace.d3.cli import default_cache
    from vulntrace.dataset import vulndb
    from vulntrace.eval.run_info import run_info

    cfg_path = Path(args.candidates) if args.candidates else sl.D3C_CANDIDATES_PATH
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    cache = Path(args.cache) if args.cache else default_cache()
    gomodcache = _gomodcache(args)
    work = Path(args.work) if args.work else DATA / "d3c" / "shared" / "apps"
    vcache = Path(args.vulndb_cache) if args.vulndb_cache else None
    if not vulndb.is_up_to_date(vcache):
        _log("error: the pinned vulndb snapshot is missing; run `python -m vulntrace dataset fetch` first")
        return EXIT_MISSING_PREREQUISITE
    probe = sl.Probe(cache_root=cache, work_root=work, gomodcache=gomodcache, log=_log)
    toolchain = probe.toolchain()
    if not toolchain:
        _log("error: `go env GOVERSION` failed; Go is needed")
        return EXIT_MISSING_PREREQUISITE
    index = sl.advisory_index_strata(vcache)
    n_s = sum(1 for v in index.values() for e in v if e["stratum"] == sl.STRATUM_S)
    n_n = sum(1 for v in index.values() for e in v if e["stratum"] == sl.STRATUM_N)
    _log(f"toolchain {toolchain}; vulndb {vulndb.pinned_commit()[:12]}; {len(config['candidates'])} candidates; "
         f"index: {n_s} S and {n_n} N module entries over {len(index)} modules")
    res = sl.select_d3c(config, index, probe, toolchain, log=_log)
    note = sl.diversity_note(res["kept"])
    out = Path(args.out) if args.out else RESULTS / "d3c"
    common = {"schema_version": sl.SCHEMA_VERSION, "rules": sl.D3C_RULES_DOC, "candidates_file": cfg_path.name,
              "toolchain": toolchain, "vulndb_commit": vulndb.pinned_commit(), "run": run_info(argv),
              "env": {"GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOFLAGS": "-mod=readonly"}}
    counts: dict[str, int] = {}
    for r in res["records"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    write_result(out / "d3c_selection.json", {
        **common, "seed": config["seed"], "pin_cutoff": config["pin_cutoff"], "status_counts": counts,
        "diversity_note": note, "totals": res["totals"], "quotas": {"S": config["quota_s"], "N": config["quota_n"],
                                                                    "min_apps": config["min_apps"], "max_apps": config["max_apps"]},
        "quotas_met": res["quotas_met"], "candidates_evaluated": res["candidates_evaluated"],
        "advisory_index": {"modules": len(index), "entries_S": n_s, "entries_N": n_n}, "candidates": res["records"]})
    cases = sl.case_list(res["kept"])
    write_result(out / "d3c_cases.json", {**common, "apps": len(res["kept"]), "case_count": len(cases),
                                          "totals": res["totals"], "cases": cases})
    print(json.dumps({"status_counts": counts, "apps": [r["repo"] for r in res["kept"]], "cases": len(cases),
                      "totals": res["totals"], "quotas_met": res["quotas_met"], "diversity": note}, indent=1))
    return EXIT_OK


def cmd_run(args, argv) -> int:
    from vulntrace.cp10 import run as r
    from vulntrace.d3 import govuln
    from vulntrace.d3 import triage_run as tr
    from vulntrace.dataset import datasets, vulndb
    from vulntrace.eval.run_info import run_info
    from vulntrace.methods.helper import HelperError, ensure_helper
    from vulntrace.pipeline import feasibility as fz
    from vulntrace.pipeline.cli import default_runners

    try:
        binary = ensure_helper()
    except HelperError as exc:
        _log(f"missing prerequisite: {exc.code}: {exc.message}")
        return EXIT_MISSING_PREREQUISITE
    out_dir = Path(args.out) if args.out else RESULTS
    env = run_info(argv)
    feas = fz.helper_settings(args.max_examined_paths, rank_evidence=True)
    if args.dataset_set == "fixtures":
        def legacy():   # the CP7 fixture pipeline: no filter; plus the CP10 evidence stage
            return default_runners(args.timeout, args.build_timeout, binary, None, evidence=True)

        with tempfile.TemporaryDirectory(prefix="vt_cp10_fixtures_") as tmp:
            doc = r.run_fixtures(legacy, legacy, Path(tmp), binary, log=_log)
        doc["environment"] = env
        write_result(out_dir / "fixtures.json", doc)
        return EXIT_OK
    case_path = r.case_paths(args.dataset_set)
    if not case_path.is_file():
        _log(f"missing prerequisite: {case_path}" + (" (run `python -m vulntrace cp10 select`)"
                                                       if args.dataset_set == "d3c" else ""))
        return EXIT_MISSING_PREREQUISITE
    vcache = Path(args.cache) if args.cache else None
    cases, _ = datasets.load_all_cases(vcache)
    if not cases:
        _log("missing prerequisite: no vulndb snapshot (run `python -m vulntrace dataset fetch`)")
        return EXIT_MISSING_PREREQUISITE
    gomodcache = _gomodcache(args)
    tr.setup_env(gomodcache)
    cache_root = gomodcache.parent
    gv_exe = gv_db = None
    if not args.no_govulncheck:
        gv_exe, err = govuln.ensure_govulncheck(cache_root / "tools", cache_root / "gomod-tools")
        if err:
            _log(f"govulncheck could not be built ({err}); the reference comparison is skipped")
        else:
            gv_db, err = govuln.ensure_db(cache_root / "osv-db" / vulndb.pinned_commit()[:12], vcache)
            if err:
                _log(f"govulncheck database could not be prepared ({err}); the reference comparison is skipped")
                gv_exe = None
    data_dir = Path(args.data_dir) if args.data_dir else DATA / args.dataset_set

    def factory():
        return default_runners(args.timeout, args.build_timeout, binary, feas, evidence=True)

    doc, hyg, leg = r.run_set(args.dataset_set, json.loads(case_path.read_text(encoding="utf-8")),
                              {c["id"]: c for c in cases}, data_dir=data_dir, gomodcache=gomodcache, factory=factory,
                              binary=binary, gv_exe=gv_exe, gv_db=gv_db, only=args.only, rerun=args.rerun, log=_log)
    doc["environment"] = env
    doc["feasibility_settings"] = feas
    r.write_set(args.dataset_set, doc, hyg, leg, out_dir, write_result)
    return EXIT_OK


def dispatch(args, argv) -> int:
    if args.cp10_command == "select":
        return cmd_select(args, argv)
    if args.cp10_command == "run":
        return cmd_run(args, argv)
    if args.cp10_command == "sheet":
        from vulntrace.cp10 import sheet

        return sheet.cmd_sheet(args, write_result, _log)
    if args.cp10_command == "report":
        from vulntrace.cp10 import report

        return report.cmd_report(args, _log)
    return EXIT_INVALID_INPUT
