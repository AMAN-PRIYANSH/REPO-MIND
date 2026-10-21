# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP3 - Advisory dataset, fix evidence, release ranges, baselines (+ CI)**
- State: `IN_PROGRESS`
- Branch in use: `claude/lucid-fermi-9esjyw`
- Specification: [checkpoints/CP3.md](../implementation/checkpoints/CP3.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | IN_PROGRESS | claude/lucid-fermi-9esjyw | - |
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
- [~] D5. D1 and D4 datasets built and committed (case lists) - D1 done (150 cases, committed); D4 build running
- [x] D6. Baselines E0 (D1) and B-ID (D4) with metrics - code done; E0 scored on real D1; B-ID pending D4 data
- [x] D7. Ceiling investigation (Q8) - code done; pending D4 data to run for real
- [x] D8. Tests (unit, integration, opt-in network smoke)
- [ ] D9. Results document docs/results/CP3_DATASETS_AND_BASELINES.md
- [ ] CP3 report written; STATUS set to AWAITING_REVIEW

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP3: started 21 Oct 2026 on branch `claude/lucid-fermi-9esjyw`. Tasks 0a-0c and deliverables 1-4, 6, 7, 8 done and pushed (see commit log). D1 dataset built for real: 150 cases committed at `docs/results/datasets/D1_cases.json` (144 AVAILABLE, 4 EMPTY, 2 UNAVAILABLE, from 506 eligible - matches feasibility trial 1's 507 almost exactly). E0 baseline scored on the real D1 result: precision 0.584, recall 0.845, f1 0.631 (core symbols) - same ballpark as trial 2 (0.70 / 0.91).

D4 (release-range) build is the one piece not finished: it is network- and compute-heavy (resolving two version refs, deepening and walking commit history per case, across up to 500 candidate cases to find >=25 with more than 100 candidates). It has been attempted three times now; the first two were killed deliberately rather than trusted, each after finding and fixing a real bug live:

1. First attempt - killed at ~70/500 after finding `d12c28a`: TRUNCATED cases weren't counted toward "large" despite carrying real, large candidate lists (candidates come from a single two-tree diff, not the possibly-incomplete commit walk).
2. Second attempt - crashed outright at ~126/500 on an unhandled `subprocess.TimeoutExpired` from a slow `git fetch --depth=501` on a large active repo (`c96d904` fixed `git_fetch.run_git` to catch timeouts everywhere instead of letting them propagate). Relaunched, then killed again at 47/500 after a code-review (not a test failure) found a second, more serious bug (`48aec8a`): the exploration order came from `stratified_sample(eligible, target=len(eligible), ...)`, whose own "pool fits within target" short-circuit returns the pool sorted by id, unshuffled - so forced (post-cutoff) cases were not actually guaranteed to be explored first as the design requires. Fixed by building the explored order explicitly as `sorted(forced) + shuffled(remainder)`.
3. Third attempt - relaunched under both fixes via `python -u -m vulntrace dataset build --mode release > /tmp/d4_build3.log 2>&1`, running in background. This is the one to let finish; do not kill it unless a new bug is found. Underlying git repo caches from the earlier attempts are still on disk and are reused (no wasted network work).

Next steps once this D4 build finishes: (1) verify its output and write `docs/results/datasets/D4_cases.json` (via `dataset build --mode release`'s own CLI flow, which calls `build.build_d4` / `write_case_list` - no separate reprocessing step needed, the fixes are already in the code that produced the run); (2) `python -m vulntrace eval symbols --strategy id-search`; (3) run the ceiling investigation (`ceiling.run_investigation`) over the D4 cases; (4) `python -m vulntrace results render --doc cp3 --input results/cp3 --out docs/results/CP3_DATASETS_AND_BASELINES.md`; (5) run the full test suite one final time; (6) write `docs/progress/reports/CP3_REPORT.md` (format in `prompts/SESSION_WRAPPER.md`), set this file's state to `AWAITING_REVIEW`, commit and push. Everything else is done; do not start CP4.)
