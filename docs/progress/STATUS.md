# Progress status

This file is the single source of truth for where the build stands. Claude Code updates it after every task. The supervising assistant updates it when a checkpoint is approved or released.

## Current

- Current checkpoint: **CP4 - Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker**
- State: `CHANGES_REQUESTED` (see the review notes at the end of checkpoints/CP4.md: the first Colab run was invalid; fix list FIX-1..FIX-6)
- Branch in use: `claude/vulntrace-ai-build-9qhbjg`
- Specification: [checkpoints/CP4.md](../implementation/checkpoints/CP4.md)

State values: `READY` → `IN_PROGRESS` → `AWAITING_REVIEW` → `APPROVED` (or `CHANGES_REQUESTED`).

## Checkpoint ledger

| CP | Title | State | Branch | Report |
|---|---|---|---|---|
| CP1 | Ground truth and linker presence | APPROVED (1 fix carried to CP2 task 0) | claude/vulntrace-checkpoint-continue-ia7tx5 | [CP1_REPORT](reports/CP1_REPORT.md) |
| CP2 | Go call-graph helper and verdict rule | APPROVED | claude/optimistic-shannon-397w1q | [CP2_REPORT](reports/CP2_REPORT.md) |
| CP3 | Advisory dataset, fix evidence, release ranges, baselines (+ CI) | APPROVED | claude/lucid-fermi-9esjyw | [CP3_REPORT](reports/CP3_REPORT.md) |
| CP4 | Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker | CHANGES_REQUESTED | claude/vulntrace-ai-build-9qhbjg | [CP4_REPORT](reports/CP4_REPORT.md) |
| CP5 | Local LLM layer, root-cause selection, HyDE, lifting, Colab runs | NOT_RELEASED | - | - |
| CP6 | LangGraph investigation agent | NOT_RELEASED | - | - |
| CP7 | End-to-end triage, verifier, real apps, demo | NOT_RELEASED | - | - |
| CP8 | Multi-agent experiment (stretch) and final report | NOT_RELEASED | - | - |

## Current checkpoint task list

Claude Code: copy the deliverables of the current checkpoint here as a checklist when you start, and tick them as you commit.

- [x] Task 0a: `dataset materialize --set d4` (120 cases, 1366.9 s, 1 difference listed) and `--set d1` (150 cases, 1 difference listed)
- [x] Task 0b: `cluster_key` on D4 cases (94 clusters); cluster bootstrap; CP3 doc regenerated (`dcdac10`)
- [x] Task 0c: `undated` bucket in every date split; CP3 doc regenerated (`dcdac10`)
- [x] D1: chunking, three variants, caps, masking, query-leakage tests (`39ff46d`)
- [x] D2: VectorStore + in-memory + pgvector, docker-compose, shared suite, CI pgvector job green; Q10 answered (`1d8d2cf`, `b357700`)
- [x] D3: BM25 + code-aware tokeniser (`78c9c24`)
- [~] D4: dense retrieval code, fake, sentence-transformers wrapper, embedding cache done (`b74cca2`); **real model run not done** (Hugging Face blocked here; needs Colab)
- [~] D5: RRF + Reranker interface, fake, cross-encoder wrapper done (`78c9c24`, `b74cca2`); **real reranker run not done**
- [x] D6: harness, CLI, metrics, both denominators, buckets, cluster CIs, rclone-removed, B-ID + random (`1f6dd9d`); real runs only for no-model configs (`7cea026`)
- [~] D7: notebook done (`1f1c607`) and its grid dry-run on real D4 with fakes (91 s); **not executed in Colab**
- [x] D8: tests (329 unit+contract incl. both backends; 66 integration + 2 opt-in skips; CI green)
- [x] D9: `docs/results/CP4_RETRIEVAL_RESULTS.md` generated (baselines + BM25 only)
- [x] Report `docs/progress/reports/CP4_REPORT.md`; STATUS `AWAITING_REVIEW`

## Handoff notes

Claude Code: if you stop before the checkpoint is complete, write here exactly what is done, what is half-done, and the very next step.

CP4 is AWAITING_REVIEW on `claude/vulntrace-ai-build-9qhbjg`. What is missing for criterion 6 is a run the owner does:

1. Open `notebooks/cp4_retrieval_colab.ipynb` in Colab (T4 GPU), keep `BRANCH = "claude/vulntrace-ai-build-9qhbjg"` (or `main` after merge), run all cells. Materialisation took ~23 min here; GPU times are unknown.
2. Hand the downloaded `cp4_results.zip` to the next session. It holds `cp4/cases.json`, `cp4/runs/*.json`, `cp4/D4_materialize_colab.json`, `cp4/model_problems.json` (JSON only).
3. Next session: compare the zip's `cases.json` with `docs/results/cp4/cases.json` and report every difference. If the bundle contains every config, replace `docs/results/cp4/` with it, then run `python -m vulntrace results render --doc cp4 --input docs/results/cp4 --out docs/results/CP4_RETRIEVAL_RESULTS.md`, and update CP4_REPORT sections 5 and 6 (criterion 6).

The notebook's Colab mechanics are untested (only its config grid was dry-run), so small fixes may be needed on first use.
