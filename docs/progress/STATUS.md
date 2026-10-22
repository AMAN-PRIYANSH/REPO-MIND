# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP5 - Local LLM layer, root-cause selection, HyDE**
- State: `AWAITING_REVIEW` (criterion 6 NOT MET: no real LLM run; needs the owner's Colab run)
- Branch in use: `claude/vulntrace-ai-build-o31zls`
- Specification: [checkpoints/CP5.md](../implementation/checkpoints/CP5.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | APPROVED | claude/vulntrace-ai-build-9qhbjg | [CP4_REPORT](reports/CP4_REPORT.md) |
| CP5 | Local LLM layer, root-cause selection, HyDE | AWAITING_REVIEW (no real run yet) | claude/vulntrace-ai-build-o31zls | [CP5_REPORT](reports/CP5_REPORT.md) |
| CP5b | Lifting and caller/callee queries (Go helper) | NOT_RELEASED | - | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [x] 0a Neutral headline + paired method-vs-method rows in CP4 renderer; regenerate CP4 results doc
- [x] 0b Notebook import path line in CP4 notebook (CP5 notebook gets it when written; test globs all notebooks)
- [x] 0c Retrieval config file (fixed retriever) read by harness
- [x] 1 LLMClient (real, endpoint rule, fake, call records)
- [x] 2 Response cache (no prompts/responses committed)
- [x] 3 Prompts + closed-set validation + injection tests
- [x] 4 HyDE
- [x] 5 Eval commands (select fix/release, retrieval --hyde) + JSON results + renderer
- [x] 6 Contamination split
- [x] 7 Models config (max two, tags/digests recorded in Colab)
- [x] 8 Colab notebook written + tested; fake-LLM dry run on real D1/D4 evidence done (CP5_DRYRUN.log). NOT executed in Colab
- [x] 9 Tests (unit + integration)
- [x] 10a Results doc generator code (docs/results/CP5_LLM_RESULTS.md still to be generated from the real run)
- [x] 11 Report CP5_REPORT.md, AWAITING_REVIEW
- [ ] (open) real Colab run of E1/S1/HyDE -> commit docs/results/cp5/ and render CP5_LLM_RESULTS.md

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP5: all code, tests, notebook and dry run done; the only missing piece is the real Colab run (owner runs notebooks/cp5_llm_colab.ipynb, hands over cp5_results.zip). Next session: unzip into docs/results/cp5/, render CP5_LLM_RESULTS.md, check invalid rates, add results section to the report. Earlier note: CP4 was approved on 22 Oct 2026; read the review notes in checkpoints/CP3.md and CP4.md - they bind CP5. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists.)
