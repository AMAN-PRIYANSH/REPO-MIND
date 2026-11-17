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
