"""`python -m vulntrace eval triage --set fixtures|d1|d4` (CP7 deliverable 4)."""

import json
import os
import sys
import tempfile
from pathlib import Path

from vulntrace.dataset import build as dataset_build
from vulntrace.dataset import datasets
from vulntrace.eval import triage_eval as te
from vulntrace.eval.lift_cli import default_gomodcache
from vulntrace.eval.run_info import run_info
from vulntrace.methods.helper import HelperError, ensure_helper
from vulntrace.paths import REPO_ROOT

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 1, 2, 3
MAX_RESULT_BYTES = 512 * 1024
DEFAULT_OUT = REPO_ROOT / "docs" / "results" / "cp7"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _write(path: Path, obj) -> int:
    n = te.write_json(path, obj)
    if n > MAX_RESULT_BYTES:
        _log(f"error: {path} is {n} bytes, over the 512 KiB limit for committed results")
        raise SystemExit(EXIT_UNEXPECTED)
    _log(f"wrote {path} ({n} bytes)")
    return n


def cmd_eval_triage(args, argv) -> int:
    from vulntrace.pipeline.cli import default_runners

    try:
        binary = ensure_helper()
    except HelperError as exc:
        print(f"missing prerequisite: {exc.code}: {exc.message}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    def factory():
        return default_runners(args.timeout, args.build_timeout, binary)

    env = run_info(["eval", "triage", *argv[2:]] if argv[:2] == ["eval", "triage"] else argv)
    if args.dataset_set == "fixtures":
        with tempfile.TemporaryDirectory(prefix="vt_cp7_fixtures_") as tmp:
            doc = te.eval_fixtures(factory, Path(tmp), binary, log=_log)
        doc["environment"] = env
        _write(out_dir / "fixtures.json", doc)
    else:
        name = "D1_cases.json" if args.dataset_set == "d1" else "D4_cases.json"
        case_list = json.loads(Path(args.cases or dataset_build.RESULTS_DATASETS_DIR / name).read_text(encoding="utf-8"))
        cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
        if not cases:
            print("missing prerequisite: no vulndb snapshot (run `python -m vulntrace dataset fetch`)", file=sys.stderr)
            return EXIT_MISSING_PREREQUISITE
        data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
        gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
        gomodcache.mkdir(parents=True, exist_ok=True)
        os.environ["GOMODCACHE"] = str(gomodcache)   # `go mod tidy`, the helper, `go build` and `go list` share it
        os.environ["GOWORK"] = "off"
        doc = te.eval_real(args.dataset_set, case_list, {c["id"]: c for c in cases}, data_dir,
                           base_factory=factory, repo_cache=Path(args.repo_cache) if args.repo_cache else None,
                           gomodcache=gomodcache, jobs=args.jobs, max_mains=args.max_mains or te.EVAL_MAX_MAINS,
                           limit=args.limit, only=args.only, rerun=args.rerun, log=_log)
        doc["environment"] = env
        doc["environment"]["gomodcache_note"] = "a shared module cache; first-time downloads dominate preparation time"
        if args.limit or args.only:
            doc["partial_run"] = {"limit": args.limit, "only": args.only}
        _write(out_dir / f"{args.dataset_set}.json", doc)
        for cid in args.example or []:
            p = data_dir / "triage" / args.dataset_set / f"{cid}.verdict.json.gz"
            if p.is_file():
                _write(out_dir / "examples" / f"{args.dataset_set}_{cid}.verdict.json", te.example_verdict(te._read_gz(p)))
            else:
                _log(f"no verdict for example {cid}")
    fx, d4 = out_dir / "fixtures.json", out_dir / "d4.json"
    if fx.is_file() and d4.is_file():
        pol = te.decide_mode2_policy(json.loads(fx.read_text(encoding="utf-8"))["rows"],
                                     json.loads(d4.read_text(encoding="utf-8"))["rows"])
        _write(out_dir / "mode2_policy.json", pol)
    return EXIT_OK
