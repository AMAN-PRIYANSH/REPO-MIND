# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP4 - Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker**
- State: `READY` (released, not started)
- Branch in use: (none yet - the first session writes its own `claude/...` session branch here; see `CLAUDE.md` section 5)
- Specification: [checkpoints/CP4.md](../implementation/checkpoints/CP4.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | READY | - | - |
| CP5 | Local LLM layer, root-cause selection, HyDE, lifting, Colab runs | NOT_RELEASED | - | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [ ] (CP4 not started)

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP4: none yet. CP3 was approved on 21 Oct 2026; read its review notes in checkpoints/CP3.md - findings 1-5 bind CP4. The CP3 D4 evidence in `data/` is NOT available: CP4 task 0a re-materialises it from the 120 fixed IDs.)
