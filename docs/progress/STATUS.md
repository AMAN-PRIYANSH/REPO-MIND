# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP9 - Path-feasibility filter for REACHABLE (downgrade-only)**
- State: `AWAITING_ADJUDICATION` (D3b sheets in `docs/results/cp9/d3b/adjudication/`; report `reports/CP9_REPORT.md`, scoring sections pending)
- Branch in use: `claude/intelligent-planck-krrtgg`
- Specification: [checkpoints/CP9.md](../implementation/checkpoints/CP9.md)

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
| CP9 | Path-feasibility filter for REACHABLE (downgrade-only) | AWAITING_ADJUDICATION | claude/intelligent-planck-krrtgg | [CP9_REPORT](reports/CP9_REPORT.md) (scoring pending) |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

CP9 (session branch `claude/intelligent-planck-krrtgg`):

- [x] 1. Feasibility check in the Go helper (F1-F3 on SSA, one level of call-site context, N examined paths, conservative when undecidable)
- [x] 2. Pipeline and verifier integration (`PATHS_INFEASIBLE`, schema extension, verifier checks of infeasible steps and of the filtered path, downgrade-only tests, `--no-feasibility`)
- [x] 3. Fixtures by construction: >= 2 infeasible and >= 2 feasible look-alikes per pattern; CP2/CP7 fixtures keep their verdicts
- [x] 4a. Evaluation: fixtures (downgrades, false downgrades)
- [x] 4b. Evaluation: D3 before/after (in-sample, labelled so)
- [x] 4c. Evaluation: D3b selection (code, D3 rules, D3 apps excluded, seed fixed before runs), triage with/without filter, adjudication sheets -> `AWAITING_ADJUDICATION`
- [x] 4d. Evaluation: D1/D4 downgrade counts by pattern
- [x] 4e. Results renderer with headline fixed before any D3b result -> `docs/results/CP9_FEASIBILITY_RESULTS.md`, files under `docs/results/cp9/` (< 512 KiB each)
- [x] 5. Tests (CI still to be checked on the last commit): unit per pattern (SSA snippets), contract tests for new fields, integration on fixtures; CI green
- [ ] 6. After adjudication (second session): scoring, results document, report `CP9_REPORT.md`, STATUS `AWAITING_REVIEW`

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

CP9 session `claude/intelligent-planck-krrtgg` (17-18 Nov 2026), stopped at `AWAITING_ADJUDICATION`:

- Done: tasks 1-5 and 4a-4e. Results: `docs/results/cp9/` and `docs/results/CP9_FEASIBILITY_RESULTS.md` (headline
  pending). Report `docs/progress/reports/CP9_REPORT.md` (sections 5 criterion 5 and 6 headline pending).
- For the supervisor: fill `docs/results/cp9/d3b/adjudication/adjudication.json` (7 cases; read the three Markdown
  sheets beside it). Per case: `adjudication_off` (path A), `adjudication_on` (path B; none is pre-filled as
  SAME_AS_OFF because path B differs in all 7), `truth` (target reachable by some path), `by`, `note`, `filled: true`.
  No case was downgraded, so `steps_correct` stays null. Then set STATUS to IN_PROGRESS on this branch.
- Scoring session: `python -m vulntrace cp9 report` (renders the fixed headline from the filled sheet), check
  `python -m pytest tests/contract/test_cp9_committed.py`, complete the report (criterion 5, headline, section 6),
  set `AWAITING_REVIEW`. No Go or network is needed for scoring.
- D3b caveats to keep in the scoring: 4 of 11 D3b cases share advisories with D3; 3 applications only.
- Never commit `docs/results/datasets/D1|D4_materialize.json` changes made by `dataset materialize --cases` (revert).

(Earlier: CP8 was approved on 17 Nov 2026 and CP9 was added at the owner's request. The D3 evidence and checkouts are not in the repository: rebuild them with the CP7b commands. If CP9 stops at AWAITING_ADJUDICATION, the supervisor sets IN_PROGRESS on the builder branch once the D3b sheets are filled.)
