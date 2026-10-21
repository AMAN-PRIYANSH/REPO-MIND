"""Command-line entry point: python -m vulntrace <command>."""

import argparse
import shutil
import sys
from pathlib import Path

from vulntrace.paths import FIXTURES_DIR

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 1, 2, 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vulntrace")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="report Python, Go, Docker and tool versions")
    fx = sub.add_parser("fixtures", help="synthetic reachability suite")
    fsub = fx.add_subparsers(dest="fixtures_command", required=True)
    sc = fsub.add_parser("score", help="run a method over the suite and write a scored report")
    sc.add_argument("--method", required=True, choices=["linker"])
    sc.add_argument("--out", default="results/cp1", help="output directory (default: results/cp1)")
    sc.add_argument("--fixtures-dir", default=str(FIXTURES_DIR))
    sc.add_argument("--compare-inlining", action="store_true",
                    help="also build without -gcflags=all=-l and report both (not used for scoring)")
    hp = sub.add_parser("helper", help="the Go analysis helper vt-helper")
    hsub = hp.add_subparsers(dest="helper_command", required=True)
    hsub.add_parser("build", help="build vt-helper into the cache (offline) and print its path")
    hsub.add_parser("fetch", help="download the helper's Go dependencies (uses the network; run once)")
    rs = sub.add_parser("results", help="committed results documents")
    rsub = rs.add_subparsers(dest="results_command", required=True)
    rr = rsub.add_parser("render", help="generate a docs/results/ document from a score report file")
    rr.add_argument("--doc", required=True, choices=["cp1"])
    rr.add_argument("--input", required=True, help="score report JSON written by `fixtures score`")
    rr.add_argument("--out", required=True, help="Markdown file to write")
    return p


def _cmd_doctor() -> int:
    from vulntrace.env import run_doctor

    rep = run_doctor()
    print("\n".join(rep.lines))
    return rep.exit_code


def _cmd_helper(args) -> int:
    from vulntrace.methods.helper import HelperError, ensure_helper, fetch_helper_modules

    if shutil.which("go") is None:
        print("error: go toolchain not found (run `python -m vulntrace doctor`)", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    if args.helper_command == "fetch":
        p = fetch_helper_modules()
        print((p.stdout + p.stderr).strip() or "helper modules downloaded")
        return EXIT_OK if p.returncode == 0 else EXIT_MISSING_PREREQUISITE
    try:
        print(ensure_helper())
    except HelperError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    return EXIT_OK


def _cmd_render(args) -> int:
    from vulntrace.eval.results_doc import render

    if not Path(args.input).is_file():
        print(f"error: no such report file: {args.input}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(args.doc, Path(args.input)), encoding="utf-8")
    print(f"wrote {out}")
    return EXIT_OK


def _cmd_score(args, argv: list[str]) -> int:
    from vulntrace.eval.fixture_score import render_markdown, score_linker, write_report
    from vulntrace.eval.run_info import run_info

    fixtures_dir = Path(args.fixtures_dir)
    if not (fixtures_dir / "manifest.json").is_file():
        print(f"error: no manifest.json in {fixtures_dir}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    if shutil.which("go") is None:
        print("error: go toolchain not found (run `python -m vulntrace doctor`)", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    report = score_linker(fixtures_dir, compare_inlining=args.compare_inlining)
    report["run"] = run_info(argv)
    jp, mp = write_report(report, Path(args.out))
    c = report["counts"]
    print(render_markdown(report))
    print(f"agreements={c['agreements']} false_not_reachable={c['false_not_reachable']} "
          f"false_reachable={c['false_reachable']} errors={c['errors']} (of {c['cases']} cases)")
    print(f"wrote {jp} and {mp}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_INVALID_INPUT if exc.code not in (0, None) else EXIT_OK
    try:
        if args.command == "doctor":
            return _cmd_doctor()
        if args.command == "fixtures" and args.fixtures_command == "score":
            return _cmd_score(args, argv)
        if args.command == "helper":
            return _cmd_helper(args)
        if args.command == "results" and args.results_command == "render":
            return _cmd_render(args)
    except Exception as exc:  # unexpected
        print(f"unexpected error: {exc!r}", file=sys.stderr)
        return EXIT_UNEXPECTED
    return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
