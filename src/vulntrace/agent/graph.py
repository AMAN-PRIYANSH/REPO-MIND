"""The investigation agent as a LangGraph state graph (CP6 deliverable 1).

    START -> budget -> act -> tool ----> budget -> ...
                        |  -> submit --> END (SUBMITTED / ABSTAINED / INVALID_ANSWER) or budget (one retry)
                        |  -> repair --> budget (one repair turn per invalid action)
                        '-> END (ERROR, INVALID_ACTION after a failed repair)
    budget -> END on a budget stop (STEPS, TOKENS, CONTEXT, TIME)
    tool   -> END on LOOP_DETECTED

- `budget` checks the budgets before every model call.
- `act` makes one model call (temperature 0, fixed seed) and parses one JSON action.
- `tool` runs the action against the case's closed pool, or answers a repeated identical call
  with a note instead of running it again; one repeat too many is `LOOP_DETECTED`.
- `repair` shows the model why its reply was rejected; a second invalid reply in a row ends
  the run (`INVALID_ACTION`).
- `submit` checks the answer (`protocol.check_answer`); a rejected answer gets one retry per
  run, a second rejection is `INVALID_ANSWER`.

The state holds the candidate pool, the message history, steps and tokens used, and the trace.
Nothing is repaired silently: every invalid reply, repair, rejection, repeat and tool error is
counted in `counters` and recorded in the trace turn where it happened.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from vulntrace.agent import budget as B
from vulntrace.agent import prompts as AP
from vulntrace.agent import protocol as P
from vulntrace.agent.tools import Tools, search_listing
from vulntrace.agent.world import CaseWorld
from vulntrace.models.llm import LLMClient, LLMError, LLMSettings

SCHEMA_VERSION = "1.0"
AGENT_NAME = "investigator_v1"
AGENT_SETTINGS = LLMSettings(temperature=0.0, seed=7, max_tokens=256, json_mode=True)
INITIAL_SEARCH_K = 10
RECURSION_LIMIT = 500   # LangGraph's own guard; the budgets stop a run long before this
SHOWN_IN_TRACE = 20     # candidate IDs / SHAs of one tool output kept in the trace (IDs only, never code)

COUNTERS = ("invalid_actions", "repaired_actions", "answer_rejections", "repeated_calls", "tool_errors",
            "truncated_outputs", "length_stops")


class AgentState(TypedDict, total=False):
    pool: frozenset
    messages: list[dict[str, str]]
    steps: int
    llm_calls: int
    prompt_tokens: int
    output_tokens: int
    max_call_prompt_tokens: int
    agent_seconds: float
    action: dict[str, Any] | None
    problems: list[dict[str, str]]
    raw: str
    repair_pending: bool
    answer_retry_used: bool
    next_purpose: str            # what the next model call is: "action", "repair" or "answer_retry"
    seen_candidates: frozenset
    seen_commits: tuple
    calls: dict[str, int]
    turns: list[dict[str, Any]]
    counters: dict[str, int]
    stop_reason: str | None
    budget_reason: str | None
    error: str | None
    answer: list[str]
    evidence: list[str]


@dataclass(frozen=True)
class AgentConfig:
    arm: str
    graph_tools: bool
    budget: B.Budget = field(default_factory=B.Budget)
    settings: LLMSettings = AGENT_SETTINGS

    def as_dict(self) -> dict[str, Any]:
        return {"arm": self.arm, "graph_tools": self.graph_tools, "budget": self.budget.as_dict(),
                "settings": self.settings.as_dict(), "agent": AGENT_NAME, "prompt_set": AP.PROMPT_SET,
                "prompt_sha256": AP.prompt_set_sha256(), "initial_search_k": INITIAL_SEARCH_K}

    def config_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True).encode("utf-8")).hexdigest()


def messages_sha256(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _replace_last(turns: list[dict], **outcome) -> list[dict]:
    last = dict(turns[-1])
    last.update(outcome)
    return turns[:-1] + [last]


def _bump(counters: dict[str, int], **inc) -> dict[str, int]:
    out = dict(counters)
    for k, v in inc.items():
        out[k] = out.get(k, 0) + v
    return out


class Agent:
    def __init__(self, world: CaseWorld, client: LLMClient, config: AgentConfig,
                 clock: Callable[[], float] = time.monotonic):
        self.world, self.client, self.config, self.clock = world, client, config, clock
        self.budget = config.budget
        self.tools = Tools(world, self.budget.max_tool_chars, config.graph_tools)
        self.graph = self._build()

    # --- nodes ------------------------------------------------------------------------------
    def _budget(self, s: AgentState) -> dict[str, Any]:
        b = self.budget
        reason = None
        est = B.estimate_tokens(s["messages"])
        if s["steps"] >= b.max_steps:
            reason = B.STEPS
        elif s["agent_seconds"] >= b.max_seconds:
            reason = B.TIME
        elif est > b.max_prompt_tokens_per_call:
            reason = B.CONTEXT
        elif s["prompt_tokens"] + est > b.max_total_prompt_tokens:
            reason = B.TOKENS
        if reason:
            return {"stop_reason": B.BUDGET_EXCEEDED, "budget_reason": reason}
        return {}

    def _act(self, s: AgentState) -> dict[str, Any]:
        purpose = s["next_purpose"]
        messages = s["messages"]
        turn: dict[str, Any] = {"n": s["llm_calls"] + 1, "step": s["steps"] + 1, "purpose": purpose,
                                "prompt_sha256": messages_sha256(messages), "prompt_messages": len(messages),
                                "prompt_chars": sum(len(m["content"]) for m in messages),
                                "estimated_prompt_tokens": B.estimate_tokens(messages)}
        try:
            resp = self.client.complete(messages, self.config.settings)
        except LLMError as exc:
            turn.update(outcome="llm_error", error=exc.code)
            return {"turns": s["turns"] + [turn], "stop_reason": B.ERROR, "error": exc.code,
                    "llm_calls": s["llm_calls"] + 1}
        n_in = resp.input_tokens if resp.input_tokens is not None else turn["estimated_prompt_tokens"]
        n_out = resp.output_tokens or 0
        action, problems = P.parse_action(resp.text, self.tools.names)
        turn.update(raw_response=resp.text, parsed=action.as_dict() if action else None,
                    problems=[p.code for p in problems],
                    llm={**resp.provenance(), "input_tokens_estimated": resp.input_tokens is None})
        upd: dict[str, Any] = {
            "llm_calls": s["llm_calls"] + 1, "prompt_tokens": s["prompt_tokens"] + n_in,
            "output_tokens": s["output_tokens"] + n_out, "max_call_prompt_tokens": max(s["max_call_prompt_tokens"], n_in),
            "agent_seconds": s["agent_seconds"] + float(resp.latency_s or 0.0), "raw": resp.text,
            "action": action.as_dict() if action else None, "problems": [p.__dict__ for p in problems],
            "counters": _bump(s["counters"], length_stops=int(resp.finish_reason == "length"))}
        if problems:
            if s["repair_pending"]:
                turn["outcome"] = "invalid_after_repair"
                upd.update(stop_reason=B.INVALID_ACTION, counters=_bump(upd["counters"], invalid_actions=1))
            else:
                turn["outcome"] = "invalid"
        upd["turns"] = s["turns"] + [turn]
        return upd

    def _repair(self, s: AgentState) -> dict[str, Any]:
        text = "; ".join(p["message"] for p in s["problems"])
        msgs = s["messages"] + [{"role": "assistant", "content": s["raw"]},
                                {"role": "user", "content": AP.repair_message(text, self.tools.names)}]
        return {"messages": msgs, "repair_pending": True, "next_purpose": "repair",
                "counters": _bump(s["counters"], invalid_actions=1)}

    def _clear_repair(self, s: AgentState, counters: dict[str, int]) -> dict[str, int]:
        return _bump(counters, repaired_actions=1) if s["repair_pending"] else counters

    def _tool(self, s: AgentState) -> dict[str, Any]:
        action = P.Action(s["action"]["tool"], s["action"]["args"])
        counters = self._clear_repair(s, s["counters"])
        key = action.key()
        step = s["steps"] + 1
        calls = dict(s["calls"])
        seen_c, seen_k = s["seen_candidates"], s["seen_commits"]
        if key in calls:
            counters = _bump(counters, repeated_calls=1)
            if counters["repeated_calls"] > self.budget.max_repeated_calls:
                return {"stop_reason": B.LOOP_DETECTED, "counters": counters, "repair_pending": False,
                        "turns": _replace_last(s["turns"], outcome="loop_stop", repeat_of_step=calls[key])}
            output, dt = AP.repeat_output(calls[key]), 0.0
            outcome = {"outcome": "repeat", "repeat_of_step": calls[key], "tool": action.tool}
        else:
            t0 = self.clock()
            obs = self.tools.run(action)
            dt = self.clock() - t0
            calls[key] = step
            output = obs.output
            seen_c = seen_c | set(obs.candidates_shown)
            seen_k = seen_k + tuple(x for x in obs.commits_shown if x not in seen_k)
            counters = _bump(counters, tool_errors=int(not obs.ok), truncated_outputs=int(obs.truncated))
            outcome = {"outcome": "tool", "tool": action.tool, "ok": obs.ok, "result_summary": obs.summary,
                       "output_chars": len(output), "full_chars": obs.full_chars, "truncated": obs.truncated,
                       "shown_ids": list(obs.candidates_shown[:SHOWN_IN_TRACE]),
                       "shown_commits": [x[:12] for x in obs.commits_shown[:SHOWN_IN_TRACE]],
                       "tool_ms": round(dt * 1000, 1), "notes": obs.notes}
        msgs = s["messages"] + [{"role": "assistant", "content": s["raw"]},
                                {"role": "user", "content": AP.observation_message(action.tool, step,
                                                                                   self.budget.max_steps, output)}]
        return {"messages": msgs, "steps": step, "calls": calls, "seen_candidates": seen_c, "seen_commits": seen_k,
                "counters": counters, "repair_pending": False, "next_purpose": "action",
                "agent_seconds": s["agent_seconds"] + dt,
                "turns": _replace_last(s["turns"], **outcome)}

    def _submit(self, s: AgentState) -> dict[str, Any]:
        action = P.Action(s["action"]["tool"], s["action"]["args"])
        counters = self._clear_repair(s, s["counters"])
        answer, problems = P.check_answer(action, s["pool"], self.budget.max_answer_ids, set(s["seen_candidates"]),
                                          s["seen_commits"])
        if answer is not None:
            reason = B.ABSTAINED if answer.abstain else B.SUBMITTED
            return {"stop_reason": reason, "answer": list(answer.candidate_ids), "evidence": list(answer.evidence),
                    "steps": s["steps"] + 1, "counters": counters, "repair_pending": False,
                    "turns": _replace_last(s["turns"], outcome="answer_accepted", abstain=answer.abstain)}
        counters = _bump(counters, answer_rejections=1)
        turns = _replace_last(s["turns"], outcome="answer_rejected", answer_problems=[p.code for p in problems])
        if s["answer_retry_used"]:
            return {"stop_reason": B.INVALID_ANSWER, "counters": counters, "turns": turns, "repair_pending": False}
        msgs = s["messages"] + [{"role": "assistant", "content": s["raw"]},
                                {"role": "user", "content": AP.repair_message("; ".join(p.message for p in problems),
                                                                              self.tools.names)}]
        return {"messages": msgs, "answer_retry_used": True, "counters": counters, "turns": turns,
                "repair_pending": False, "next_purpose": "answer_retry"}

    # --- wiring -----------------------------------------------------------------------------
    @staticmethod
    def _after_budget(s: AgentState) -> str:
        return END if s.get("stop_reason") else "act"

    @staticmethod
    def _after_act(s: AgentState) -> str:
        if s.get("stop_reason"):
            return END
        if s["problems"]:
            return "repair"
        return "submit" if s["action"]["tool"] == P.SUBMIT else "tool"

    @staticmethod
    def _after_step(s: AgentState) -> str:
        return END if s.get("stop_reason") else "budget"

    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("budget", self._budget)
        g.add_node("act", self._act)
        g.add_node("repair", self._repair)
        g.add_node("tool", self._tool)
        g.add_node("submit", self._submit)
        g.add_edge(START, "budget")
        g.add_conditional_edges("budget", self._after_budget, {"act": "act", END: END})
        g.add_conditional_edges("act", self._after_act, {"repair": "repair", "tool": "tool", "submit": "submit", END: END})
        g.add_edge("repair", "budget")
        g.add_conditional_edges("tool", self._after_step, {"budget": "budget", END: END})
        g.add_conditional_edges("submit", self._after_step, {"budget": "budget", END: END})
        return g.compile()

    # --- run --------------------------------------------------------------------------------
    def initial_messages(self) -> tuple[list[dict[str, str]], dict[str, Any]]:
        w = self.world
        header = f"{min(INITIAL_SEARCH_K, len(w.initial_ranking))} best of {len(w.candidates)} candidates, best first:"
        listing, shown, trunc, _full = search_listing(w, w.initial_ranking, INITIAL_SEARCH_K, self.budget.max_tool_chars,
                                                      header)
        from vulntrace.llm.prompts import escape_untrusted

        listing, n_esc = escape_untrusted(listing)
        task, meta = AP.task_message(w.advisory, len(w.candidates), listing, self.budget.max_steps)
        system = AP.system_message(self.budget.max_steps, self.budget.max_answer_ids, self.tools.graph_tools)
        meta.update(initial_candidates_shown=list(shown), initial_truncated=trunc,
                    delimiter_escapes=meta["delimiter_escapes"] + n_esc)
        return [{"role": "system", "content": system}, {"role": "user", "content": task}], meta

    def run(self) -> dict[str, Any]:
        t0 = self.clock()
        messages, meta = self.initial_messages()
        state: AgentState = {
            "pool": self.world.pool, "messages": messages, "steps": 0, "llm_calls": 0, "prompt_tokens": 0,
            "output_tokens": 0, "max_call_prompt_tokens": 0, "agent_seconds": 0.0, "action": None, "problems": [],
            "raw": "", "repair_pending": False, "answer_retry_used": False, "next_purpose": "action",
            "seen_candidates": frozenset(meta["initial_candidates_shown"]), "seen_commits": (), "calls": {},
            "turns": [], "counters": {k: 0 for k in COUNTERS}, "stop_reason": None, "budget_reason": None,
            "error": None, "answer": [], "evidence": []}
        final = self.graph.invoke(state, {"recursion_limit": RECURSION_LIMIT})
        return self._trace(final, meta, self.clock() - t0)

    def _trace(self, s: AgentState, meta: dict[str, Any], wall: float) -> dict[str, Any]:
        cfg = self.config
        stop = s.get("stop_reason") or B.ERROR
        tool_counts: dict[str, int] = {}
        for t in s["turns"]:
            if t.get("outcome") in ("tool", "repeat"):
                tool_counts[t["tool"]] = tool_counts.get(t["tool"], 0) + 1
        return {
            "schema_version": SCHEMA_VERSION, "trace_id": hashlib.sha256(
                f"{self.world.case_id}|{cfg.config_sha256()}|{self.client.identity()}".encode()).hexdigest()[:24],
            "case_id": self.world.case_id, "agent": AGENT_NAME, "arm": cfg.arm, "config": cfg.as_dict(),
            "config_sha256": cfg.config_sha256(), "model": self.client.info(), "tools": list(self.tools.names),
            "graph_tools_available": self.tools.graph_tools, "graph_note": self.world.graph_note,
            "commit_diffs_available": self.world.commit_diffs is not None, "pool_size": len(self.world.candidates),
            "n_commits": len(self.world.commits), "initial": meta, "turns": s["turns"],
            "final": {"candidate_ids": list(s["answer"]), "evidence": list(s["evidence"]),
                      "abstain": stop == B.ABSTAINED, "valid": stop in (B.SUBMITTED, B.ABSTAINED)},
            "stop_reason": stop, "budget_reason": s.get("budget_reason"), "error": s.get("error"),
            "counters": dict(s["counters"]), "tool_counts": tool_counts,
            "totals": {"steps": s["steps"], "llm_calls": s["llm_calls"], "input_tokens": s["prompt_tokens"],
                       "output_tokens": s["output_tokens"], "max_call_prompt_tokens": s["max_call_prompt_tokens"],
                       "agent_seconds": round(s["agent_seconds"], 3), "wall_seconds": round(wall, 3),
                       "seen_candidates": len(s["seen_candidates"]), "seen_commits": len(s["seen_commits"])}}


def run_agent(world: CaseWorld, client: LLMClient, config: AgentConfig,
              clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    return Agent(world, client, config, clock).run()
