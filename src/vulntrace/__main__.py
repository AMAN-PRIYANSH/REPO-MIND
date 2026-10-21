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
    sc.add_argument("--method", required=True, choices=["linker", "vta", "naive", "combined"])
    sc.add_argument("--out", default=None,
                    help="output directory (default: results/cp1 for linker, results/cp2 otherwise)")
    sc.add_argument("--timeout", type=float, default=300.0, help="helper timeout per case in seconds (default 300)")
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
    rr.add_argument("--doc", required=True, choices=["cp1", "cp2", "cp3"])
    rr.add_argument("--input", required=True,
                    help="cp1: linker score JSON; cp2/cp3: directory with the relevant score JSON files")
    rr.add_argument("--out", required=True, help="Markdown file to write")

    ds = sub.add_parser("dataset", help="D1/D4 dataset construction (CP3)")
    dsub = ds.add_subparsers(dest="dataset_command", required=True)
    dfetch = dsub.add_parser("fetch", help="fetch the pinned golang/vulndb snapshot (uses the network)")
    dfetch.add_argument("--cache", default=None, help="cache directory (default: ~/.cache/vulntrace/vulndb-src)")
    dbuild = dsub.add_parser("build", help="build D1 (fix evidence) or D4 (release ranges); uses the network")
    dbuild.add_argument("--mode", required=True, choices=["fix", "release"])
    dbuild.add_argument("--seed", type=int, default=None, help="sampling seed (default: a fixed project constant)")
    dbuild.add_argument("--target", type=int, default=None, help="sample size (default: 150 for fix, 120 for release)")
    dbuild.add_argument("--out", default=None, help="docs/results/datasets/ output path (default: D1/D4_cases.json)")
    dbuild.add_argument("--cache", default=None, help="vulndb cache directory")
    dbuild.add_argument("--repo-cache", default=None, help="cache directory for fetched third-party repositories")

    dmat = dsub.add_parser("materialize", help="rebuild bulky D4 evidence into data/ from the committed case list "
                                               "(never re-selects cases; uses the network; resumable)")
    dmat.add_argument("--set", required=True, choices=["d4", "d1"], dest="dataset_set")
    dmat.add_argument("--cases", default=None, help="case list (default: docs/results/datasets/D4|D1_cases.json)")
    dmat.add_argument("--data-dir", default=None, help="output data directory (default: data/)")
    dmat.add_argument("--cache", default=None, help="vulndb cache directory")
    dmat.add_argument("--repo-cache", default=None, help="cache directory for fetched third-party repositories")
    dmat.add_argument("--delay", type=float, default=1.0, help="seconds to wait between cases that fetch (default 1)")
    dmat.add_argument("--summary-out", default=None,
                      help="where to write the run summary (default: docs/results/datasets/D4|D1_materialize.json)")

    ev = sub.add_parser("eval", help="baselines and evaluation (CP3+)")
    esub = ev.add_subparsers(dest="eval_command", required=True)
    es = esub.add_parser("symbols", help="symbol-identification baselines")
    es.add_argument("--strategy", required=True, choices=["e0", "id-search"])
    es.add_argument("--cases", default=None, help="D1/D4 case-list JSON (default: docs/results/datasets/D1|D4_cases.json)")
    es.add_argument("--cache", default=None, help="vulndb cache directory")
    es.add_argument("--out", default=None, help="output directory (default: results/cp3)")
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

    if not Path(args.input).exists():
        print(f"error: no such report file or directory: {args.input}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(args.doc, Path(args.input)), encoding="utf-8")
    print(f"wrote {out}")
    return EXIT_OK


def _cmd_dataset(args) -> int:
    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import datasets, vulndb
    from vulntrace.methods.helper import HelperError, ensure_helper

    cache = Path(args.cache) if args.cache else None
    if args.dataset_command == "fetch":
        try:
            path = vulndb.ensure_vulndb_snapshot(cache)
        except vulndb.VulndbError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_MISSING_PREREQUISITE
        print(f"vulndb snapshot ready at {path} (pinned commit {vulndb.pinned_commit()})")
        return EXIT_OK

    if shutil.which("go") is None or shutil.which("git") is None:
        print("error: go toolchain and git are both required (run `python -m vulntrace doctor`)", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    try:
        binary = ensure_helper()
        vulndb.ensure_vulndb_snapshot(cache)
    except (HelperError, vulndb.VulndbError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    cases, parse_errors = datasets.load_all_cases(cache)
    if parse_errors:
        print(f"warning: {parse_errors} report(s) failed to parse (counted, not dropped silently)", file=sys.stderr)
    repo_cache = Path(args.repo_cache) if args.repo_cache else None
    if args.dataset_command == "materialize":
        return _cmd_materialize(args, cases, binary, repo_cache)
    seed = args.seed if args.seed is not None else dataset_build.DEFAULT_SEED

    def progress(i, n, result):
        print(f"{i}/{n} {result['status']} candidates={len(result['candidates'])}", file=sys.stderr)

    if args.mode == "fix":
        target = args.target or datasets.D1_TARGET
        summary = dataset_build.build_d1(cases, binary, cache_root=repo_cache, seed=seed, target=target,
                                         progress=progress)
        out = Path(args.out) if args.out else dataset_build.RESULTS_DATASETS_DIR / "D1_cases.json"
    else:
        target = args.target or datasets.D4_TARGET
        summary = dataset_build.build_d4(cases, binary, cache_root=repo_cache, seed=seed, target=target,
                                         progress=progress)
        out = Path(args.out) if args.out else dataset_build.RESULTS_DATASETS_DIR / "D4_cases.json"
    dataset_build.write_case_list(summary, out)
    print(f"{summary['dataset']}: {summary['sample_count']} cases (eligible {summary['eligible_count']}), "
         f"status counts {summary['status_counts']}")
    print(f"wrote {out}")
    return EXIT_OK


def _cmd_materialize(args, cases, binary, repo_cache) -> int:
    import json

    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import materialize

    name = args.dataset_set.upper()
    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / f"{name}_cases.json"
    if not case_list_path.is_file():
        print(f"error: no such case list: {case_list_path}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    case_list = json.loads(case_list_path.read_text(encoding="utf-8"))
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR

    def progress(i, n, case_id, what):
        print(f"{i}/{n} {case_id} {what}", file=sys.stderr, flush=True)

    fn = materialize.materialize_d4 if args.dataset_set == "d4" else materialize.materialize_d1
    summary = fn(case_list, {c["id"]: c for c in cases}, binary, data_dir=data_dir, cache_root=repo_cache,
                 delay_s=args.delay, progress=progress)
    out = (Path(args.summary_out) if args.summary_out
           else dataset_build.RESULTS_DATASETS_DIR / f"{name}_materialize.json")
    dataset_build.write_case_list(summary, out)
    print(f"{name} materialize: {summary['case_count']} cases in {summary['wall_seconds']}s; "
          f"actions {summary['action_counts']}; status counts {summary['status_counts']} "
          f"(case list: {summary['expected_status_counts']}); {len(summary['differences'])} case(s) differ")
    for d in summary["differences"]:
        print(f"  DIFFERS {d['id']}: {'; '.join(d['differences'])}")
    print(f"wrote {out}")
    return EXIT_OK


def _cmd_eval_symbols(args) -> int:
    from vulntrace.dataset import datasets
    from vulntrace.dataset.build import RESULTS_DATASETS_DIR
    from vulntrace.eval import symbols_score

    cache = Path(args.cache) if args.cache else None
    default_cases = RESULTS_DATASETS_DIR / ("D1_cases.json" if args.strategy == "e0" else "D4_cases.json")
    case_list_path = Path(args.cases) if args.cases else default_cases
    if not case_list_path.is_file():
        print(f"error: no such case list: {case_list_path} (run `python -m vulntrace dataset build` first)",
              file=sys.stderr)
        return EXIT_INVALID_INPUT
    cases, _ = datasets.load_all_cases(cache)
    cases_by_id = {c["id"]: c for c in cases}
    out_dir = Path(args.out) if args.out else Path("results/cp3")
    if args.strategy == "e0":
        report = symbols_score.score_e0(case_list_path, cases_by_id)
    else:
        report = symbols_score.score_id_search(case_list_path, cases_by_id)
    jp, _ = symbols_score.write_score(report, out_dir)
    s = report["summary_core"]
    exact_match = sum(1 for r in report["rows"] if r["core"] and r["core"]["exact_match"])
    print(f"{report['strategy']} on {report['dataset']}: {report['scored_count']}/{report['case_count']} scored")
    print(f"precision={s['precision']['mean']:.3f} recall={s['recall']['mean']:.3f} f1={s['f1']['mean']:.3f} "
         f"exact_match={exact_match}")
    print(f"wrote {jp}")
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
    if args.method == "linker":
        report = score_linker(fixtures_dir, compare_inlining=args.compare_inlining)
        report["run"] = run_info(argv)
        jp, mp = write_report(report, Path(args.out or "results/cp1"))
        md = render_markdown(report)
    else:
        from vulntrace.eval import callgraph_score as cs
        from vulntrace.methods.helper import HelperError, ensure_helper

        if args.compare_inlining:
            print("error: --compare-inlining applies to --method linker only", file=sys.stderr)
            return EXIT_INVALID_INPUT
        try:
            binary = ensure_helper()
        except HelperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_MISSING_PREREQUISITE
        if args.method == "combined":
            report = cs.score_combined(fixtures_dir, binary=binary, timeout=args.timeout)
        else:
            method = cs.VTA_METHOD if args.method == "vta" else cs.NAIVE_METHOD
            report = cs.score_callgraph(fixtures_dir, method, binary=binary, timeout=args.timeout)
        report["run"] = run_info(argv)
        jp, mp = cs.write_score(report, Path(args.out or "results/cp2"))
        md = cs.render_markdown(report)
    c = report["counts"]
    print(md)
    print(f"false_not_reachable={c['false_not_reachable']} false_reachable={c['false_reachable']} "
          f"agreements={c['agreements']} cant_determine={c.get('cant_determine', 0)} errors={c['errors']} "
          f"(of {c['cases']} cases)")
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
        if args.command == "dataset":
            return _cmd_dataset(args)
        if args.command == "eval" and args.eval_command == "symbols":
            return _cmd_eval_symbols(args)
    except Exception as exc:  # unexpected
        print(f"unexpected error: {exc!r}", file=sys.stderr)
        return EXIT_UNEXPECTED
    return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
