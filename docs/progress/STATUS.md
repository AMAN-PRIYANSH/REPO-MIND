# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP6 - LangGraph investigation agent (Mode 2)**
- State: `AWAITING_REVIEW` (owner's Colab results committed, results document, failure analysis and report done; headline: the agent does not beat retrieval A0, a negative result)
- Branch in use: `claude/vulntrace-ai-build-1wfa8e` (continues `claude/gracious-carson-ch1i9r`, fast-forwarded at `0f4310c`)
- Specification: [checkpoints/CP6.md](../implementation/checkpoints/CP6.md)

State values: `READY` → `IN_PROGRESS` → (`AWAITING_COLAB` →) `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | APPROVED | claude/vulntrace-ai-build-9qhbjg | [CP4_REPORT](reports/CP4_REPORT.md) |
| CP5 | Local LLM layer, root-cause selection, HyDE | APPROVED | claude/vulntrace-ai-build-o31zls | [CP5_REPORT](reports/CP5_REPORT.md) |
| CP5b | Lifting and caller/callee queries (Go helper) | APPROVED | claude/eloquent-shannon-baphva | [CP5b_REPORT](reports/CP5b_REPORT.md) |
| CP6 | LangGraph investigation agent | AWAITING_REVIEW | claude/vulntrace-ai-build-1wfa8e (continues claude/gracious-carson-ch1i9r) | [CP6_REPORT](reports/CP6_REPORT.md) |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

CP6 (from the specification's deliverables):

- [x] D1 Agent graph (`src/vulntrace/agent/`): LangGraph loop act -> tools -> budget check; state (pool, history, steps, tokens); tools `search_code`, `read_function`, `search_commits`, `show_commit`, `submit_answer`, ablation `callers`/`callees` from precomputed neighbour tables; closed pool; truncation budget; submit validation (1-3 IDs, cited evidence, one retry, `INVALID_ANSWER`, `abstain`); budgets (steps, chars per call, prompt tokens, wall clock) recorded; temperature 0, fixed seed; full trace per case
- [x] D1b Neighbour tables for `callers`/`callees` built from CP5b helper modes (gitignored evidence dir), counts of cases without tables
- [x] D2 Prompts `agent_system_v1`, `agent_repair_v1` frozen before any real run
- [x] D3 Fake LLM and fake tools; scripted sequences for: success, invalid JSON then repair, out-of-pool ID, budget stop by steps / tokens / time, abstention, `LOOP_DETECTED`, tool error
- [x] D4 `eval symbols --strategy agent --set d4`: arms A0-A3, metrics with both denominators, cluster bootstrap, paired vs A0 and A1, cost table, contamination split, failure analysis tooling, results JSON in `docs/results/cp6/`, renderer to `docs/results/CP6_AGENT_RESULTS.md`
- [x] D5 Colab notebook `notebooks/cp6_agent_colab.ipynb` (gate, `sys.path`, resumable cache, real-generate check, results zip)
- [x] D6 Tests: unit, contract, integration with fakes; CI green
- [x] Dry run with the fake LLM on real D4 evidence (session)
- [x] Owner's Colab run (A2/A3 real numbers), failure analysis from real traces (18 cases, 2 worked traces), honest headline
- [x] Report `docs/progress/reports/CP6_REPORT.md` (updated with the real results)

## Handoff notes

CP6 is complete and waits for review (26 Oct 2026, branch `claude/vulntrace-ai-build-1wfa8e`, continuing `claude/gracious-carson-ch1i9r`). Results: `docs/results/CP6_AGENT_RESULTS.md` (generated), files in `docs/results/cp6/`. Headline: the agent does not beat retrieval (A0) on any-hit@1 for either model; it beats A1 only for qwen A3 (A1 answered 35% of cases); it costs about 5x the prompt tokens of S1. Read report sections 7 (deviations 16-19: renderer wording and two tables were changed after the results were seen) and 8 before judging. Not done on purpose: second seed, post-hoc v2, any prompt or budget change. Nothing for the next session to do on CP6 unless the review requests changes. CP7 is NOT_RELEASED.

(CP5b was approved on 23 Oct 2026; the review notes at the end of checkpoints/CP3.md to CP5b.md bind later checkpoints. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists.)
