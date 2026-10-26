# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP7 - End-to-end triage and evidence verifier**
- State: `IN_PROGRESS`
- Branch in use: `claude/vulntrace-ai-build-exhh01`
- Specification: [checkpoints/CP7.md](../implementation/checkpoints/CP7.md)

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
| CP6 | LangGraph investigation agent (negative result) | APPROVED | claude/vulntrace-ai-build-1wfa8e | [CP6_REPORT](reports/CP6_REPORT.md) |
| CP7 | End-to-end triage and evidence verifier | IN_PROGRESS | claude/vulntrace-ai-build-exhh01 | - |
| CP7b | Real applications (D3) and demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

CP7 (started 26 Oct 2026 on `claude/vulntrace-ai-build-exhh01`, fresh from `main`; no earlier CP7 branch existed):

- [ ] 0. Environment check recorded (OS, Python, Go, git, Docker, network)
- [ ] 1. Pipeline `src/vulntrace/pipeline/` and `python -m vulntrace triage` (Mode 1 all changed non-test functions, Mode 2 retriever top-k, `auto` mode choice, optional lifting as `LIFTED` seeds, two methods per symbol + `verdict.py`, failure as `CANT_DETERMINE` with a reason code, safety flags)
- [ ] 2. Evidence verifier `src/vulntrace/verifier/` (funcs, call-site file/line, `edges`, entry/target structure, every `REACHABLE` has a verified path; downgrade-only; corrupted-path tests; no-upgrade proof by test)
- [ ] 3. `schemas/verdict.schema.json` extended without breaking old files; contract tests with recorded outputs per verdict and reason code
- [ ] 4. `python -m vulntrace eval triage`: D2 fixture metrics; D1/D4 distribution, coverage, `CANT_DETERMINE` reasons; Mode 2 `NOT_REACHABLE` policy; cost; results in `docs/results/cp7/` and `docs/results/CP7_TRIAGE_RESULTS.md` (headline fixed before results)
- [ ] 5. Tests (unit, contract, integration); CI green on the last commit
- [ ] 6. Report `docs/progress/reports/CP7_REPORT.md`; STATUS `AWAITING_REVIEW`

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP6 was approved on 26 Oct 2026 as a negative result; read the review notes at the end of checkpoints/CP3.md to CP6.md - they bind CP7. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists.)
