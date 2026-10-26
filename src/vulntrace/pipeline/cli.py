"""`python -m vulntrace triage --advisory <ID> --app <dir> [--mode auto|fix|release]`: one verdict JSON."""

import json
import sys
from functools import partial
from pathlib import Path
from typing import Any

from vulntrace.methods.helper import DEFAULT_TIMEOUT_S, HelperError, ensure_helper
from vulntrace.pipeline import aggregate, analyse as an, app as app_mod, inputs, triage
from vulntrace.schemas import validation_errors

EXIT_OK, EXIT_UNEXPECTED, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 1, 2, 3


def add_parser(sub) -> None:
    tr = sub.add_parser("triage", help="CP7: full pipeline on one advisory and one app; prints one verdict JSON "
                                       "(reachability only, never exploitability)")
    src = tr.add_mutually_exclusive_group(required=True)
    src.add_argument("--advisory", help="advisory ID in the pinned vulndb snapshot (run `dataset fetch` once)")
    src.add_argument("--advisory-file", help="a VulnCase JSON file instead of the vulndb snapshot")
    tr.add_argument("--app", required=True, help="the Go module (directory with go.mod) to triage")
    tr.add_argument("--mode", default="auto", choices=["auto", "fix", "release", "targets"],
                    help="auto: Mode 1 when a fix commit is known, else Mode 2 (default)")
    tr.add_argument("--target", action="append", default=None,
                    help="targets mode: <package>:<symbol>, repeatable (for example vtfixtures/vulnlib:Parse)")
    tr.add_argument("--data-dir", default=None, help="materialised evidence directory (default: data/)")
    tr.add_argument("--fix-evidence", default=None, help="a FixEvidence JSON file (overrides --data-dir)")
    tr.add_argument("--release-range", default=None, help="a ReleaseRange JSON file (overrides --data-dir)")
    tr.add_argument("--candidate-code", default=None, help="its candidate_code JSON file (overrides --data-dir)")
    tr.add_argument("--vulndb-cache", default=None, help="vulndb cache directory")
    tr.add_argument("--module-rel", default=None,
                    help="the advisory module's directory inside the fix repository (default: inferred from paths)")
    tr.add_argument("--main", action="append", default=None, help="analyse only this main package (repeatable)")
    tr.add_argument("--max-mains", type=int, default=app_mod.DEFAULT_MAX_MAINS,
                    help=f"analyse at most this many main packages (default {app_mod.DEFAULT_MAX_MAINS}; more makes "
                         "coverage incomplete, so NOT_REACHABLE is not concluded)")
    tr.add_argument("--commit", default=None, help="record this commit for the app (an extracted tree)")
    tr.add_argument("--k", type=int, default=None, help="Mode 2: candidates analysed (default: the fixed retriever's k)")
    tr.add_argument("--retriever", default="fixed", help="Mode 2: fixed (default), bm25, or hybrid:<embedder>")
    tr.add_argument("--lift", default=None, choices=["NEAREST", "ALL"],
                    help="add LIFTED symbols as extra, non-deciding seeds (default off)")
    tr.add_argument("--mode2-policy", default=aggregate.MODE2_POLICY_DOWNGRADE,
                    choices=[aggregate.MODE2_POLICY_DOWNGRADE, aggregate.MODE2_POLICY_KEEP],
                    help="what a Mode 2 NOT_REACHABLE becomes (default DOWNGRADE to CANT_DETERMINE; see the CP7 report)")
    tr.add_argument("--no-verify", action="store_true", help="skip the evidence verifier (verification NOT_RUN)")
    tr.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds per helper call (default 300)")
    tr.add_argument("--build-timeout", type=float, default=an.DEFAULT_BUILD_TIMEOUT_S,
                    help="seconds per linker build (default 600)")
    tr.add_argument("--out", default=None, help="also write the verdict JSON to this file")


def default_runners(timeout: float = DEFAULT_TIMEOUT_S, build_timeout: float = an.DEFAULT_BUILD_TIMEOUT_S,
                    binary: Path | None = None) -> triage.Runners:
    """The real methods: Go helper (VTA, edges, funcs, lift), `go build` + `go tool nm`, `go list`."""
    from vulntrace.methods.lift import run_lift
    from vulntrace.verifier import verify as vf
    from vulntrace.verifier.sources import FileSource

    def verifier_ctx(info: app_mod.AppInfo, incomplete: bool):
        use_git = info.commit_source == "GIT_HEAD" and info.dirty is False
        src = FileSource(info.module_dir, info.commit, info.git_prefix, use_git=use_git)
        return vf.VerifyContext(module_dir=info.module_dir, source=src, funcs_fn=vf.helper_funcs(binary),
                                edges_fn=vf.helper_edges(binary, timeout), locate_fn=vf.go_list_locator(info.module_dir),
                                incomplete=incomplete)

    def lift(module_dir: Path, seeds: list[dict[str, str]], rule: str) -> list[dict[str, Any]]:
        return run_lift(module_dir, seeds, rules=[rule], timeout=timeout, binary=binary)

    return triage.Runners(vta=an.default_vta(timeout, binary=binary), linker=an.default_linker(build_timeout),
                          verifier_ctx=verifier_ctx, lift=lift)


def repo_commit() -> str | None:
    from vulntrace.eval.run_info import _out

    return _out(["git", "rev-parse", "--short", "HEAD"])


def build_request(args) -> triage.TriageRequest:
    app = Path(args.app)
    if not app.is_dir():
        raise inputs.InputError(f"--app {args.app} is not a directory")
    if args.advisory_file:
        advisory = inputs.load_advisory_file(Path(args.advisory_file))
    else:
        advisory = inputs.load_advisory_from_vulndb(args.advisory, Path(args.vulndb_cache) if args.vulndb_cache else None)
    case_id = advisory["id"]
    ev = inputs.load_evidence(case_id, Path(args.data_dir) if args.data_dir else inputs.DATA_DIR)
    for key, flag in (("fix_evidence", args.fix_evidence), ("release_range", args.release_range),
                      ("candidate_code", args.candidate_code)):
        if flag:
            ev[key] = inputs.read_json(Path(flag))
            if ev[key] is None:
                raise inputs.InputError(f"{flag} does not exist")
    targets = [inputs.parse_target(t) for t in args.target] if args.target else None
    if args.mode == "targets" and not targets:
        raise inputs.InputError("--mode targets needs at least one --target")
    from vulntrace.dataset import vulndb

    return triage.TriageRequest(
        case_id=case_id, app=app, mode=args.mode, advisory=advisory, targets=targets,
        fix_evidence=ev["fix_evidence"], release_range=ev["release_range"], candidate_code=ev["candidate_code"],
        module_rel=args.module_rel, mains=args.main, max_mains=args.max_mains, commit=args.commit, k=args.k,
        retriever=args.retriever, lift_rule=args.lift, mode2_policy=args.mode2_policy, run_verifier=not args.no_verify,
        vulndb_commit=vulndb.pinned_commit() if advisory.get("_source") == "vulndb" else advisory.get("source", {}).get("vulndb_commit"),
        repo_commit=repo_commit())


def cmd_triage(args) -> int:
    try:
        req = build_request(args)
    except inputs.InputError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    try:
        binary = ensure_helper()
    except HelperError as exc:
        print(f"missing prerequisite: {exc.code}: {exc.message}", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    verdict = triage.run_triage(req, default_runners(args.timeout, args.build_timeout, binary))
    errors = validation_errors("verdict", verdict)
    if errors:
        print("internal error: verdict violates schemas/verdict.schema.json: " + "; ".join(errors[:5]), file=sys.stderr)
        return EXIT_UNEXPECTED
    text = json.dumps(verdict, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return EXIT_OK
