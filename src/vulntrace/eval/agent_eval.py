"""CP6 evaluation runner: the agent arms on D4 (`eval symbols --strategy agent --set d4`).

Arms (all on the same D4 cases):

- **A0** retrieval top-1 / top-3 of the fixed retriever (`hybrid:bge-small`, `code+commits`), the
  agent's own initial search, recorded in every agent row (`a0_top3`);
- **A1** S1 top-10 from the committed CP5 result files (reused, never re-run; scored by the renderer);
- **A2** the agent without graph tools; **A3** the agent with `callers` / `callees`.

One result document per arm and model: compact per-case rows (answer IDs, stop reason, counters,
tokens, times, gold candidate IDs for scoring) and no prompt, code or raw model text. The full trace
of every case goes to a gitignored, gzipped trace file, which also makes the run resumable: a case
whose trace exists for the same configuration and model is not run again. Gold is read only after
the agent has answered (the world the agent sees has no gold).
"""

import json
import time
from pathlib import Path
from typing import Any, Callable

from vulntrace.agent import budget as B
from vulntrace.agent import prepare
from vulntrace.agent.graph import AgentConfig, run_agent
from vulntrace.agent.world import CaseWorld, candidates_from_chunks, commits_from_range
from vulntrace.models.llm import LLMClient
from vulntrace.retrieval.query import QueryInput

SCHEMA_VERSION = "1.0"
ARMS = {"A2": False, "A3": True}       # arm -> graph tools
MAX_CONSECUTIVE_ERRORS = 3


class RunAborted(Exception):
    pass


def build_world(harness, cfg, variant: str, case, data_dir: Path, graph: bool) -> CaseWorld:
    rr = json.loads((Path(data_dir) / "release_range" / f"{case.case_id}.json").read_text(encoding="utf-8"))
    chunks = harness.ranges[case.range_key]
    diffs, dnote, table, gnote = prepare.load_case_extras(data_dir, case.case_id)
    world = CaseWorld(
        case_id=case.case_id, advisory=QueryInput(case.summary, case.details),
        candidates=candidates_from_chunks(chunks, rr), commits=commits_from_range(rr),
        search=lambda q: harness.rank_query(cfg, case, variant, q),
        initial_ranking=harness.rank_case(cfg, case, variant),
        commit_diffs=diffs, commit_diffs_note=dnote,
        graph=table if graph else None, graph_note=gnote if graph else "graph tools are not part of this arm")
    return world


def trace_path(trace_dir: Path, arm: str, alias: str, case_id: str) -> Path:
    return Path(trace_dir) / f"{arm}__{alias}" / f"{case_id}.json.gz"


def _reusable(trace: dict[str, Any], config: AgentConfig, client: LLMClient) -> bool:
    return (trace.get("config_sha256") == config.config_sha256() and trace.get("stop_reason") != B.ERROR
            and (trace.get("model") or {}).get("model_id") == client.model_id
            and (trace.get("model") or {}).get("model_digest") == client.model_digest)


def row(case, trace: dict[str, Any] | None, a0: list[str]) -> dict[str, Any]:
    base = {"id": case.case_id, "created": case.created, "cluster_key": case.cluster_key,
            "n_candidates": len(case.candidate_ids), "gold_ids": sorted(case.gold_core),
            "gold_derived_ids": sorted(case.gold_core_derived), "gold_in_candidates": bool(case.gold_core),
            "a0_top3": a0[:3]}
    if trace is None:
        return {**base, "stop_reason": B.NOT_RUN, "budget_reason": None, "error": None, "answer": [], "abstain": False,
                "evidence": {"candidates": 0, "commits": 0}, "steps": 0, "llm_calls": 0, "input_tokens": 0,
                "output_tokens": 0, "max_call_prompt_tokens": 0, "agent_seconds": 0.0, "wall_seconds": 0.0,
                "counters": {}, "tool_counts": {}, "graph_tools_available": False, "commit_diffs_available": False,
                "answer_ids_seen": None, "trace_id": None, "reused_trace": False}
    t = trace["totals"]
    ev = trace["final"]["evidence"]
    return {**base, "stop_reason": trace["stop_reason"], "budget_reason": trace["budget_reason"], "error": trace["error"],
            "answer": trace["final"]["candidate_ids"], "abstain": trace["final"]["abstain"],
            "evidence": {"candidates": sum(1 for x in ev if x in case.candidate_ids),
                         "commits": sum(1 for x in ev if x not in case.candidate_ids)},
            "steps": t["steps"], "llm_calls": t["llm_calls"], "input_tokens": t["input_tokens"],
            "output_tokens": t["output_tokens"], "max_call_prompt_tokens": t["max_call_prompt_tokens"],
            "agent_seconds": t["agent_seconds"], "wall_seconds": t["wall_seconds"], "counters": trace["counters"],
            "tool_counts": trace["tool_counts"], "graph_tools_available": trace["graph_tools_available"],
            "commit_diffs_available": trace["commit_diffs_available"],
            "answer_ids_seen": trace["final"]["answer_ids_seen"],
            "trace_id": trace["trace_id"], "reused_trace": trace.get("_reused", False)}


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    run = [r for r in rows if r["stop_reason"] != B.NOT_RUN]
    by_stop = {s: sum(1 for r in rows if r["stop_reason"] == s) for s in B.STOP_REASONS}
    by_budget = {s: sum(1 for r in rows if r["budget_reason"] == s) for s in B.BUDGET_REASONS}
    ctr = lambda k: sum(r["counters"].get(k, 0) for r in run)  # noqa: E731
    cases_with = lambda k: sum(1 for r in run if r["counters"].get(k, 0) > 0)  # noqa: E731
    return {"cases": len(rows), "run": len(run), "stop_reasons": by_stop, "budget_reasons": by_budget,
            "invalid_actions": ctr("invalid_actions"), "cases_with_invalid_action": cases_with("invalid_actions"),
            "repaired_actions": ctr("repaired_actions"), "answer_rejections": ctr("answer_rejections"),
            "repeated_calls": ctr("repeated_calls"), "tool_errors": ctr("tool_errors"),
            "truncated_outputs": ctr("truncated_outputs"), "length_stops": ctr("length_stops"),
            "graph_tools_available": sum(1 for r in run if r["graph_tools_available"]),
            "commit_diffs_available": sum(1 for r in run if r["commit_diffs_available"]),
            "llm_calls": sum(r["llm_calls"] for r in run), "input_tokens": sum(r["input_tokens"] for r in run),
            "output_tokens": sum(r["output_tokens"] for r in run),
            "agent_seconds": round(sum(r["agent_seconds"] for r in run), 1),
            "wall_seconds": round(sum(r["wall_seconds"] for r in run), 1),
            "reused_traces": sum(1 for r in run if r["reused_trace"])}


def run_arm(harness, cfg, variant: str, arm: str, client: LLMClient, alias: str, data_dir: Path, trace_dir: Path,
            budget: B.Budget = B.Budget(), rerun: bool = False, limit: int | None = None,
            progress: Callable[[int, int, str], None] | None = None) -> dict[str, Any]:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {sorted(ARMS)}")
    config = AgentConfig(arm, ARMS[arm], budget)
    rows, consecutive = [], 0
    cases = harness.cases[: limit or None]
    t0 = time.monotonic()
    for i, case in enumerate(cases, start=1):
        a0 = harness.rank_case(cfg, case, variant)
        if not case.candidate_ids:
            rows.append(row(case, None, a0))
            continue
        tp = trace_path(trace_dir, arm, alias, case.case_id)
        trace = None
        if tp.is_file() and not rerun:
            old = prepare.read_gz(tp)
            if _reusable(old, config, client):
                trace = {**old, "_reused": True}
        if trace is None:
            world = build_world(harness, cfg, variant, case, data_dir, graph=ARMS[arm])
            trace = run_agent(world, client, config)
            trace["retriever"] = {"config": cfg.name, "variant": variant}
            prepare.write_gz(tp, trace)
        consecutive = consecutive + 1 if trace["stop_reason"] == B.ERROR else 0
        if consecutive >= MAX_CONSECUTIVE_ERRORS:
            raise RunAborted(f"{MAX_CONSECUTIVE_ERRORS} cases in a row ended with a server error ({trace['error']}); "
                             "is the model server up? Nothing is written; finished cases are in the trace directory "
                             "and the response cache, and a re-run resumes.")
        rows.append(row(case, trace, a0))
        if progress:
            progress(i, len(cases), f"{case.case_id} {trace['stop_reason']} steps={trace['totals']['steps']}")
    return {"schema_version": SCHEMA_VERSION, "experiment": arm, "arm": arm, "dataset": "D4",
            "graph_tools": ARMS[arm], "config": config.as_dict(), "config_sha256": config.config_sha256(),
            "retriever": {"config": cfg.name, "variant": variant}, "case_count": len(cases),
            "counts": counts(rows), "wall_seconds": round(time.monotonic() - t0, 1), "rows": rows}
