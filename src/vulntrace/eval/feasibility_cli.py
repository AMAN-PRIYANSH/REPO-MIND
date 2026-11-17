"""`python -m vulntrace eval feasibility --set fixtures` (CP9 deliverable 4, fixtures part).

Results go to docs/results/cp9/ (each file under 512 KiB); local paths become `<local>`."""

import sys
import tempfile
from pathlib import Path

from vulntrace.eval import feasibility_eval as fe
from vulntrace.eval.run_info import run_info
from vulntrace.eval.triage_cli import EXIT_MISSING_PREREQUISITE, EXIT_OK, _log, _write
from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.paths import REPO_ROOT
from vulntrace.pipeline import feasibility as fz

DEFAULT_OUT = REPO_ROOT / "docs" / "results" / "cp9"


def cmd_eval_feasibility(args, argv) -> int:
    from vulntrace.pipeline.cli import default_runners

    try:
        binary = ensure_helper()
    except HelperError as exc:
        print(f"missing prerequisite: {exc.code}: {exc.message}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    feas = fz.helper_settings(args.max_examined_paths)
    env = run_info(["eval", "feasibility", *argv[2:]] if argv[:2] == ["eval", "feasibility"] else argv)

    def off():
        return default_runners(args.timeout, args.build_timeout, binary, None)

    def on():
        return default_runners(args.timeout, args.build_timeout, binary, feas)

    if args.dataset_set == "fixtures":
        with tempfile.TemporaryDirectory(prefix="vt_cp9_fixtures_") as tmp:
            doc = fe.eval_all_fixtures(off, on, Path(tmp), binary, log=_log)
        doc["environment"] = env
        doc["feasibility_settings"] = feas
        _write(out_dir / "fixtures.json", doc)
        return EXIT_OK
    from vulntrace.eval import feasibility_real as fr

    return fr.cmd(args, argv, binary, off, on, feas, env, out_dir)


def add_cp9_parser(sub) -> None:
    cp = sub.add_parser("cp9", help="CP9: D3b adjudication sheets and the results document")
    csub = cp.add_subparsers(dest="cp9_command", required=True)
    sh = csub.add_parser("sheet", help="adjudication sheets for D3b (every case REACHABLE in either run)")
    sh.add_argument("--results", default=None, help="D3b results directory (default: docs/results/cp9/d3b)")
    sh.add_argument("--data-dir", default=None, help="D3b working data (default: data/cp9/d3b), for the source lines")
    sh.add_argument("--gomodcache", default=None, help="Go module cache used by the run")
    sh.add_argument("--force", action="store_true", help="overwrite a sheet that already has answers")
    rp = csub.add_parser("report", help="render docs/results/CP9_FEASIBILITY_RESULTS.md")
    rp.add_argument("--out", default=None)


def cmd_cp9(args) -> int:
    import json

    from vulntrace.eval import feasibility_report as frep

    if args.cp9_command == "report":
        path = frep.write(Path(args.out) if args.out else frep.OUT)
        _log(f"wrote {path}")
        return EXIT_OK
    from vulntrace.d3 import select as sl
    from vulntrace.d3 import triage_run as tr
    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import datasets
    from vulntrace.eval import feasibility_sheet as fsh
    from vulntrace.eval.lift_cli import default_gomodcache

    results = Path(args.results) if args.results else DEFAULT_OUT / "d3b"
    existing = results / "adjudication" / "adjudication.json"
    if existing.is_file() and not args.force and any(c.get("filled") for c in json.loads(existing.read_text())["cases"]):
        _log(f"error: {existing} already has answers; refusing to overwrite")
        return 2
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR / "cp9" / "d3b"
    gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
    root = tr.goroot()
    summaries = {c["id"]: c["summary"] for c in datasets.load_all_cases()[0]}
    doc = json.loads((results / "d3b_feasibility.json").read_text(encoding="utf-8"))
    go_version = next(iter(doc["toolchain"]["on"].get("helper") or []), None)

    def roots_for(row):
        return {"app": sl.app_tree_dir(data_dir / "shared" / "apps", row["app_repo"], row["app_commit"]),
                "$GOMODCACHE": gomodcache, "$GOROOT": Path(root) if root else None}

    sheet = fsh.build(results, roots_for, go_version, summaries)
    _log(f"wrote {len(sheet['cases'])} case(s) to {results / 'adjudication'}")
    return EXIT_OK
