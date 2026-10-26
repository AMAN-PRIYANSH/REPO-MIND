# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP6 - LangGraph investigation agent (Mode 2)**
- State: `IN_PROGRESS` (code done; the owner's Colab run is finished and `cp6_results.zip` exists; the next session does the results steps below)
- Branch in use: `claude/gracious-carson-ch1i9r`
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
| CP6 | LangGraph investigation agent | IN_PROGRESS | claude/gracious-carson-ch1i9r | [CP6_REPORT](reports/CP6_REPORT.md) |
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
- [ ] Owner's Colab run (A2/A3 real numbers), failure analysis from real traces, honest headline
- [x] Report `docs/progress/reports/CP6_REPORT.md` (first version; update after the Colab run)

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

CP6 (26 Oct 2026, branch `claude/gracious-carson-ch1i9r`). **Done:** agent code, prompts `agent_v1` frozen at `42da9a4` (before any real run; no model has seen them), tests (734 passed locally, CI green), renderer, notebook, D4 evidence + commit diffs + neighbour tables built in the session (summary committed as `docs/results/cp6/agent_evidence.json`), dry run on real evidence. The neighbour tables were handed to the owner as `cp6_graph_tables.zip` (sha256 613734f574f0197ed2cf3e9de18cb7ae7c043e34172ba70db1f1dc14dbcebe1e).
**Not done (needs the owner's run):** real A2/A3 results, failure analysis, worked traces, honest headline (criteria 5-7).
**Owner:** upload `cp6_graph_tables.zip` to `MyDrive/vulntrace_cp6/`, then run the notebook once per PART (1-4, one Colab session each; re-run a PART that was cut off). The zip from PART 4 holds all results.
**Supervisor note, 26 Oct 2026:** the owner's four Colab parts are done; `cp6_results.zip` (479 files: 4 result files + 472 traces) was checked by the supervisor (zip valid, 118 traces per arm and model, evidence tables identical to the committed summary). State was set from AWAITING_COLAB to IN_PROGRESS so that a new session continues on this branch (CLAUDE.md section 5 only continues IN_PROGRESS or CHANGES_REQUESTED).
**Next session, after receiving `cp6_results.zip`:**
1. Unzip into the scratch area. Copy only `cp6/*.json` into `docs/results/cp6/` (keep `agent_evidence.json` as committed; add `agent_evidence_colab.json`, `colab_run.json`, `D4_materialize_colab.json`, `model_problems.json`). Never commit `traces/`. Check each file is < 512 KiB, no `dry_run`, and the `counts.run` of every arm file (expect 118).
2. `python -m vulntrace results render --doc cp6 --input docs/results/cp6 --out docs/results/CP6_AGENT_RESULTS.md`.
3. Failure analysis: rebuild D4 evidence (`dataset materialize --set d4`) for function names, then read at least 10 wrong cases with `python -m vulntrace agent show-trace --trace <traces/...>.json.gz --data-dir data` (add `--raw` for the replies). Write `docs/results/cp6/failure_analysis.json`: `{"classified_by", "method", "cases": [{"id","model","arm","stop_reason","answer","gold","cause","note"}], "worked_traces": [{"kind": "success"|"failure","id","model","arm","lines": [show-trace lines, no code],"comment"}]}`. Causes: wrong tool use, ignored evidence, gave up, format failure, label convention (plus gold not reachable / other). Re-render.
4. Update `CP6_REPORT.md` (sections 4-6, criteria 5-7) with the real numbers copied from the document; set STATE `AWAITING_REVIEW`.
Do not edit prompts or budgets after seeing results; a v2 would be a separate, labelled post-hoc row.

(CP5b was approved on 23 Oct 2026; read the review notes at the end of checkpoints/CP3.md to CP5b.md - they bind CP6. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists.)
