# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP5b - Lifting and caller/callee queries (Go helper)**
- State: `IN_PROGRESS`
- Branch in use: `claude/eloquent-shannon-baphva`
- Specification: [checkpoints/CP5b.md](../implementation/checkpoints/CP5b.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | APPROVED | claude/vulntrace-ai-build-9qhbjg | [CP4_REPORT](reports/CP4_REPORT.md) |
| CP5 | Local LLM layer, root-cause selection, HyDE | APPROVED | claude/vulntrace-ai-build-o31zls | [CP5_REPORT](reports/CP5_REPORT.md) |
| CP5b | Lifting and caller/callee queries (Go helper) | IN_PROGRESS | claude/eloquent-shannon-baphva | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [ ] Task 0a: D1 first-pass materialize mismatch (cause, one-pass fix, test, remove notebook workaround)
- [ ] Task 0b: Ollama install check in CP5 notebook
- [ ] Task 0c: correct GO-2020-0006 in D4_cases.json (+ counts, gate expectations)
- [ ] Task 0d: HyDE table comparison count note; regenerate CP5_LLM_RESULTS.md
- [ ] D1: helper `lift` mode (NEAREST + ALL, depth limit, ROOT_ONLY, LOAD_FAILED)
- [ ] D2: helper `callers` / `callees` modes + Python wrappers + schema entries
- [ ] D3: lifting fixtures (observed truths)
- [ ] D4: `eval lift` on D1, E1+L, D4 ceiling; results/cp5b/ + docs/results/CP5B_LIFTING_RESULTS.md
- [ ] D5: tests (Go, Python contract, integration)
- [ ] Report CP5b_REPORT.md, STATE AWAITING_REVIEW

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP5b: none yet. CP5 was approved on 22 Oct 2026; read the review notes in checkpoints/CP3.md, CP4.md and CP5.md - they bind CP5b. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists.)
