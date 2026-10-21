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
    rr.add_argument("--doc", required=True, choices=["cp1", "cp2", "cp3", "cp4"])
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
    er = esub.add_parser("retrieval", help="Mode 2 retrieval evaluation on D4 (CP4)")
    er.add_argument("--config", action="append", required=True,
                    help="random | size | bid | bid-only | bm25 | dense:<e> | hybrid:<e> | hybrid+rerank:<e>+<r> "
                         "(repeatable; e.g. --config bm25 --config dense:bge-small)")
    er.add_argument("--variant", action="append", default=None,
                    help="chunk variant (repeatable; default: all of code_only, code+commits, code+commits_idmasked)")
    _add_eval_data_args(er)
    er.add_argument("--out", default=None, help="results directory (default: results/cp4)")
    er.add_argument("--replace-cases", action="store_true",
                    help="allow overwriting a cases.json in --out that differs from this run's evidence")

    ix = sub.add_parser("index", help="chunk, embed and store D4 candidates (CP4)")
    ixsub = ix.add_subparsers(dest="index_command", required=True)
    ib = ixsub.add_parser("build", help="embed every chunk (cached by content hash) and optionally store it in pgvector")
    ib.add_argument("--set", required=True, choices=["d4"], dest="dataset_set")
    ib.add_argument("--embedder", action="append", required=True, help="embedder alias (repeatable)")
    ib.add_argument("--variant", action="append", default=None, help="chunk variant (repeatable; default: all)")
    _add_eval_data_args(ib)
    return p


def _add_eval_data_args(sp) -> None:
    sp.add_argument("--cases", default=None, help="D4 case list (default: docs/results/datasets/D4_cases.json)")
    sp.add_argument("--data-dir", default=None, help="materialised evidence directory (default: data/)")
    sp.add_argument("--cache", default=None, help="vulndb cache directory")
    sp.add_argument("--embedding-cache", default=None, help="embedding cache directory (default: data/embeddings)")
    sp.add_argument("--device", default=None, help="model device, e.g. cuda or cpu (default: library default)")
    sp.add_argument("--store", choices=["memory", "pgvector"], default="memory", help="vector store backend")
    sp.add_argument("--dsn", default=None, help="PostgreSQL DSN for --store pgvector (default: $VULNTRACE_PG_DSN)")
    sp.add_argument("--allow-missing", action="store_true",
                    help="score cases without materialised evidence as misses instead of stopping")


def _load_eval_set(args):
    import json
    import os

    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import datasets
    from vulntrace.eval import retrieval as er

    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D4_cases.json"
    case_list = json.loads(case_list_path.read_text(encoding="utf-8"))
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
    ev_cases, ranges, notes = er.load_eval_set(case_list, {c["id"]: c for c in cases}, data_dir,
                                               allow_missing=args.allow_missing)
    store = None
    if args.store == "pgvector":
        from vulntrace.retrieval.pgvector_store import PgVectorStore

        store = PgVectorStore(args.dsn or os.environ.get("VULNTRACE_PG_DSN",
                                                         "postgresql://postgres:postgres@localhost:5432/postgres"))
    emb_cache = Path(args.embedding_cache) if args.embedding_cache else dataset_build.DATA_DIR / "embeddings"
    harness = er.Harness(ev_cases, ranges, embedding_cache_root=emb_cache, store=store, device=args.device,
                         log=lambda m: print(m, file=sys.stderr, flush=True))
    return ev_cases, ranges, notes, harness


def _cmd_eval_retrieval(args, argv) -> int:
    import json

    from vulntrace.eval import retrieval as er
    from vulntrace.retrieval.chunking import VARIANTS

    try:
        configs = [er.parse_config(c) for c in args.config]
    except er.HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    variants = args.variant or list(VARIANTS)
    bad = [v for v in variants if v not in VARIANTS]
    if bad:
        print(f"error: unknown variant(s) {bad}; expected {list(VARIANTS)}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        ev_cases, ranges, notes, harness = _load_eval_set(args)
    except er.HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    out = Path(args.out) if args.out else Path("results/cp4")
    cases_doc = er.cases_document(ev_cases, ranges, notes)
    existing = out / "cases.json"
    if existing.is_file() and not args.replace_cases:
        old = json.loads(existing.read_text(encoding="utf-8"))
        if old["cases"] != cases_doc["cases"]:
            print(f"error: {existing} was written from different evidence; runs would not be comparable. "
                  "Use a new --out directory, or --replace-cases (and re-run every config).", file=sys.stderr)
            return EXIT_INVALID_INPUT
    er.write_json(existing, cases_doc)
    env = er.environment(argv)
    done = set()
    for cfg in configs:
        for variant in (["-"] if cfg.text_free else variants):
            if (cfg.name, variant) in done:
                continue
            done.add((cfg.name, variant))
            run = harness.run(cfg, variant)
            run["environment"] = er.environment(argv) if cfg.embedder else env
            p = er.write_json(out / "runs" / er.run_file_name(cfg.name, run["variant"]), run)
            from vulntrace.eval.retrieval_report import Summaries

            sm = Summaries(cases_doc, [run]).summary(0)
            print(f"{cfg.name} [{run['variant']}]: R@1={sm['recall@1']['mean']:.3f} R@10={sm['recall@10']['mean']:.3f} "
                  f"MRR={sm['mrr']['mean']:.3f} (n={sm['mrr']['n']}, all scored cases) -> {p}", flush=True)
        if cfg.embedder and not any(c.embedder == cfg.embedder for c in configs[configs.index(cfg) + 1:]):
            harness.release_dense(cfg.embedder)
    return EXIT_OK


def _cmd_index_build(args) -> int:
    from vulntrace.eval import retrieval as er
    from vulntrace.retrieval.chunking import VARIANTS

    variants = args.variant or list(VARIANTS)
    try:
        _ev, ranges, _notes, harness = _load_eval_set(args)
    except er.HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    for alias in args.embedder:
        for v in variants:
            stats = harness.prepare_dense(alias, v, progress=lambda i, n: print(f"  {alias} {v}: {i}/{n}",
                                                                                    file=sys.stderr, flush=True))
            print(f"{alias} [{v}]: {stats} over {len(ranges)} ranges")
    return EXIT_OK


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
        if args.command == "eval" and args.eval_command == "retrieval":
            return _cmd_eval_retrieval(args, argv)
        if args.command == "index" and args.index_command == "build":
            return _cmd_index_build(args)
    except Exception as exc:  # unexpected
        print(f"unexpected error: {exc!r}", file=sys.stderr)
        return EXIT_UNEXPECTED
    return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
