# CP6 - LangGraph investigation agent (Mode 2)

- Recommended model: **Opus 5.5**, effort **high** (agent design and failure handling; keep the session focused)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days, plus one Colab run by the owner
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `CP4.md`, `CP5.md`, `CP5b.md` (**review notes at the end of each bind this checkpoint**), `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 4, 5 "Agent tools", and the helper contract), `docs/design/DATA_MODEL.md`, `docs/evaluation/EVALUATION_PLAN.md`, `docs/decisions/RISKS_AND_OPEN_QUESTIONS.md`

## Goal

Build one investigation agent (LangGraph) for **Mode 2** (no fix commit; candidates are the functions changed between the vulnerable and fixed releases) and measure it honestly against the best non-agent pipeline on D4. The question is not "does an agent sound clever" but "does it beat retrieval top-k and the one-shot LLM (S1), and what does it cost?"

An agent is justified only if it wins on a measured number. A negative result is an acceptable, reportable outcome.

## Findings that shape this checkpoint (from CP5 and CP5b reviews)

- E1 showed an LLM that picks **one** function loses recall. The agent therefore returns a **ranked list** (at most 3 IDs), never a single forced pick, and is scored at top-1 and top-3.
- S1: llama3.1-8b beat retrieval top-1 modestly; qwen2.5-coder abstained heavily under a prompt that invites abstention. The agent protocol must make abstention rare and explicit, and report it.
- HyDE is weak: the agent does not use HyDE.
- D4 ceiling: graph expansion has weak support (1 of 17 within 1 hop). `callers`/`callees` are an **ablation arm**, not an expected win.
- Local 7-8B models are unreliable at native tool calling. Use a **JSON action protocol** (the model emits one JSON action per turn; code parses and validates it), not provider-specific tool calling. Invalid actions are counted and given one repair turn.

## Deliverables

1. **Agent graph** - `src/vulntrace/agent/`
   - LangGraph state graph: `plan/act` loop -> tool executor -> budget check -> back, ending in `submit_answer` or a budget stop. State holds the candidate pool, history, steps used, tokens used.
   - Tools (contract in `INTERFACES_AND_CONTRACTS.md` section 5): `search_code`, `read_function`, `search_commits`, `show_commit`, `submit_answer`, and (ablation arm only) `callers`, `callees`.
   - `search_code` uses the fixed CP4 retriever (`hybrid:bge-small`, `code+commits` chunks) behind the existing interface. `read_function` and `show_commit` answer only for candidates and commits of the current case (closed pool; anything else returns an error observation, never data). Tool outputs are truncated to a stated budget.
   - `callers`/`callees` read **precomputed** neighbour tables (built by CP5b helper modes in a session with Go and the module proxy, stored in the gitignored evidence directory) so the Colab run needs no Go. If the tables cannot be built for some cases, those cases run without the tools and the count is reported.
   - `submit_answer`: ordered list of 1-3 candidate IDs plus cited evidence (function IDs or commit SHAs seen in the trace). IDs outside the pool are rejected with one retry; a second failure is `INVALID_ANSWER` (counted, scored as a miss). An explicit `abstain` is allowed, counted, and scored as a miss.
   - Budgets (recorded in every run): max steps (default 8), max tool-output characters per call, max total prompt tokens, wall-clock limit per case. A budget stop scores as a miss and is counted by reason.
   - Temperature 0, fixed seed. Full trace (every prompt hash, raw response, parsed action, tool result summary, timings, token counts) saved per case.

2. **Prompts** - versioned, frozen files in `src/vulntrace/agent/prompts/` (`agent_system_v1`, `agent_repair_v1`). **Freeze them before the first real run. Do not edit them after seeing D4 results.** If a second version is tried it is reported as a separate, labelled post-hoc row, never replacing v1.

3. **Fake LLM and fake tools for tests** (per `INTERFACES_AND_CONTRACTS.md`): scripted action sequences covering: normal success, invalid JSON then repair, out-of-pool ID, budget stop by steps, by tokens, by time, abstention, repeated identical tool call loop (stop with `LOOP_DETECTED`), tool error. No test downloads or calls a model.

4. **Evaluation** - `python -m vulntrace eval symbols --strategy agent --set d4`
   - Arms, all on the same D4 cases and the same two local models as CP5: **A0** retrieval top-1 and top-3 (`hybrid:bge-small`); **A1** S1 top-10 from the committed CP5 results (reused, no re-run); **A2** agent without graph tools; **A3** agent with `callers`/`callees`.
   - Metrics: any-hit@1, any-hit@3, precision@1, MRR where defined, on both denominators used in CP4 (gold inside the candidate set; all scored cases), cluster bootstrap 95% intervals on D4 clusters, **paired** differences against A0 and A1.
   - Cost: steps per case, tokens per case, wall-clock per case, and the rates of invalid action, repaired action, abstention, loop stop, budget stop, by reason. The cost table is part of the headline, not an appendix.
   - Contamination split by model cutoff, as in CP5.
   - Failure analysis: list at least 10 cases where the agent was wrong and read their traces; classify the cause (wrong tool use, ignored evidence, gave up, format failure, label convention). Show 2 worked traces, one success and one failure.
   - Results to `docs/results/cp6/` as JSON (no prompts with code text, per-file size under 512 KiB; traces may be stored compressed outside git and summarised in the results), rendered by code to `docs/results/CP6_AGENT_RESULTS.md`.

5. **Colab notebook** `notebooks/cp6_agent_colab.ipynb`, same rules as CP5: evidence on local Colab disk, evidence gate, `sys.path` line, resumable cache, real-generate check for Ollama, results zip. The owner runs it; the session does not need models.

6. **Tests** - unit (graph transitions, budgets, validation, loop detection), contract (tool schemas, trace schema), integration with fakes end to end. CI green. Nothing needs the network.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Agent graph and all tools implemented; closed pool enforced; budgets recorded. | Tests |
| 2 | Prompts frozen before any real run; commit order shows it. | `git log` |
| 3 | Fake-driven tests cover every failure path listed in deliverable 3. | Test summary |
| 4 | Notebook ready with gate, resume and real-generate check; ready for the owner's run. | Notebook, report |
| 5 | After the owner's run: A0-A3 table with paired intervals, both denominators, cost table, failure counts by reason. | Results doc |
| 6 | At least 10 failure cases classified from traces, 2 worked traces. | Results doc |
| 7 | Honest headline: states plainly whether the agent beats A0 and A1 and at what cost; a negative result is stated as such. | Results doc |
| 8 | All tests pass locally and in CI; no `data/`, caches, models or traces with code text committed. | Printed summaries, `git ls-files` |
| 9 | Report `docs/progress/reports/CP6_REPORT.md`; STATUS `AWAITING_REVIEW` (after the owner's Colab results are committed, or `AWAITING_COLAB` if the code is done but the run is not). | Files |

## Out of scope

Verifier, end-to-end triage, Mode 1 agent, real applications, multi-agent (CP8), any change to retrievers, HyDE, any paid API. Do not tune prompts, budgets or models on D4 results.

## Known risks

- 7-8B models may loop or emit invalid actions often; that is a result. Report rates, do not hide them by silent repair.
- Context limits: tool output truncation matters more than clever prompting.
- A run can be long on a free T4; keep it resumable and report what did not finish.
- With 94 clusters, intervals will be wide; say "no detectable difference" when the interval includes 0.

## Review notes

(The supervising assistant adds notes here.)

**Supervisor review, 26 Oct 2026 - APPROVED as a negative result** (branch `claude/vulntrace-ai-build-1wfa8e` at `ff4d63b`, which carries `claude/gracious-carson-ch1i9r` and the owner's Colab run).

Checked by the supervisor: `pytest tests/unit tests/contract` -> 621 passed, 10 skipped; CI green on every commit of the branch including the last (the builder reported the last three as unconfirmed; they passed). The owner's `cp6_results.zip` was checked before the results session (valid zip, 118 traces per arm and model, evidence identical to the committed summary). The headline numbers were recomputed from the committed result files (any-hit@1 against A0, per model's headline group; the supervisor's group sizes differ by two cases because of a simple date filter, differences agree to within 0.004). No traces, caches or `data/` are tracked; every result file is under 512 KiB.

What the results say (numbers in `docs/results/CP6_AGENT_RESULTS.md`):

1. **The agent does not beat plain retrieval (A0).** llama3.1-8b: A2 and A3 both equal A0 at top-1 (difference 0.000). qwen2.5-coder-7b: A2 is worse than A0 by about 0.21 (interval excludes 0); A3 is lower by about 0.09.
2. **The only win is over a weak baseline** (qwen A3 over the one-shot A1, which answered only 35% of cases); this is not evidence for the agent.
3. **Cost is high:** about 5 times the prompt tokens and about twice the seconds of the one-shot LLM.
4. **qwen's loss is mostly the frozen loop rule:** 40 of 118 A2 runs ended with `LOOP_DETECTED` and no answer; in 18 of them A0's top-1 was right. Whether a looser rule changes the verdict is untested. Do not tune it on D4; a v2 would need a labelled post-hoc row.
5. **The builder changed the renderer's headline after seeing the results** (the original sentence was true only because of the weak-A1 win). No prompt, budget or number changed, and the change is disclosed as deviations 16-17. Accepted: the new wording is the more honest one. The rule stays: headline wording is fixed before results are seen.
6. The failure analysis is a purposive sample (18 cases chosen to cover stop reasons, models and arms), so cause counts are not rates. The three "label convention" calls were not checked against code.

Design decision for CP7 (binding): **the end-to-end pipeline does not use the agent.** Mode 2 uses the retriever's top-k (A0) as its candidate list; the agent stays in the repository as a measured negative result and as the starting point for CP8's optional experiment. An interview-ready sentence: "I built the agent, measured it against the strongest simple baseline, and it did not win, so the product uses retrieval."
