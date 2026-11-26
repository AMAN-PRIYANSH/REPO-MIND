# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP10 - Verdict-level trust against govulncheck, target hygiene and honest evidence**
- State: `IN_PROGRESS` (builder session 1 started 26 Nov 2026)
- Branch in use: `claude/wizardly-hamilton-0ft7q0`
- Specification: [checkpoints/CP10.md](../implementation/checkpoints/CP10.md)

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
| CP8 | Final report, README and interview notes (multi-agent dropped) | APPROVED | claude/vulntrace-ai-build-5f8jgi | [CP8_REPORT](reports/CP8_REPORT.md) |
| CP9 | Path-feasibility filter for REACHABLE (downgrade-only) | APPROVED | claude/intelligent-planck-krrtgg, claude/elegant-mccarthy-wq32ck | [CP9_REPORT](reports/CP9_REPORT.md) |
| CP10 | Verdict-level trust against govulncheck | IN_PROGRESS | claude/wizardly-hamilton-0ft7q0 | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

CP10 (from `docs/implementation/checkpoints/CP10.md`; ticked when committed):

- [x] 0. STATUS IN_PROGRESS, branch recorded; environment checked
- [x] 1a. Target hygiene in code: curated vulndb symbols decide (`origin: VULNDB`), changed functions kept as extra evidence; no curated symbols: changed functions minus `context_only`; only context targets reachable -> `CANT_DETERMINE` / `ONLY_CONTEXT_TARGETS_REACHABLE`
- [x] 1b. `--legacy-targets` reproduces CP7/CP9 verdicts exactly (test); hygiene never creates NOT_REACHABLE in stratum N (test)
- [x] 2a. Evidence ranking among the examined paths (filter pass, fewer DYNAMIC, shorter; N recorded)
- [x] 2b. DYNAMIC steps carry `confirmed: false` and their kind; verdict records the path evidence level (`STATIC_PATH` / `HAS_DYNAMIC_STEPS` with count)
- [x] 2c. Text output and demo page say "route shown is an example from the call graph; steps marked unconfirmed may not run in this context"
- [x] 3a. D3c rules, candidate list and seed committed before any D3c probe; selection code with strata S/N and quotas, D3/D3b apps excluded
- [x] 3b. Scoring renderer with the headline fixed before any D3c result
- [x] 3c. D3c selection run (case list committed)
- [ ] 3d. D3c triage: VulnTrace new rules and `--legacy-targets`, govulncheck (source, symbol scan, pinned vulndb)
- [ ] 4. Verdict-level adjudication sheets: every D3c case; truth-only items for the 7 D3 REACHABLE and the D3b non-REACHABLE cases; STATUS `AWAITING_ADJUDICATION`
- [ ] 5. (second session, after adjudication) scoring: `docs/results/CP10_VERDICT_RESULTS.md` rendered by code
- [ ] 6. Tests for hygiene, legacy reproduction, ranking and labels, sheets and scoring; CI green on the last commit
- [ ] 7. Report `docs/progress/reports/CP10_REPORT.md`; STATUS `AWAITING_REVIEW` (after scoring)

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP9 was approved on 20 Nov 2026 as a negative result; read the review notes at the end of CP7.md, CP7b.md and CP9.md - they bind CP10. D3/D3b evidence and checkouts are not in the repository: rebuild them with the CP7b/CP9 commands. When CP10 stops at AWAITING_ADJUDICATION, the supervisor fills the sheets and sets IN_PROGRESS on the builder branch.)
