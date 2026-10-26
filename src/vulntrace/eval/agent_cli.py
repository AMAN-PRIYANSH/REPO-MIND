"""Command implementations for CP6:

    eval symbols --strategy agent --set d4 [--arm A2 --arm A3]   run the agent arms, write result JSON
    agent prepare --set d4 [--diffs] [--graph]                   commit diffs and neighbour tables
    agent show-trace --trace <file.json.gz>                      read one case's trace (failure analysis)

All LLM use goes through `llm.factory.make_client` (loopback endpoint rule, disk cache). The
evaluation refuses to write anything when the evidence is empty or differs from the committed case
list (the CP4 gate), or when no case was run.
"""

import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

from vulntrace.agent import budget as B
from vulntrace.agent import prepare
from vulntrace.agent import prompts as AP
from vulntrace.eval import cp5_cli
from vulntrace.eval import retrieval as er
from vulntrace.llm import models_config
from vulntrace.models.llm import EndpointError

EXIT_OK, EXIT_INVALID_INPUT, EXIT_MISSING_PREREQUISITE = 0, 2, 3
DEFAULT_OUT = "results/cp6"


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _progress(i: int, n: int, what: str) -> None:
    if i == 1 or i % 10 == 0 or i == n:
        _log(f"  {i}/{n} {what}")


def langgraph_version() -> str | None:
    try:
        return importlib.metadata.version("langgraph")
    except importlib.metadata.PackageNotFoundError:
        return None


def budget_from_args(args) -> B.Budget:
    """The default budget unless a flag overrides one value; every run records the budget it used."""
    d = B.Budget()
    return B.Budget(max_steps=args.max_steps or d.max_steps, max_tool_chars=args.max_tool_chars or d.max_tool_chars,
                    max_total_prompt_tokens=args.max_total_prompt_tokens or d.max_total_prompt_tokens,
                    max_prompt_tokens_per_call=args.max_prompt_tokens_per_call or d.max_prompt_tokens_per_call,
                    max_seconds=args.max_seconds or d.max_seconds)


def evidence_availability(case_list: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    out = {"commit_diffs": {}, "graph": {}}
    for e in case_list["cases"]:
        diffs, dnote, table, gnote = prepare.load_case_extras(data_dir, e["id"])
        out["commit_diffs"][e["id"]] = diffs is not None
        out["graph"][e["id"]] = table is not None
    return {k: {"available": sum(v.values()), "of": len(v)} for k, v in out.items()}


def cmd_eval_agent(args, argv, load_d4_harness) -> int:
    from vulntrace.eval import agent_eval

    if args.dataset_set != "d4":
        print("error: the agent runs on D4 only (Mode 2): pass --set d4", file=sys.stderr)
        return EXIT_INVALID_INPUT
    arms = args.arm or ["A2", "A3"]
    bad = [a for a in arms if a not in agent_eval.ARMS]
    if bad:
        print(f"error: unknown arm(s) {bad}; expected {sorted(agent_eval.ARMS)} (A0 and A1 are scored by the renderer)",
              file=sys.stderr)
        return EXIT_INVALID_INPUT
    if langgraph_version() is None:
        print("error: langgraph is not installed; install the agent extra: pip install -e '.[agent]'", file=sys.stderr)
        return EXIT_MISSING_PREREQUISITE
    try:
        client, model = cp5_cli._client(args)
        ev_cases, ranges, notes, harness = load_d4_harness(args)
    except (EndpointError, er.HarnessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    from vulntrace.dataset import build as dataset_build

    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D4_cases.json"
    case_list = json.loads(case_list_path.read_text(encoding="utf-8"))
    cfg, _sec, f = cp5_cli.retriever_config(args.dry_run)
    alias = models_config.resolve(model)["alias"]
    out = Path(args.out) if args.out else Path(DEFAULT_OUT)
    trace_dir = Path(args.trace_dir) if args.trace_dir else data_dir / "agent_traces"
    env = er.environment(argv)
    budget = budget_from_args(args)
    availability = evidence_availability(case_list, data_dir)
    _log(f"agent on {len(ev_cases)} D4 cases, arms {arms}, retriever {cfg.name} [{f.variant}], model {client.model_id}; "
         f"commit diffs for {availability['commit_diffs']['available']}, neighbour tables for "
         f"{availability['graph']['available']} of {len(case_list['cases'])} cases")
    for arm in arms:
        try:
            doc = agent_eval.run_arm(harness, cfg, f.variant, arm, client, alias, data_dir, trace_dir, budget,
                                     rerun=args.rerun, limit=args.limit, progress=_progress)
        except agent_eval.RunAborted as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_INVALID_INPUT
        doc["model"] = cp5_cli.model_block(client, model, args.dry_run)
        doc["prompt"] = {"set": AP.PROMPT_SET, "sha256": AP.prompt_set_sha256(), "templates": list(AP.ALL_TEMPLATES)}
        doc["embedding_model"] = harness.embedder(cfg.embedder).info() if cfg.embedder else None
        doc["agent_evidence"] = availability
        doc["langgraph_version"] = langgraph_version()
        doc["environment"] = er.environment(argv, base=env)
        doc["dry_run"] = args.dry_run
        doc["limit"] = args.limit
        c = doc["counts"]
        if c["run"] == 0:
            print(f"error: arm {arm}: the agent ran on 0 cases; refusing to write", file=sys.stderr)
            return EXIT_INVALID_INPUT
        path = er.write_json(out / f"agent__{arm}__{alias}.json", doc)
        s = c["stop_reasons"]
        print(f"{arm} [{alias}]: {c['run']} run; submitted {s['SUBMITTED']}, abstained {s['ABSTAINED']}, "
              f"invalid answer {s['INVALID_ANSWER']}, invalid action {s['INVALID_ACTION']}, loop {s['LOOP_DETECTED']}, "
              f"budget {s['BUDGET_EXCEEDED']} {c['budget_reasons']}, errors {s['ERROR']}; {c['llm_calls']} calls, "
              f"{c['input_tokens']} in / {c['output_tokens']} out tokens; reused traces {c['reused_traces']} -> {path}")
    return EXIT_OK


def cmd_agent_prepare(args, argv) -> int:
    from vulntrace.dataset import build as dataset_build
    from vulntrace.dataset import datasets
    from vulntrace.eval.lift_cli import default_gomodcache
    from vulntrace.eval.run_info import run_info
    from vulntrace.methods.helper import HelperError, ensure_helper

    if not (args.diffs or args.graph):
        print("error: give --diffs and/or --graph", file=sys.stderr)
        return EXIT_INVALID_INPUT
    binary, gomodcache = None, None
    if args.graph:
        try:
            binary = ensure_helper()
        except HelperError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_MISSING_PREREQUISITE
        gomodcache = Path(args.gomodcache) if args.gomodcache else default_gomodcache()
        gomodcache.mkdir(parents=True, exist_ok=True)
        os.environ["GOMODCACHE"], os.environ["GOWORK"] = str(gomodcache), "off"
        os.environ.setdefault("GOMEMLIMIT", "9GiB")
    case_list_path = Path(args.cases) if args.cases else dataset_build.RESULTS_DATASETS_DIR / "D4_cases.json"
    case_list = json.loads(case_list_path.read_text(encoding="utf-8"))
    cases, _ = datasets.load_all_cases(Path(args.cache) if args.cache else None)
    data_dir = Path(args.data_dir) if args.data_dir else dataset_build.DATA_DIR
    missing = [e["id"] for e in case_list["cases"] if not (data_dir / "release_range" / f"{e['id']}.json").is_file()]
    if missing:
        print(f"error: {len(missing)} D4 case(s) have no release_range evidence in {data_dir}; run "
              "`dataset materialize --set d4` first", file=sys.stderr)
        return EXIT_INVALID_INPUT
    summary = prepare.prepare_all(case_list, {c["id"]: c for c in cases}, data_dir, diffs=args.diffs, graph=args.graph,
                                  repo_cache=Path(args.repo_cache) if args.repo_cache else None, gomodcache=gomodcache,
                                  binary=binary, jobs=args.jobs, timeout=args.timeout, rerun=args.rerun, limit=args.limit)
    summary["environment"] = run_info(argv)
    summary["settings"] = {"diff_store_cap": prepare.DIFF_STORE_CAP, "neighbour_max_results": prepare.NEIGHBOUR_MAX_RESULTS,
                           "hops": 1, "graph": "helper VTA call graph, library mode, module at the range's `from` commit; "
                                               "only candidates of the vulnerable release (side OLD or BOTH) are nodes"}
    out = Path(args.summary_out) if args.summary_out else Path(DEFAULT_OUT) / "agent_evidence.json"
    if out.is_file():  # keep the part of an earlier summary this invocation did not rebuild
        old = json.loads(out.read_text(encoding="utf-8"))
        for key in ("commit_diffs", "graph"):
            if not summary[key] and old.get(key):
                summary[key], summary[f"{key}_status_counts"] = old[key], old.get(f"{key}_status_counts")
    er.write_json(out, summary)
    print(f"commit diffs: {summary.get('commit_diffs_status_counts')}; neighbour tables: "
          f"{summary.get('graph_status_counts')} -> {out}")
    return EXIT_OK


def trace_lines(trace: dict[str, Any], symbols: dict[str, str] | None = None) -> list[str]:
    """A readable, code-free rendering of one trace (actions, outcomes, IDs shown, tokens)."""
    sym = (lambda i: f"{i}={symbols.get(i, '?')}") if symbols else (lambda i: i)
    t = trace["totals"]
    out = [f"{trace['case_id']} arm {trace['arm']} model {trace['model'].get('model_id')}: {trace['stop_reason']}"
           + (f"/{trace['budget_reason']}" if trace["budget_reason"] else "")
           + f"; answer {[sym(i) for i in trace['final']['candidate_ids']]}; steps {t['steps']}, calls {t['llm_calls']}, "
             f"tokens {t['input_tokens']}/{t['output_tokens']}, {t['agent_seconds']} s",
           f"  initial search showed: {', '.join(sym(i) for i in trace['initial']['initial_candidates_shown'])}"]
    for turn in trace["turns"]:
        act = turn.get("parsed") or {}
        args = json.dumps(act.get("args", {}), ensure_ascii=False)[:160]
        line = f"  [{turn['n']}] {turn['purpose']}: {act.get('tool', '(invalid)')} {args if act else ''}"
        if turn.get("problems"):
            line += f" problems={turn['problems']}"
        line += f" -> {turn.get('outcome')}"
        if turn.get("result_summary"):
            line += f": {turn['result_summary']}"
        if turn.get("answer_problems"):
            line += f" {turn['answer_problems']}"
        if turn.get("shown_ids"):
            line += f"; shown {[sym(i) for i in turn['shown_ids'][:10]]}"
        out.append(line)
    return out


def cmd_show_trace(args) -> int:
    p = Path(args.trace)
    if not p.is_file():
        print(f"error: no such trace file: {p}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    trace = prepare.read_gz(p)
    symbols = None
    if args.data_dir:
        rr_p = Path(args.data_dir) / "release_range" / f"{trace['case_id']}.json"
        if rr_p.is_file():
            symbols = {c["candidate_id"]: c["symbol"] for c in json.loads(rr_p.read_text(encoding="utf-8"))["candidates"]}
    print("\n".join(trace_lines(trace, symbols)))
    if args.raw:
        for turn in trace["turns"]:
            print(f"--- [{turn['n']}] raw response:\n{turn.get('raw_response')}")
    return EXIT_OK
