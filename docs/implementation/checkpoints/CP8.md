# CP8 - Final report, README and interview notes

- Recommended model: **Sonnet 5.5**, effort **high** (accurate writing; every number must be traceable)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 1-2 days. No model run, no Colab, no new experiment.
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, the **review notes at the end of `CP3.md` to `CP7b.md`** (they are the supervisor's verdicts and caveats; the final documents must not claim more than they allow), every results document in `docs/results/`, `docs/design/ARCHITECTURE.md` (or the design overview that exists), `docs/evaluation/EVALUATION_PLAN.md`

## Goal

Turn the repository into something a reader (an interviewer, a reviewer) can understand in five minutes and verify in an hour: what VulnTrace AI does, how it is built, what was measured, what worked, what did not, and why. Nothing new is built or measured.

## Binding rules

- **Every number comes from a committed result file.** Numbers in prose are produced by code or checked by a test against the result files. No number is typed from memory or from a report's prose.
- **Negative results are first-class:** E1 (LLM selection loses recall), HyDE (weak), the CP6 agent (does not beat retrieval, about 5x the tokens), D3 REACHABLE paths (0 of 7 runnable). Each is stated plainly with what it changed in the design.
- **Wording limits from the reviews:** reachability only, never exploitability; REACHABLE means "a call-graph path exists; needs a human look"; the D3 adjudication was two Claude reviewers reconciled by the supervising assistant with an owner spot-check, never "expert ground truth"; govulncheck was not worse than VulnTrace on the D3 cases; Mode 2 numbers in CP7 used BM25, not the intended retriever; lifting ran with go1.26.10 outside CI.
- No change to code behaviour, verdict rules, prompts or result files. Small fixes to broken links or stale docs are allowed and listed.

## Deliverables

1. **Results summary generator** - `python -m vulntrace results summary` writes `docs/results/SUMMARY.md` and `docs/results/summary.json`: one table per experiment (CP4 retrieval, CP5 E1/S1/HyDE, CP5b lifting, CP6 agent, CP7 fixtures and distributions, CP7b real apps), headline numbers with intervals and n, each row linking to the result file it came from. A test re-generates it and fails if the committed copy differs.

2. **README.md** (repository root), plain and short:
   - What it is (two sentences), the three verdicts, reachability not exploitability.
   - How it works: one diagram (Mermaid) of the pipeline: advisory -> symbols (Mode 1: all changed functions; Mode 2: retrieval top-k) -> two-method reachability -> verdict rule -> downgrade-only verifier; where RAG and LLMs were tried and measured.
   - Key results: a short table taken from `summary.json` (a test checks the numbers).
   - What did not work and what it taught (the negative results above).
   - Quickstart that runs offline on a fixture (the exact commands from `docs/DEMO.md`), zero-cost note, repository map, licence status.

3. **Final report** - `docs/FINAL_REPORT.md`: problem and scope; design decisions with the measurement that justified each (link to the checkpoint review notes); datasets (D1, D2 fixtures, D4, D3) and their limits; each experiment (question, setup, result, what it changed); threats to validity (small n, same-family reviewers, contamination split, toolchain differences, BM25 fallback); what I would do next (path-feasibility checking for REACHABLE, using clear-answer CANT_DETERMINE cases, more real applications, a human expert adjudicator). Numbers come from `summary.json`.

4. **Interview notes** - `docs/INTERVIEW_NOTES.md`: a 60-second project pitch; 10-15 likely questions with short honest answers grounded in the results (for example "Why not just use govulncheck?", "Why did you drop the agent?", "How do you know the numbers are real?", "What is the biggest weakness?"); each answer links to its evidence. Written so the owner can say it in her own words.

5. **Housekeeping:** `docs/progress/SUPERVISOR_HANDOFF.md` is updated by the supervisor, not by this session. This session lists stale or contradictory docs it finds (do not delete design history; add a short "superseded by" note where needed).

6. **Tests:** summary regeneration test; README and interview-notes number checks; relative-link check for the new documents; CI green.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | `results summary` regenerates `SUMMARY.md` and `summary.json` exactly from committed result files. | Test |
| 2 | README, final report and interview notes contain no number that is not in `summary.json` or a cited result file; a test checks the README and interview-notes numbers. | Tests |
| 3 | Every negative result is stated with its consequence for the design. | Documents |
| 4 | Wording limits above respected (reachability only; REACHABLE caveat; adjudication method; govulncheck comparison; BM25; toolchain). | Review |
| 5 | Quickstart commands run offline on a fixture in a clean checkout (run them and paste the output in the report). | Report |
| 6 | No behaviour, result-file, prompt or verdict-rule change. | `git diff --stat` |
| 7 | All tests pass locally and in CI (check CI on the **last** commit); report `docs/progress/reports/CP8_REPORT.md`; STATUS `AWAITING_REVIEW`. | Files |

## Out of scope

New experiments, multi-agent work, path-feasibility checking, retrieval or prompt changes, a hosted demo, slides.

## Review notes

(The supervising assistant adds notes here.)

**Supervisor review, 17 Nov 2026 - APPROVED** (branch `claude/vulntrace-ai-build-5f8jgi` at `3113659`).

Checked by the supervisor: `pytest tests/unit tests/contract` -> 887 passed, 10 skipped; CI green on every commit including the last; `results summary` is a new command only (no behaviour change in `src/`). Wording limits checked in README, FINAL_REPORT and INTERVIEW_NOTES: reachability not exploitability; REACHABLE = "a call-graph path exists; needs a human look"; the D3 adjudication is described as two Claude reviewers reconciled by the supervising assistant with an owner spot-check, not expert ground truth; govulncheck agreement (9/11) and the two cases where it was right; BM25 fallback for the measured Mode 2 run; go1.26.10 outside CI. The claim "most Go advisories do not name symbols" comes from the pre-design feasibility measurement and is labelled as such.

The project is complete at CP8. Any further work (for example path-feasibility checking for REACHABLE) would be a new checkpoint with its own specification.
