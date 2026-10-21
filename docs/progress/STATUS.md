# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP3 - Advisory dataset, fix evidence, release ranges, baselines (+ CI)**
- State: `APPROVED` (merged into main)
- Branch in use: `claude/lucid-fermi-9esjyw`
- Specification: [checkpoints/CP3.md](../implementation/checkpoints/CP3.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | NOT_RELEASED | - | - |
| CP5 | Local LLM layer, root-cause selection, HyDE, lifting, Colab runs | NOT_RELEASED | - | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [x] Task 0a: package-not-in-program contract change (reach -> NO_PATH, details.package_not_in_program)
- [x] Task 0b: GitHub Actions CI workflow (first run green: https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39615369023)
- [x] Task 0c: generic symbols in linker method (attempt - bare generic functions now PRESENT via prefix match; generic methods still UNSUPPORTED_SYMBOL_FORM)
- [x] D1. vulndb snapshot pinned (config file); licence recorded
- [x] D2. Report reader and VulnCase builder + schema
- [x] D3. Mode 1 FixEvidence extraction + schema
- [x] D4. Mode 2 ReleaseRange extraction + schema
- [x] D5. D1 and D4 datasets built and committed (case lists) - D1: 150 cases; D4: 120 cases (third build attempt, both bug fixes applied)
- [x] D6. Baselines E0 (D1) and B-ID (D4) with metrics - both scored on real data
- [x] D7. Ceiling investigation (Q8) - run for real on D4 data
- [x] D8. Tests (unit, integration, opt-in network smoke)
- [x] D9. Results document docs/results/CP3_DATASETS_AND_BASELINES.md
- [x] CP3 report written; STATUS set to AWAITING_REVIEW

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP3: started 21 Oct 2026 on branch `claude/lucid-fermi-9esjyw`. All tasks and deliverables (0a-0c, D1-D9) done and pushed - see commit log and `docs/progress/reports/CP3_REPORT.md` for the full account.

D1: 150 cases committed (144 AVAILABLE, 4 EMPTY, 2 UNAVAILABLE, from 506 eligible). E0 baseline on the real D1 result: precision 0.584, recall 0.845, f1 0.631 (core symbols).

D4 took three build attempts - the first two were killed deliberately after finding and fixing real bugs (TRUNCATED-but-large cases undercounted, `d12c28a`; an unhandled subprocess timeout, `c96d904`; a broken exploration order found by code review, not a test failure, `48aec8a`) rather than trusting partial or buggy output. The third attempt, under both fixes, finished cleanly: 120 cases committed (103 AVAILABLE, 2 EMPTY, 14 TRUNCATED, 1 PSEUDO_VERSION_UNRESOLVED, from 500 eligible; 38 cases found with >100 candidates against a target of 25). B-ID baseline on the real D4 result: precision 0.490, recall 0.295, f1 0.193. Ceiling investigation run for real: 119 cases checked, 31 with a missing core symbol (57 EXISTS_UNCHANGED, 4 NOT_FOUND_EITHER_VERSION).

Full non-network test suite: 311 passed, 2 skipped (opt-in network tests only). Go helper tests: pass. CI green on all 14/14 runs on this branch, confirmed via the Actions API.

CP3_REPORT.md is written. State is now AWAITING_REVIEW. Do not start CP4; the owner and supervising assistant review next.)
