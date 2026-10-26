"""The generated CP6 results document (`docs/results/CP6_AGENT_RESULTS.md`, deliverable 4).

Reads the agent result files (`agent__<arm>__<model>.json`) of one directory and, for arm A1, the
committed CP5 S1 files (`select_release__<model>__k10.json`), and computes every number here:

- per case and arm a ranked list of at most 3 candidate IDs - A0 the retriever's top 3, A1 the S1
  selection in the order the model gave (S1 was not asked to rank, so A1@1 uses its first listed
  ID), A2/A3 the agent's answer;
- any-hit@1, any-hit@3, MRR@3 (1/rank of the first gold ID within the list, else 0) and precision@1
  over answered cases, on two denominators: (b) all D4 cases, (a) cases with a gold function among
  the candidates;
- cluster-bootstrap 95% intervals on D4 clusters and **paired** differences on the same draws;
- the cost table (steps, tokens, time, failure rates by reason) as part of the headline;
- the contamination split by model cutoff, as in CP5.

Wording rule (as CP5): an arm is called better or worse only when the paired interval excludes 0;
otherwise "no detectable difference". The first paragraph states the main finding, including a
negative one, and the cost.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np

from vulntrace.eval import cp5_stats as st
from vulntrace.eval.llm_report import _ci, _f, contamination_counts, group_defs, verdict
from vulntrace.paths import REPO_ROOT

ARMS = ("A0", "A1", "A2", "A3")
ARM_LABEL = {"A0": "A0 retrieval top-1 / top-3", "A1": "A1 S1 top-10 selection (CP5, reused)",
             "A2": "A2 agent, no graph tools", "A3": "A3 agent + callers/callees"}
COLS = ("hit1", "hit3", "mrr3", "answered")
PAIRS = (("A2", "A0"), ("A2", "A1"), ("A3", "A0"), ("A3", "A1"), ("A3", "A2"))
CP5_DIR = REPO_ROOT / "docs" / "results" / "cp5"
CP4_HYBRID_RUN = REPO_ROOT / "docs" / "results" / "cp4" / "runs" / "hybrid_bge-small__code-commits.json"
FAILURE_FILE = "failure_analysis.json"
FAILURE_CLASSES = ("wrong tool use", "ignored evidence", "gave up", "format failure", "label convention",
                   "gold not reachable", "other")


def _load(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def load_cp6(results_dir: Path, cp5_dir: Path = CP5_DIR) -> dict[str, Any]:
    d = Path(results_dir)
    out: dict[str, Any] = {"agent": {}, "a1": {}, "evidence": None, "failures": None, "colab": None}
    for p in sorted(d.glob("agent__*__*.json")):
        doc = _load(p)
        out["agent"][(doc["arm"], doc["model"]["alias"])] = doc
    for alias in sorted({a for _arm, a in out["agent"]}):
        p = Path(cp5_dir) / f"select_release__{alias}__k10.json"
        if p.is_file():
            out["a1"][alias] = _load(p)
    for key, name in (("evidence", "agent_evidence.json"), ("failures", FAILURE_FILE), ("colab", "colab_run.json")):
        if (d / name).is_file():
            out[key] = _load(d / name)
    return out


# --- scoring -----------------------------------------------------------------------------------------
def list_metrics(ranked: list[str], gold: set[str]) -> list[float]:
    top = list(ranked)[:3]
    first = next((i for i, x in enumerate(top, start=1) if x in gold), None)
    return [float(bool(set(top[:1]) & gold)), float(bool(set(top) & gold)), 1.0 / first if first else 0.0,
            float(bool(top))]


def arm_lists(model_docs: dict[str, dict], a1_doc: dict | None) -> tuple[list[dict], dict[str, list[list[str]]], dict]:
    """(case facts, {arm: ranked list per case}, notes) for one model, on the agent files' case list."""
    base_doc = model_docs.get("A2") or model_docs.get("A3")
    cases = [{k: r[k] for k in ("id", "created", "cluster_key", "n_candidates", "gold_ids", "gold_in_candidates", "a0_top3")}
             for r in base_doc["rows"]]
    lists: dict[str, list[list[str]]] = {"A0": [c["a0_top3"] for c in cases]}
    notes: dict[str, Any] = {"a0_mismatch": 0, "a1_missing": []}
    for arm in ("A2", "A3"):
        if arm in model_docs:
            by = {r["id"]: r for r in model_docs[arm]["rows"]}
            lists[arm] = [by[c["id"]]["answer"] if c["id"] in by else [] for c in cases]
            notes["a0_mismatch"] += sum(1 for c in cases if c["id"] in by and by[c["id"]]["a0_top3"] != c["a0_top3"])
    if a1_doc is not None:
        by = {r["id"]: r for r in a1_doc["rows"]}
        out = []
        for c in cases:
            r = by.get(c["id"])
            if r is None:
                notes["a1_missing"].append(c["id"])
                out.append([])
            else:
                out.append(list(r["llm"]["selected"]) if r["llm"]["status"] == "VALID" else [])
        lists["A1"] = out
    return cases, lists, notes


def _matrix(lists: list[list[str]], cases: list[dict]) -> np.ndarray:
    return np.array([list_metrics(L, set(c["gold_ids"])) for L, c in zip(lists, cases)], dtype=np.float64).reshape(len(cases), 4)


def _prec1(lists, cases) -> str:
    vals = [float(bool(set(L[:1]) & set(c["gold_ids"]))) for L, c in zip(lists, cases) if L]
    return f"{_f(float(np.mean(vals)) if vals else float('nan'))} (n={len(vals)})"


def _sub(seq, mask):
    return [x for x, m in zip(seq, mask) if m]


def arms_table(cases, lists, mask) -> list[str]:
    """Arms rows and paired differences for the cases selected by `mask`."""
    sub = _sub(cases, mask)
    if not sub:
        return ["no cases.", ""]
    g = st.Group([c["cluster_key"] for c in sub])
    out = [f"n = {len(sub)} cases ({g.n_clusters} clusters)", "",
           "| Arm | any-hit@1 | any-hit@3 | MRR@3 | precision@1 (answered) | answered |", "|---|---|---|---|---|---|"]
    for arm in ARMS:
        if arm not in lists:
            out.append(f"| {ARM_LABEL[arm]} | not run | | | | |")
            continue
        ls = _sub(lists[arm], mask)
        s = dict(zip(COLS, g.summary(_matrix(ls, sub))))
        out.append(f"| {ARM_LABEL[arm]} | {_ci(s['hit1'])} | {_ci(s['hit3'])} | {_ci(s['mrr3'])} | {_prec1(ls, sub)} | "
                   f"{_ci(s['answered'])} |")
    out.append("")
    rows = []
    for a, b in PAIRS:
        if a in lists and b in lists:
            d = dict(zip(COLS, g.paired(_matrix(_sub(lists[a], mask), sub), _matrix(_sub(lists[b], mask), sub))))
            rows.append(f"| {a} − {b} | {_ci(d['hit1'])} | {_ci(d['hit3'])} | {_ci(d['mrr3'])} | {verdict(d['hit1'])} |")
    if rows:
        out += ["| Paired difference | Δ any-hit@1 | Δ any-hit@3 | Δ MRR@3 | any-hit@1 reading |", "|---|---|---|---|---|", *rows, ""]
    return out


def paired(cases, lists, mask, a, b, col="hit1") -> dict[str, float] | None:
    sub = _sub(cases, mask)
    if not sub or a not in lists or b not in lists:
        return None
    g = st.Group([c["cluster_key"] for c in sub])
    return dict(zip(COLS, g.paired(_matrix(_sub(lists[a], mask), sub), _matrix(_sub(lists[b], mask), sub))))[col]


def mean_of(rows, mask, col) -> dict[str, float] | None:
    sub = _sub(rows, mask)
    return None if not sub else {"mean": float(np.mean([r[col] for r in sub]))}


# --- cost ----------------------------------------------------------------------------------------------
def _stats(vals: list[float]) -> str:
    if not vals:
        return "-"
    a = np.array(vals, dtype=np.float64)
    return f"{a.mean():.1f} / {np.median(a):.1f} / {a.max():.0f}"


def _p(vals: list[float], q: float) -> str:
    return "-" if not vals else f"{np.quantile(np.array(vals, dtype=np.float64), q):.1f}"


def cost_tables(agent: dict, a1: dict) -> list[str]:
    out = ["| Model | Arm | cases run | steps (mean / median / max) | model calls | prompt tokens per case (mean / median / max) | "
           "completion tokens per case | largest prompt of one call | model+tool seconds per case (mean / p50 / p95) | "
           "wall seconds per case (mean) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for alias in sorted({a for _arm, a in agent}):
        if alias in a1:
            rows = [r for r in a1[alias]["rows"] if r["llm"]["status"] != "NOT_ASKED"]
            lat = [r["llm"]["latency_s"] for r in rows]
            out.append(f"| `{alias}` | A1 (CP5 S1, one call + at most one retry) | {len(rows)} | 1 / 1 / 1 | "
                       f"{_stats([len(r['llm']['attempts']) for r in rows])} | {_stats([r['llm']['input_tokens'] for r in rows])} | "
                       f"{_stats([r['llm']['output_tokens'] for r in rows])} | "
                       f"{max((a['input_tokens'] or 0 for r in rows for a in r['llm']['attempts']), default=0)} | "
                       f"{_stats(lat).split(' / ')[0]} / {_p(lat, .5)} / {_p(lat, .95)} | - |")
        for arm in ("A2", "A3"):
            doc = agent.get((arm, alias))
            if doc is None:
                continue
            rows = [r for r in doc["rows"] if r["stop_reason"] != "NOT_RUN"]
            sec = [r["agent_seconds"] for r in rows]
            out.append(f"| `{alias}` | {arm} | {len(rows)} | {_stats([r['steps'] for r in rows])} | "
                       f"{_stats([r['llm_calls'] for r in rows])} | {_stats([r['input_tokens'] for r in rows])} | "
                       f"{_stats([r['output_tokens'] for r in rows])} | {max((r['max_call_prompt_tokens'] for r in rows), default=0)} | "
                       f"{_stats(sec).split(' / ')[0]} / {_p(sec, .5)} / {_p(sec, .95)} | "
                       f"{_stats([r['wall_seconds'] for r in rows]).split(' / ')[0]} |")
    out += ["", "Model seconds are the latencies the server reported for each call (kept in the response cache, so a "
            "resumed run reports the original times); tool seconds are measured. Token counts are the server's.", ""]
    out += ["| Model | Arm | run | submitted | abstained | INVALID_ANSWER | INVALID_ACTION | LOOP_DETECTED | budget stop "
            "(steps / tokens / context / time) | server ERROR | cases with an invalid action | repaired actions | rejected "
            "answers | repeated calls | tool errors | cut outputs | replies cut by max_tokens | graph tools available |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (arm, alias), doc in sorted(agent.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        c = doc["counts"]
        s, b, n = c["stop_reasons"], c["budget_reasons"], c["run"] or 1
        pct = lambda k: f"{k} ({100 * k / n:.0f}%)"  # noqa: E731
        out.append(f"| `{alias}` | {arm} | {c['run']} | {pct(s['SUBMITTED'])} | {pct(s['ABSTAINED'])} | {pct(s['INVALID_ANSWER'])} | "
                   f"{pct(s['INVALID_ACTION'])} | {pct(s['LOOP_DETECTED'])} | {b['STEPS']} / {b['TOKENS']} / {b['CONTEXT']} / "
                   f"{b['TIME']} | {s['ERROR']} | {pct(c['cases_with_invalid_action'])} | {c['repaired_actions']} | "
                   f"{c['answer_rejections']} | {c['repeated_calls']} | {c['tool_errors']} | {c['truncated_outputs']} | "
                   f"{c['length_stops']} | {c['graph_tools_available'] if arm == 'A3' else '-'} |")
    return out + [""]


def tool_use_table(agent: dict) -> list[str]:
    tools = sorted({t for doc in agent.values() for r in doc["rows"] for t in r["tool_counts"]})
    out = ["| Model | Arm | " + " | ".join(f"`{t}`" for t in tools) + " | answer IDs all seen in the trace | evidence: candidate IDs / "
           "commit SHAs |", "|---|---|" + "---|" * len(tools) + "---|---|"]
    for (arm, alias), doc in sorted(agent.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        rows = [r for r in doc["rows"] if r["stop_reason"] != "NOT_RUN"]
        n = len(rows) or 1
        answered = [r for r in rows if r["answer"]]
        out.append(f"| `{alias}` | {arm} | " + " | ".join(f"{sum(r['tool_counts'].get(t, 0) for r in rows) / n:.2f}" for t in tools)
                   + f" | {sum(1 for r in answered if r['answer_ids_seen'])} of {len(answered)} | "
                     f"{sum(r['evidence']['candidates'] for r in rows)} / {sum(r['evidence']['commits'] for r in rows)} |")
    return out + ["", "Tool columns: mean calls per case (a repeated identical call counts; it is answered with a note, not run "
                  "again).", ""]


# --- consistency checks --------------------------------------------------------------------------------
def a0_vs_cp4(cases: list[dict]) -> str:
    if not CP4_HYBRID_RUN.is_file():
        return "CP4 run file not found; A0 not compared."
    run = _load(CP4_HYBRID_RUN)
    first = {r["id"]: r["core"]["first_rank"] for r in run["rows"]}
    agree = total = 0
    for c in cases:
        if c["id"] in first:
            total += 1
            fr = first[c["id"]]
            hit3_cp4 = fr is not None and fr <= 3
            hit3_now = bool(set(c["a0_top3"]) & set(c["gold_ids"]))
            agree += hit3_cp4 == hit3_now
    return (f"A0 any-hit@3 agrees with the committed CP4 run of the same retriever on {agree} of {total} cases "
            "(CP4: `docs/results/cp4/runs/hybrid_bge-small__code-commits.json`).")


# --- failure analysis ------------------------------------------------------------------------------------
def failure_section(fa: dict | None) -> list[str]:
    out = ["## Failure analysis (traces read by hand)", ""]
    if not fa:
        return out + ["**Not done yet.** It needs the traces of the owner's real run: at least 10 cases where the agent was "
                      "wrong, each read from its trace and classified (wrong tool use, ignored evidence, gave up, format failure, "
                      "label convention), and two worked traces. Commit the classification as "
                      f"`docs/results/cp6/{FAILURE_FILE}` and re-render.", ""]
    cases = fa.get("cases", [])
    counts: dict[str, int] = {}
    for c in cases:
        counts[c["cause"]] = counts.get(c["cause"], 0) + 1
    out += [f"{len(cases)} wrong cases classified by {fa.get('classified_by', '?')} from their traces "
            f"({fa.get('method', 'agent show-trace')}). Causes: " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + ".", "",
            "| Case | Model | Arm | Stop | Answer | Gold | Cause | What the trace shows |", "|---|---|---|---|---|---|---|---|"]
    for c in cases:
        out.append(f"| {c['id']} | `{c['model']}` | {c['arm']} | {c['stop_reason']} | {', '.join(c.get('answer', [])) or '-'} | "
                   f"{', '.join(c.get('gold', [])) or '-'} | {c['cause']} | {c.get('note', '')} |")
    out.append("")
    for w in fa.get("worked_traces", []):
        out += [f"### Worked trace ({w['kind']}): {w['id']}, `{w['model']}`, {w['arm']}", "", "```", *w["lines"], "```", "",
                w.get("comment", ""), ""]
    return out


# --- document --------------------------------------------------------------------------------------------
def headline(agent: dict, a1: dict, per_model: dict) -> list[str]:
    if not agent:
        return ["**Main finding.** No agent result files in this directory: nothing is claimed.", ""]
    parts = []
    for alias, pm in per_model.items():
        cases, lists, mask, label = pm["cases"], pm["lists"], pm["head_mask"], pm["head_label"]
        n = sum(mask)
        bits = []
        for arm in ("A2", "A3"):
            if arm not in lists:
                continue
            for base in ("A0", "A1"):
                d = paired(cases, lists, mask, arm, base)
                if d is None:
                    continue
                word = ("beats" if d["ci_low"] > 0 else "is worse than" if d["ci_high"] < 0 else
                        "shows no detectable difference from")
                bits.append(f"{arm} {word} {base} on any-hit@1 ({_ci(d)})")
        cost = []
        for arm in ("A2", "A3"):
            doc = agent.get((arm, alias))
            if doc:
                run = [r for r in doc["rows"] if r["stop_reason"] != "NOT_RUN"]
                if run:
                    cost.append(f"{arm} used {np.mean([r['input_tokens'] for r in run]):.0f} prompt tokens and "
                                f"{np.mean([r['agent_seconds'] for r in run]):.1f} model+tool seconds per case")
        if alias in a1:
            asked = [r for r in a1[alias]["rows"] if r["llm"]["status"] != "NOT_ASKED"]
            if asked:
                cost.append(f"A1 used {np.mean([r['llm']['input_tokens'] for r in asked]):.0f} tokens and "
                            f"{np.mean([r['llm']['latency_s'] for r in asked]):.1f} s")
        parts.append(f"`{alias}` ({label}, n = {n}, denominator (b) all cases): " + "; ".join(bits) + ". Cost: "
                     + "; ".join(cost) + ".")
    beat_any = any("beats" in p for p in parts)
    lead = ("**Main finding.** " + ("The agent beats a baseline in at least one comparison below (interval excludes 0). "
                                    if beat_any else
                                    "The agent does not beat the non-agent baselines: no comparison below has an interval "
                                    "that excludes 0 in its favour. "))
    return [lead + " ".join(parts), ""]


def render_cp6_doc(results_dir: Path, source: str, cp5_dir: Path = CP5_DIR) -> str:
    data = load_cp6(results_dir, cp5_dir)
    agent, a1 = data["agent"], data["a1"]
    fake = any(doc.get("dry_run") or doc["model"].get("dry_run") for doc in agent.values())
    lines = ["# CP6 results: the LangGraph investigation agent (Mode 2, D4)", "",
             f"Generated by `python -m vulntrace results render --doc cp6 --input {source}`. Do not edit by hand.", ""]
    if fake:
        lines += ["> **WARNING: some results come from the FAKE LLM and the fake embedder (a dry run).** Their numbers measure "
                  "nothing about any model; they only show that the pipeline runs end to end.", ""]
    per_model: dict[str, dict] = {}
    for alias in sorted({a for _arm, a in agent}):
        model_docs = {arm: doc for (arm, a), doc in agent.items() if a == alias}
        cases, lists, notes = arm_lists(model_docs, a1.get(alias))
        cutoff = next(iter(model_docs.values()))["model"]["cutoff"]
        groups = group_defs(cases, cutoff)
        per_model[alias] = {"cases": cases, "lists": lists, "notes": notes, "cutoff": cutoff, "groups": groups,
                            "head_mask": groups[0][2], "head_label": groups[0][1].replace(" - HEADLINE", "")}
    lines += headline(agent, a1, per_model)
    lines += ["The cost table is part of this headline:", ""] + (cost_tables(agent, a1) if agent else ["(no runs)", ""])
    lines += ["## Setup", ""]
    if agent:
        any_doc = next(iter(agent.values()))
        cfg = any_doc["config"]
        lines += [f"- Arms on the same D4 cases: {'; '.join(ARM_LABEL[a] for a in ARMS)}. A0 is the agent's own automatic "
                  "first search (the fixed retriever on the advisory text), recorded in every row. A1 is read from "
                  "`docs/results/cp5/select_release__<model>__k10.json`; S1 was not asked to rank, so A1@1 is its first "
                  "listed ID (indicative).",
                  f"- Retriever: `{any_doc['retriever']['config']}` [{any_doc['retriever']['variant']}]; embedder "
                  f"{(any_doc.get('embedding_model') or {}).get('model_id')}.",
                  f"- Agent `{cfg['agent']}`, prompts `{cfg['prompt_set']}` (sha256 `{cfg['prompt_sha256'][:16]}...`), "
                  f"LangGraph {any_doc.get('langgraph_version')}, settings {json.dumps(cfg['settings'])}.",
                  f"- Budgets: {json.dumps(cfg['budget'])}. A budget stop, an abstention, `INVALID_ANSWER`, "
                  "`INVALID_ACTION`, `LOOP_DETECTED` and a server error all score as misses.",
                  f"- Agent evidence: commit diffs for {any_doc['agent_evidence']['commit_diffs']['available']} and "
                  f"neighbour tables for {any_doc['agent_evidence']['graph']['available']} of "
                  f"{any_doc['agent_evidence']['graph']['of']} cases. A3 cases without a table run without the graph tools "
                  "(counted in the cost table).",
                  f"- Environment: repository commit {any_doc['environment'].get('repo_commit')}"
                  f"{' (dirty)' if any_doc['environment'].get('repo_dirty') else ''}, GPU "
                  f"{any_doc['environment'].get('gpu')}, Python {any_doc['environment'].get('python_full')}."]
        for (arm, alias), doc in sorted(agent.items()):
            m = doc["model"]
            lines.append(f"- `{alias}` {arm}: tag `{m.get('ollama_tag')}`, digest `{m.get('model_digest')}`, cutoff "
                         f"{m.get('cutoff') or 'undocumented'}; {doc['counts']['run']} cases run, "
                         f"{doc['counts']['reused_traces']} from earlier traces; limit {doc.get('limit')}.")
        lines.append("")
    for alias, pm in per_model.items():
        cases, lists, notes = pm["cases"], pm["lists"], pm["notes"]
        lines += [f"## `{alias}`: arms A0-A3", "", f"Contamination split: {contamination_counts(cases, pm['cutoff'])}.",
                  f"Cases with a gold function among the candidates: {sum(c['gold_in_candidates'] for c in cases)} of "
                  f"{len(cases)}; the others are misses for every arm (the pool is closed).",
                  f"A1 rows missing from the CP5 file: {len(notes['a1_missing'])}"
                  + (f" ({', '.join(notes['a1_missing'][:10])})" if notes["a1_missing"] else "")
                  + f"; A0 lists that differ between the A2 and A3 files: {notes['a0_mismatch']}.", ""]
        if not fake:
            lines += [a0_vs_cp4(cases), ""]
        for key, label, mask in pm["groups"]:
            for dn, dlabel, dmask in (("b", "(b) all cases", [True] * len(cases)),
                                      ("a", "(a) gold among the candidates", [c["gold_in_candidates"] for c in cases])):
                lines += [f"### {label}, denominator {dlabel}", ""]
                lines += arms_table(cases, lists, [m and d for m, d in zip(mask, dmask)])
    if agent:
        lines += ["## Tool use", ""] + tool_use_table(agent)
    lines += failure_section(data["failures"])
    lines += ["## Limits of this measurement", "",
              "- The pool is closed: the agent can only answer with functions the release changed. Cases whose gold function "
              "is not a candidate are misses for every arm; the graph tools cannot add it (they only point to other "
              "candidates). CP5b found a candidate within 1 hop of a missing core symbol in 1 of 17 such cases.",
              "- 7-8B local models, temperature 0, one seed: one run per configuration; run-to-run variance is not measured.",
              "- Intervals are cluster-bootstrap 95% intervals over D4 clusters with about a hundred clusters; many comparisons "
              "are shown and none is corrected for multiplicity, so a single borderline interval is not a finding.",
              "- Prompts and budgets were frozen before the first real run and not tuned on D4.", ""]
    return "\n".join(lines).rstrip() + "\n"
