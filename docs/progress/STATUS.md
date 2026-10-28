# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP7b - Real applications (D3) and demo**
- State: `IN_PROGRESS`
- Branch in use: `claude/sleepy-tesla-smt1xr`
- Specification: [checkpoints/CP7b.md](../implementation/checkpoints/CP7b.md)

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
| CP7b | Real applications (D3) and demo | IN_PROGRESS | claude/sleepy-tesla-smt1xr | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

CP7b (session branch `claude/sleepy-tesla-smt1xr`):

- [ ] 0. Environment check (OS, Python, Go, git, Docker, network: Go proxy, GitHub, vulndb)
- [ ] 1. Application selection - `python -m vulntrace d3 select`: written rules applied by code before any triage result; every candidate printed with the rule that kept/dropped it; diversity note; committed case list (repo URL, commit, advisory, module version)
- [ ] 2. Triage run - `python -m vulntrace eval triage --set d3`: verdicts, paths with file:line, verifier outcome, CANT_DETERMINE reasons, seconds per case, toolchain; results to `docs/results/cp7b/` (< 512 KiB each)
- [ ] 3. Reference comparison (optional, labelled not truth): govulncheck source mode where it runs; per-case agreement; disagreements listed
- [ ] 4. Adjudication sheet - `docs/results/cp7b/adjudication/` (Markdown per application + one JSON with blank fields); all REACHABLE; stated sample (>=5 or all) of NOT_REACHABLE and CANT_DETERMINE; stop at `AWAITING_ADJUDICATION`
- [ ] 5. Scoring and results document (second session, after adjudication): scoring code and renderer with headline fixed before results built now; `docs/results/CP7B_REAL_APPS_RESULTS.md` rendered only after the sheet is filled
- [ ] 6. Demo - `python -m vulntrace demo build`: self-contained offline HTML from verdict JSON; `docs/DEMO.md`
- [ ] 7. Tests: selection rules, sheet generation (no invented verdict text), scoring from a filled sheet, page generator escaping; CI green on the last commit
- [ ] Report `docs/progress/reports/CP7b_REPORT.md`

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP7 was approved on 27 Oct 2026; read the review notes at the end of checkpoints/CP3.md to CP7.md - they bind CP7b. The evidence in `data/` is NOT available in a new session: `dataset materialize --set d1` and `--set d4` rebuild it from the committed case lists. If the CP7b session stops at AWAITING_ADJUDICATION, the supervisor sets the state to IN_PROGRESS on the builder branch once the sheets are filled, so a new session continues.)
