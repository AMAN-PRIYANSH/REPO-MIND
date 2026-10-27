# CP7 - End-to-end triage and evidence verifier

- Recommended model: **Opus 5.5**, effort **high** (verdict logic and verifier must be exact)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days. No Colab run is needed (no model is called by default).
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `CP2.md` (verdict rule, helper), `CP3.md` to `CP6.md` (**review notes at the end of each bind this checkpoint**), `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 1-3 and 6), `docs/design/DATA_MODEL.md`, `docs/evaluation/EVALUATION_PLAN.md`, `docs/decisions/RISKS_AND_OPEN_QUESTIONS.md`

## Goal

Make `python -m vulntrace triage --advisory <ID> --app <dir> [--mode auto|fix|release]` work end to end and print one verdict JSON with evidence, then measure how trustworthy it is. The verdict is **reachability only** (never exploitability): `REACHABLE`, `NOT_REACHABLE` or `CANT_DETERMINE`.

Real applications (D3) and the demo are **CP7b**, not this checkpoint.

## Findings that bind this design

- **No agent in the pipeline.** CP6: the agent did not beat retrieval top-1 and costs about 5x the tokens. Mode 2 uses the retriever (`hybrid:bge-small`, `code+commits`) top-k.
- **No LLM narrowing in Mode 1.** CP5 E1: an LLM that picks one changed function lost recall (0.84 -> 0.57). Mode 1 analyses **all** changed non-test functions of the fix commit (E0 behaviour). An LLM-ranked list is optional and, if included, only reorders, never removes (default off; if offered, it needs a measured reason).
- **Lifting is a widening aid only.** CP5b: lifting reaches 0.87 coverage but recall against curators' symbols is 0.25 (NEAREST) to 0.47 (ALL). Lifted symbols may be added as extra seeds with `origin: LIFTED`; they never replace a core symbol and never decide a `NOT_REACHABLE`.
- **Mode 2 candidate lists miss the root cause in about 16-19% of cases** (D4: gold not among the candidates). So in Mode 2, `NOT_REACHABLE` must never read as "the vulnerability is unreachable". It reads "none of the top-k candidate functions is reachable", and by default is downgraded to `CANT_DETERMINE` unless the report shows a measured false-NOT_REACHABLE rate that justifies keeping it (decide from the evaluation below, state the rule in the report).
- Reachability of a changed function that is not the root cause says nothing about the vulnerability. Mode 2 `REACHABLE` therefore carries the candidate's rank and score and is labelled `CANDIDATE_LEVEL`.

## Deliverables

1. **Pipeline** - `src/vulntrace/pipeline/`
   - Stages: advisory -> symbols (by mode) -> optional lifting -> reachability with two independent methods per symbol (linker presence + VTA; use the existing methods and the existing `verdict.py` rule: agreement, otherwise `CANT_DETERMINE`) -> case verdict -> verifier -> output.
   - Mode selection `auto`: a known fix commit means Mode 1, otherwise Mode 2 on the release range; the chosen mode and why are in the output.
   - Every verdict records: mode, symbols with `origin` and rank, the method results per symbol, the call path(s) with file and line, toolchain and versions, what was **not** covered (for example candidates not in the loaded program, load failures), and a plain `limitations` list.
   - Failure is a result: unloadable app, no candidate, no fix evidence -> `CANT_DETERMINE` with a reason code. Never an exception for a data problem.
   - Safety (CLAUDE.md section 8): `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; never run the app, its tests, `go generate` or its binaries. Advisory and commit text are untrusted data.

2. **Evidence verifier** - `src/vulntrace/verifier/` (contract: `INTERFACES_AND_CONTRACTS.md` section 6)
   - Checks per verdict: each target symbol exists at the analysed version (`funcs`); each call-site file and line exists at the recorded commit; each call edge exists (`edges` mode); the path starts at a `main` entry and ends at the target; every `REACHABLE` has at least one verified path.
   - **Downgrade-only:** a failed check turns the affected symbol into `CANT_DETERMINE` with `VERIFIER_REJECTED` and a reason; the verifier can never upgrade, never add symbols, never change a path.
   - Tests must include a deliberately corrupted path (wrong line, missing edge) that is rejected, and a proof by test that no input makes the verdict stronger.

3. **Verdict output schema** - `schemas/verdict.schema.json` extended without breaking old files; contract tests with recorded outputs for each verdict and each reason code.

4. **Evaluation** (E5-lite, no D3 yet): `python -m vulntrace eval triage`
   - Fixtures (D2, truth by construction): verdict accuracy, `REACHABLE` precision, false `NOT_REACHABLE` count (must be reported even when 0), verifier rejections (must be 0 on correct outputs).
   - D1 and D4 evidence: run the pipeline on the cases that have evidence and a loadable module, with the module under study as the app, to measure **verdict distribution, coverage and `CANT_DETERMINE` reasons**. These are not truth-labelled reachability cases, so report distributions and stability, not accuracy; say so plainly.
   - Mode 2 policy decision: with the D2/D4 numbers, state whether Mode 2 `NOT_REACHABLE` is kept or downgraded and why (see findings above).
   - Cost: seconds per case, how many cases need which fallback.
   - Results to `docs/results/cp7/` (JSON, each file under 512 KiB), rendered by code to `docs/results/CP7_TRIAGE_RESULTS.md`. A headline sentence is fixed in the renderer **before** the results are seen and not edited after.

5. **Tests** - unit, contract and integration (fixtures end to end, skip with a clear message if Go is missing); CI green; nothing needs the network by default; no model is called.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | `triage` works for Mode 1 and Mode 2 on fixtures and on at least one D1 and one D4 case with real evidence. | Run output, tests |
| 2 | Mode 1 analyses all changed non-test functions; no LLM selection or agent is used in the verdict path. | Code, tests |
| 3 | Two-method agreement rule applied; every `REACHABLE` has a verified path; Mode 2 results carry rank and `CANDIDATE_LEVEL`. | Tests |
| 4 | Verifier downgrade-only, proven by tests including corrupted paths. | Test summary |
| 5 | Fixture evaluation reported: accuracy, `REACHABLE` precision, false `NOT_REACHABLE` count, verifier rejections. | Results doc |
| 6 | D1/D4 distribution and coverage reported with `CANT_DETERMINE` reasons; stated as not accuracy. | Results doc |
| 7 | Mode 2 `NOT_REACHABLE` policy decided from numbers and stated in report and docs. | Report |
| 8 | No analysed code was executed; toolchain flags used; no `data/`, caches or third-party source committed. | Report, `git ls-files` |
| 9 | All tests pass locally and in CI (printed summaries; check CI on the **last** commit); report `docs/progress/reports/CP7_REPORT.md`; STATUS `AWAITING_REVIEW`. | Files |

## Out of scope

D3 and real applications, the demo page, any new model run, retrieval or prompt changes, changes to the agent, multi-agent work.

## Known risks

- Many real modules will not load (dependencies, Go version): the system must say `CANT_DETERMINE` with a reason, and the report must count these.
- Reachable by call graph is not exploitable; the output wording and docs must say reachability only.
- VTA can over-approximate dynamic dispatch; keep the `STATIC` / `DYNAMIC` edge kind in the evidence.

## Review notes

(The supervising assistant adds notes here.)

**Supervisor review, 27 Oct 2026 - APPROVED** (branch `claude/vulntrace-ai-build-exhh01` at `a3c3ac1`).

Checked by the supervisor: `pytest tests/unit tests/contract` -> 763 passed, 10 skipped; CI green on the last three commits (the earlier red run 121 is disclosed in the report: result files committed before re-rendering the document); every result file is under 512 KiB; no `data/`, traces or archives tracked. The results document's headline sentence was fixed in the renderer before any result existed, and was not edited afterwards.

What the results say (numbers in `docs/results/CP7_TRIAGE_RESULTS.md`):

1. **Fixtures (truth known):** zero false NOT_REACHABLE and zero false REACHABLE for "given targets" and Mode 1; accuracy 18/22 with 4 `CANT_DETERMINE`. Mode 2 shows 4 false REACHABLE by construction (an unrelated function changed in the same release range is reachable): this is why Mode 2 answers are labelled candidate level. The verifier rejected 0 correct outputs and 36 of 36 corrupted paths.
2. **The pipeline is conservative on real modules:** D1 102 of 143 runs and D4 88 of 120 end in `CANT_DETERMINE`. Main causes: modules that need Go 1.25 or newer (58 D1, 52 D4) while CI and the review environment have Go 1.24.7, and libraries with no `main` package (26, 22). Stability: re-running 10 cases per set gave identical verdicts. These are distributions, not accuracy.
3. **Mode 2 `NOT_REACHABLE` is downgraded to `CANT_DETERMINE`** by a rule fixed in code before the results (the rule needs at least 20 raw verdicts; D4 gave 5). Accepted.
4. **Real defects found by running on real modules, all fixed and re-run:** two linker-method defects (generic functions named without type parameters; functions in the analysed `main` package named `main.X`), which could have produced a false NOT_REACHABLE the second method did not catch; and two verifier false rejections (promoted methods, build-constrained files). This is a good interview point: the real runs found bugs the fixtures did not.
5. **Mode 2 ranked candidates with BM25** (CP4's documented fallback) because Hugging Face is blocked in the builder's environment; each verdict records this. Mode 2 results here are therefore not the intended `hybrid:bge-small` retriever; state it wherever Mode 2 numbers are used.
6. The stale CP6 notebook test (red on `main` since the CP6 approval commit, a side effect of the supervisor's STATUS edit) was repointed in its own commit without weakening it. Accepted.

Carried into CP7b: choose applications that are `main` packages and that load with the available toolchain; use the same documented toolchain approach as CP5b (a newer Go fetched into a scratch directory, `GOTOOLCHAIN=local`, recorded in every result).
