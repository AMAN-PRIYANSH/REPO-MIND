# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP1 - Ground truth and linker presence**
- State: `IN_PROGRESS`
- Branch in use: `claude/vulntrace-checkpoint-continue-ia7tx5`
- Specification: [checkpoints/CP1.md](../implementation/checkpoints/CP1.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | IN_PROGRESS | claude/vulntrace-checkpoint-continue-ia7tx5 | - |
| CP2 | Go call-graph helper and verdict rule | NOT_RELEASED | - | - |
| CP3 | Advisory dataset, fix evidence, release-range candidates, baselines | NOT_RELEASED | - | - |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | NOT_RELEASED | - | - |
| CP5 | Local LLM layer, root-cause selection, HyDE, lifting, Colab runs | NOT_RELEASED | - | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [x] D1 Python package skeleton (pyproject, src/vulntrace, tests, .gitignore)
- [x] D2 `doctor` command
- [x] D3 Schemas (fixture_manifest, method_result)
- [x] D4 Fixture suite (>=12 cases, inlining case, manifest.json)
- [x] D5 Linker-presence method
- [ ] D6 Scoring command (`fixtures score --method linker`)
- [ ] D7 Tests (unit + integration)
- [ ] D8 Results document `docs/results/CP1_LINKER_RESULTS.md`
- [ ] Report `docs/progress/reports/CP1_REPORT.md`, state -> AWAITING_REVIEW

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(none yet)
