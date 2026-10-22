"""E1 (Mode 1, D1) and S1 (Mode 2, D4) runners (CP5 deliverable 5).

E1: given the full fix diff, does an LLM choosing from the changed functions beat E0 (predict
all changed functions)? S1: given the top-k of the fixed retriever, does an LLM choosing from
those k beat the retriever's top-1?

Each runner returns one JSON-able document of compact per-case rows. A row holds the parsed
selection, validity flags, token counts, latencies and the metrics of the LLM and of its
baseline on that case - never a prompt or a raw response (those stay in the gitignored cache).
Gold is read only after the selection is made.
"""

import time
from typing import Any, Callable, Mapping

from vulntrace.dataset import baselines, datasets, materialize
from vulntrace.eval import cp5_stats as st
from vulntrace.llm import select as sel
from vulntrace.llm.prompts import (MAX_SELECTED, MODE_FIX, MODE_RELEASE, TopkPromptInput, build_fix_prompt,
                                   build_topk_prompt, fix_input, topk_candidate)
from vulntrace.models.llm import LLMClient
from vulntrace.retrieval.query import QueryInput, query_input_from_case

SCHEMA_VERSION = "1.0"
MAX_CONSECUTIVE_ERRORS = 3
NOT_ASKED = "NOT_ASKED"


class RunAborted(Exception):
    pass


class _ErrorGuard:
    """Stop a run whose server is down instead of writing a file full of ERROR rows."""

    def __init__(self):
        self.consecutive = 0

    def see(self, result: sel.SelectionResult) -> None:
        self.consecutive = self.consecutive + 1 if result.status == sel.STATUS_ERROR else 0
        if self.consecutive >= MAX_CONSECUTIVE_ERRORS:
            raise RunAborted(f"{MAX_CONSECUTIVE_ERRORS} LLM calls in a row failed ({result.error}); is the server up? "
                             "Nothing is written; finished calls are in the cache and a re-run resumes.")


def _not_asked() -> dict[str, Any]:
    return {"status": NOT_ASKED, "selected": [], "abstain": False, "retried": False, "error": None, "input_tokens": 0,
            "output_tokens": 0, "latency_s": 0.0, "attempts": []}


def counts(llm_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n_asked = sum(1 for r in llm_rows if r["status"] != NOT_ASKED)
    by = lambda s: sum(1 for r in llm_rows if r["status"] == s)
    return {"cases": len(llm_rows), "asked": n_asked, "valid": by(sel.STATUS_VALID), "invalid": by(sel.STATUS_INVALID),
            "error": by(sel.STATUS_ERROR), "not_asked": by(NOT_ASKED),
            "abstain": sum(1 for r in llm_rows if r["status"] == sel.STATUS_VALID and r["abstain"]),
            "retried": sum(1 for r in llm_rows if r["retried"]),
            "input_tokens": sum(r["input_tokens"] for r in llm_rows), "output_tokens": sum(r["output_tokens"] for r in llm_rows),
            "llm_seconds": round(sum(r["latency_s"] for r in llm_rows), 1),
            "cached_calls": sum(1 for r in llm_rows for a in r["attempts"] if a["cached"]),
            "calls": sum(len(r["attempts"]) for r in llm_rows)}


# --- E1 --------------------------------------------------------------------------------------------
def run_e1(case_list: Mapping[str, Any], cases_by_id: Mapping[str, dict], evidence_by_id: Mapping[str, dict],
           client: LLMClient, progress: Callable[[int, int, str], None] | None = None) -> dict[str, Any]:
    guard = _ErrorGuard()
    rows = []
    entries = sorted(case_list["cases"], key=lambda c: c["id"])
    t0 = time.monotonic()
    for i, entry in enumerate(entries, start=1):
        cid = entry["id"]
        case, ev = cases_by_id.get(cid), evidence_by_id.get(cid)
        if case is None or ev is None:
            continue  # same rule as CP3 scoring: a case without evidence is not scored (counted by the caller)
        symbol_of = {c["candidate_id"]: c["symbol"] for c in ev["candidates"]}
        meta: dict[str, Any] = {}
        if ev["candidates"]:
            prompt = build_fix_prompt(fix_input(query_input_from_case(case), ev))
            result = sel.select(client, prompt)
            guard.see(result)
            llm_row, meta = result.row(), prompt.meta
        else:
            llm_row = _not_asked()
        predicted = {symbol_of[c] for c in llm_row["selected"]}
        core, derived = baselines.core_symbols(case), baselines.core_and_derived_symbols(case)
        e0 = baselines.e0_predict(ev)
        n = len(ev["candidates"])
        rows.append({
            "id": cid, "created": entry.get("created"), "cluster_key": materialize.d1_cluster_key(case),
            "evidence_status": ev["status"], "n_candidates": n, "n_hunks": len(ev["hunks"]), "n_gold_core": len(core),
            "prompt_meta": meta, "llm": llm_row, "selected_symbols": sorted(predicted),
            "m": {"llm": {"core": st.set_metrics(predicted, core), "core_derived": st.set_metrics(predicted, derived)},
                  "e0": {"core": st.set_metrics(e0, core), "core_derived": st.set_metrics(e0, derived)}}})
        if progress:
            progress(i, len(entries), f"{cid} {llm_row['status']}")
    return {"schema_version": SCHEMA_VERSION, "experiment": "E1", "mode": MODE_FIX, "dataset": "D1",
            "max_selected": MAX_SELECTED[MODE_FIX], "case_count": len(entries), "scored_count": len(rows),
            "counts": counts([r["llm"] for r in rows]), "wall_seconds": round(time.monotonic() - t0, 1), "rows": rows}


# --- S1 --------------------------------------------------------------------------------------------
def run_s1(harness, cfg, variant: str, k: int, client: LLMClient,
           progress: Callable[[int, int, str], None] | None = None) -> dict[str, Any]:
    """`harness` is a CP4 `Harness` (cases, ranges, retrievers); `cfg` the fixed retriever's Config."""
    guard = _ErrorGuard()
    rows = []
    t0 = time.monotonic()
    n_cases = len(harness.cases)
    for i, case in enumerate(harness.cases, start=1):
        ranking = harness.rank_case(cfg, case, variant)
        topk = ranking[:k]
        chunk_of = {c.candidate_id: c for c in harness.ranges.get(case.range_key, [])}
        meta: dict[str, Any] = {}
        if topk:
            prompt = build_topk_prompt(TopkPromptInput(QueryInput(case.summary, case.details), tuple(topk_candidate(chunk_of[c]) for c in topk)))
            result = sel.select(client, prompt)
            guard.see(result)
            llm_row, meta = result.row(), prompt.meta
        else:
            llm_row = _not_asked()
        chosen = set(llm_row["selected"])
        top1 = set(ranking[:1])
        first = next((j for j, c in enumerate(ranking, start=1) if c in case.gold_core), None)
        rows.append({
            "id": case.case_id, "created": case.created, "cluster_key": case.cluster_key, "n_candidates": len(ranking),
            "n_gold_core": len(case.gold_core), "n_gold_core_derived": len(case.gold_core_derived),
            "gold_in_topk": bool(case.gold_core & set(topk)), "gold_derived_in_topk": bool(case.gold_core_derived & set(topk)),
            "retriever_first_rank": first, "topk_ids": topk, "prompt_meta": meta, "llm": llm_row,
            "m": {"llm": {"core": st.set_metrics(chosen, case.gold_core),
                          "core_derived": st.set_metrics(chosen, case.gold_core_derived)},
                  "top1": {"core": st.set_metrics(top1, case.gold_core),
                           "core_derived": st.set_metrics(top1, case.gold_core_derived)}}})
        if progress:
            progress(i, n_cases, f"{case.case_id} {llm_row['status']}")
    return {"schema_version": SCHEMA_VERSION, "experiment": "S1", "mode": MODE_RELEASE, "dataset": "D4", "k": k,
            "retriever": {"config": cfg.name, "variant": variant}, "max_selected": MAX_SELECTED[MODE_RELEASE],
            "case_count": n_cases, "scored_count": len(rows), "counts": counts([r["llm"] for r in rows]),
            "wall_seconds": round(time.monotonic() - t0, 1), "rows": rows}

