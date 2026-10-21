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
- [ ] Task 0b: GitHub Actions CI workflow
- [ ] Task 0c: generic symbols in linker method (attempt)
- [ ] D1. vulndb snapshot pinned (config file); licence recorded
- [ ] D2. Report reader and VulnCase builder + schema
- [ ] D3. Mode 1 FixEvidence extraction + schema
- [ ] D4. Mode 2 ReleaseRange extraction + schema
- [ ] D5. D1 and D4 datasets built and committed (case lists)
- [ ] D6. Baselines E0 (D1) and B-ID (D4) with metrics
- [ ] D7. Ceiling investigation (Q8)
- [ ] D8. Tests (unit, integration, opt-in network smoke)
- [ ] D9. Results document docs/results/CP3_DATASETS_AND_BASELINES.md
- [ ] CP3 report written; STATUS set to AWAITING_REVIEW

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

(CP3: started 21 Oct 2026 on branch `claude/lucid-fermi-9esjyw`. No continuation candidate found on other remote branches (both `claude/optimistic-shannon-397w1q` and `claude/vulntrace-checkpoint-continue-ia7tx5` are on already-approved CP2/CP1 work). Environment: Linux 6.18.44-fc-v140, Python 3.13.16, Go 1.24.7, git 2.43.0, Docker 29.9.1 all present; `proxy.golang.org` reachable; `github.com`/`api.github.com` direct access blocked by the session sandbox, but `golang/vulndb` was attached via `add_repo` (read-only, public) and cloned (sparse checkout of `data/reports/`, depth 1) to `~/.cache/vulntrace/vulndb-src`, pinned at commit `e0bad56276e98711a598adbab976de7cd914013a` (4710 report files, matching feasibility trial 1's count). vulndb's `LICENSE` file states code is BSD-style and the `/data/` directory (which includes `data/reports/`) is CC-BY-4.0 - permits reproduction/adaptation with attribution; this still only affects what *could* be committed, deliverable 5 only asks for IDs/counts/statuses either way. Baseline before any CP3 code changes: `pytest tests/unit tests/contract` -> 138 passed. Next step: implement task 0a (package_not_in_program contract change).)
