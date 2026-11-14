# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP8 - Final report, README and interview notes**
- State: `IN_PROGRESS`
- Branch in use: `claude/vulntrace-ai-build-5f8jgi`
- Specification: [checkpoints/CP8.md](../implementation/checkpoints/CP8.md)

State values: `READY` → `IN_PROGRESS` → (`AWAITING_COLAB` / `AWAITING_ADJUDICATION` →) `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | APPROVED | claude/vulntrace-ai-build-9qhbjg | [CP4_REPORT](reports/CP4_REPORT.md) |
| CP5 | Local LLM layer, root-cause selection, HyDE | APPROVED | claude/vulntrace-ai-build-o31zls | [CP5_REPORT](reports/CP5_REPORT.md) |
| CP5b | Lifting and caller/callee queries (Go helper) | APPROVED | claude/eloquent-shannon-baphva | [CP5b_REPORT](reports/CP5b_REPORT.md) |
| CP6 | LangGraph investigation agent (negative result) | APPROVED | claude/vulntrace-ai-build-1wfa8e | [CP6_REPORT](reports/CP6_REPORT.md) |
| CP7 | End-to-end triage and evidence verifier | APPROVED | claude/vulntrace-ai-build-exhh01 | [CP7_REPORT](reports/CP7_REPORT.md) |
| CP7b | Real applications (D3) and demo | APPROVED | claude/eloquent-newton-vr2093 | [CP7b_REPORT](reports/CP7b_REPORT.md) |
| CP8 | Final report, README and interview notes (multi-agent dropped) | IN_PROGRESS | claude/vulntrace-ai-build-5f8jgi | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [ ] 1. Results summary generator: `python -m vulntrace results summary` -> `docs/results/SUMMARY.md` + `summary.json`; regeneration test
- [ ] 2. README.md (repo root): what/how (Mermaid)/key results/negative results/quickstart/map/licence; number-check test
- [ ] 3. `docs/FINAL_REPORT.md`
- [ ] 4. `docs/INTERVIEW_NOTES.md`; number-check test
- [ ] 5. Housekeeping: list stale/contradictory docs; "superseded by" notes where needed (SUPERVISOR_HANDOFF.md is NOT touched)
- [ ] 6. Tests: summary regeneration, README/interview number checks, relative-link check; CI green on the last commit
- [ ] 7. Quickstart run offline on a fixture (output pasted into report); `CP8_REPORT.md`; STATUS `AWAITING_REVIEW`

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP7b was approved on 14 Nov 2026; read the review notes at the end of checkpoints/CP3.md to CP7b.md - they bind CP8, especially the wording limits. CP8 needs no `data/`, no models and no network beyond GitHub.)
