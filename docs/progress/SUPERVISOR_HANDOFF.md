# Supervisor handoff (for a new supervising chat)

Purpose: if the supervising chat's context fills up, a new chat (claude.ai, any model) can take over by reading the repository only. Nothing important lives only in a chat.

## Roles

- Owner: Lucy (student, AIML, PES University). Wants one portfolio project for AI/GenAI interviews, built in about 4 weeks, at zero cost (no paid APIs; Claude Pro only).
- Supervisor (the chat): designs, writes each checkpoint spec, reviews each checkpoint independently, merges approved work into `main`.
- Builder: Claude Code (cloud or local) builds one checkpoint per session from the spec, on its own `claude/...` branch.
- Lucy's preferences: short blocks, plain words, small tables, say the correct technical term, be strict and say plainly when something is wrong. Do not flatter.

## How to take over (read in this order)

1. `CLAUDE.md` (session rules), `docs/progress/STATUS.md` (ledger), this file.
2. `docs/implementation/IMPLEMENTATION_ROADMAP.md` (8 checkpoints, model and effort per checkpoint, drop order).
3. The current checkpoint spec in `docs/implementation/checkpoints/` including its review notes, and `docs/progress/reports/`.
4. Verify against GitHub directly: `git ls-remote origin <branch>` and a fetch with an explicit refspec (a plain `git fetch origin` may leave tracking refs stale and cause false "nothing pushed" or "unpushed commits" alarms).

## Review routine

Fetch the branch, read the report, re-run the unit and contract tests in a venv, check CI with `gh run list`, cross-check committed result files against the report's numbers, look for silent selection or leakage bugs. Go tests and integration tests cannot be run in the supervisor sandbox (no Go proxy); they rest on CI. Then fast-forward `main` onto the branch, add review notes to the checkpoint spec, write the next spec, set STATUS to READY, push, verify the remote SHA.

## State at 22 Oct 2026

- CP1, CP2, CP3: APPROVED and on `main`. CP3 review findings (see `checkpoints/CP3.md`): duplicated D4 ranges, undated cases, 500-commit truncation, 26% of cases have gold outside the candidate set.
- CP4 (retrieval stack): built on branch `claude/vulntrace-ai-build-9qhbjg`, state AWAITING_REVIEW, **not yet reviewed in full and not merged**. Its own report says acceptance criterion 6 (real dense/hybrid/rerank run) was not met.
- BM25 results on the real D4 evidence are real (produced in the Claude Code session): MRR random 0.281, B-ID 0.397, BM25 code-only 0.507, BM25 with commit subjects 0.571 (cluster intervals in the CP4 results doc). 17 of 120 advisory texts name the vulnerable function; ID-masking control proves nothing because no query contains an advisory ID.
- **The first Colab run (zip `cp4_results.zip`) is INVALID.** Checked by the supervisor: in the bundle, 0 chunks were built, every case has 0 candidates, every rank is None. Colab's own D4 materialisation produced 0 AVAILABLE cases (62 TAG_NOT_FOUND, 31 EMPTY, 18 TRUNCATED, 9 PSEUDO_VERSION_UNRESOLVED) versus 103 AVAILABLE expected, and 119 of 120 cases differ from the committed D4 list. Cause not yet proven; suspected: the git cache was placed on Google Drive (`VULNTRACE_CACHE` on the Drive mount), or git/network behaviour in Colab. Needs the printed output of the materialise cell to confirm.
- Required fix before any new Colab run: (1) keep the git/vulndb cache on local Colab disk, only embeddings and result JSON on Drive; (2) add a hard gate cell that stops the notebook if materialised statuses differ from `D4_cases.json` by more than a few cases; (3) make `eval retrieval` refuse to write results when a run has 0 chunks.
- Next: fix the notebook (small), valid Colab run, full CP4 review, merge, write CP5 (local LLM layer, HyDE, lifting, Colab runs).

## Cost rule

Never use a paid API, Fable or 1M-context models in Claude Code. Real model runs happen in Colab (free T4) because the Claude Code cloud network blocks Hugging Face.
