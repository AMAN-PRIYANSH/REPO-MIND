# CP3 - Advisory dataset, fix evidence, release ranges, baselines (+ CI)

- Recommended model: **Sonnet 5.5**, effort **high**
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `docs/implementation/checkpoints/CP2.md` (review notes), `docs/research/FEASIBILITY_FINDINGS.md` (trials 1, 2, 5), `docs/design/DATA_MODEL.md` (VulnCase, FixEvidence, ReleaseRange, RootCauseSelection), `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 1 and 2), `docs/evaluation/DATASET_STRATEGY.md` (D1, D4), `docs/evaluation/EVALUATION_PLAN.md` (E0, B-ID, metrics, uncertainty), `docs/testing/TESTING_STRATEGY.md`

## Goal

Build the labelled datasets for both modes from the Go vulnerability database, and the two baselines every later method must beat. Add continuous integration so every checkpoint is verified in a neutral environment.

No models, embeddings, retrieval, database or agent in CP3.

## Task 0 - carry-overs from the CP2 review (each its own commit)

0a. **Package-not-in-program contract change.** Implement the rule added to [interfaces](../../design/INTERFACES_AND_CONTRACTS.md) section 2: when the target's package is not part of the loaded program, `reach` returns `NO_PATH` with `details.package_not_in_program = true`; `TARGET_NOT_FOUND` stays an error for a loaded package that lacks the symbol. Update schemas (by adding, not breaking), tests and contract recordings. Re-run fixture scoring and regenerate `docs/results/CP2_CALLGRAPH_RESULTS.md`. Expected effect: `build_tag_excluded` becomes `NOT_REACHABLE`; report the observed effect, whatever it is.

0b. **Continuous integration.** Add `.github/workflows/ci.yml` (GitHub Actions; free for public repositories) that runs on every push and pull request: set up Go 1.24.x and Python 3.12; install the package with dev extras; run `pytest tests/unit tests/contract`, `go test ./...` in `helper/`, and `pytest tests/integration`. Use `set -o pipefail` or no pipes, so failures are never hidden. No secrets, no paid services. Report the URL of the first CI run and its result. If Actions cannot be enabled from the session, report that as a blocker.

0c. **Generic symbols in the linker method (attempt).** Observe how `vulnlib.ParseAny` instantiations appear in `go tool nm` output and, if a reliable rule exists, match `ParseAny[T]`-style targets to them. If no reliable rule is found, keep `UNSUPPORTED_SYMBOL_FORM` and document what was observed.

## Deliverables

1. **vulndb snapshot**
   - Fetch `golang/vulndb` (only `data/reports/`) at a commit SHA recorded in a config file, into a cache directory outside the repository (never committed).
   - Read the repository's licence file and record in the report what it allows. Until that is clear, do not commit report content; commit only advisory IDs, counts and computed results.

2. **Report reader and `VulnCase` builder** - suggested `src/vulntrace/dataset/`
   - Parse report YAML with `pyyaml` (allowed new dependency).
   - Handle: multiple modules, packages and version ranges; `/vN` module suffixes; `+incompatible`; pseudo-versions; missing `vulnerable_at` or `fixed`; `derived_symbols`; `source.created`; fix references that are commits, pull requests, or not GitHub.
   - Output `VulnCase` objects valid against a new `schemas/vuln_case.schema.json`.

3. **Mode 1 evidence: `FixEvidence`**
   - For each GitHub fix commit: bounded git fetch (commit plus parent, no full clone), changed non-test, non-vendor Go functions on both sides, using the helper's `funcs` mode, plus numbered hunks.
   - Unfetchable commits → `status: UNAVAILABLE`, counted, never silently dropped.
   - Schema `schemas/fix_evidence.schema.json`.

4. **Mode 2 evidence: `ReleaseRange`**
   - From `vulnerable_at` to the smallest `fixed` version above it (feasibility trial 5 logic). Tag naming must handle sub-module prefixes and `+incompatible`. **Pseudo-versions** must resolve through the commit hash embedded in them (5 of 50 failed in the trial without this).
   - Changed non-test, non-vendor Go functions between the two refs (candidates), and the commits in the range with their subjects and which candidates each touches. Fetch history with a bound (for example a commit cap); if the range exceeds it, mark it truncated.
   - Statuses: `AVAILABLE`, `TAG_NOT_FOUND`, `PSEUDO_VERSION_UNRESOLVED`, `EMPTY`, `TRUNCATED` (add to the data model if needed).
   - Schema `schemas/release_range.schema.json`.

5. **Datasets** (case lists committed; bulky evidence in the gitignored `data/` directory)
   - **D1** (Mode 1): 150 REVIEWED advisories with core symbols and a GitHub fix commit, stratified by `created` year, fixed random seed.
   - **D4** (Mode 2): 120 advisories from the same eligible pool, deliberately including every case with more than 100 candidates found while building (compute release ranges for more advisories if needed to reach at least 25 such cases, or report how many exist).
   - Commit `docs/results/datasets/D1_cases.json` and `D4_cases.json` (IDs, created date, candidate counts, statuses) and a generated summary document.
   - `python -m vulntrace dataset build --mode fix|release` reproduces both from the pinned vulndb commit.

6. **Baselines**
   - **E0** on D1: every changed function is predicted vulnerable.
   - **B-ID** on D4: search commit subjects and bodies in the release range for the advisory's CVE, GHSA and GO identifiers; predict the functions changed by matching commits; if nothing matches, predict nothing (counted as abstention).
   - Metrics from the [evaluation plan](../../evaluation/EVALUATION_PLAN.md): precision, recall, F1 per case (macro), exact match, any-hit, against core symbols and against core ∪ derived. For D4 also the candidate-set size distribution and the "gold not in candidates" ceiling.
   - Every rate with raw counts and a 95% bootstrap interval (fixed seed). Split by `created` date before / after 2026-06-30 (a placeholder until a model is chosen in CP5).
   - `python -m vulntrace eval symbols --strategy e0|id-search`.

7. **Ceiling investigation (open question Q8)**
   - For D4 cases where some core symbol is not among the candidates, classify why: symbol exists unchanged in the range; symbol not found at either version; matching problem; other. Report counts and 3 worked examples.

8. **Tests**
   - Unit: report parsing using small YAML written inside the tests (not copied from vulndb until the licence is confirmed); version and tag resolution including pseudo-versions; metric maths on hand-computed examples; bootstrap determinism.
   - Integration: release-range and fix-evidence extraction against small local git repositories created inside the tests (no network).
   - A network smoke test that fetches one real advisory's evidence may exist, but must be opt-in (skipped by default) and never run in CI.

9. **Results document** - `docs/results/CP3_DATASETS_AND_BASELINES.md`, generated by code: dataset sizes and statuses, candidate-size distribution, E0 and B-ID tables with intervals, ceiling investigation, and a comparison with feasibility trials 2 and 5 explaining any differences.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Task 0a done; `build_tag_excluded` outcome reported; CP2 results regenerated. | Results doc, tests |
| 2 | CI workflow exists and its first run's URL and result are reported. Unit, contract, Go and integration jobs all run. | CI link |
| 3 | Task 0c attempted; outcome documented either way. | Report |
| 4 | vulndb commit pinned; licence finding recorded. | Config file, report |
| 5 | D1 and D4 built with counts per status; nothing dropped silently. | Results doc |
| 6 | Pseudo-version resolution works (tested), and its effect on D4 coverage is reported. | Tests, results doc |
| 7 | E0 and B-ID reported with counts, intervals and the date split. | Results doc |
| 8 | Ceiling investigation reported with examples. | Results doc |
| 9 | All tests pass locally and in CI; no test needs network by default. | Printed summaries, CI |
| 10 | No vulndb content, caches or bulky evidence committed. | `git ls-files` |
| 11 | Report `docs/progress/reports/CP3_REPORT.md` in the wrapper format; STATUS `AWAITING_REVIEW`. | Files |

## Out of scope

Models of any kind, embeddings, the vector store, retrieval, the agent, lifting, the verifier, real target applications.

## Known risks

- GitHub fetches are slow; cache fetched objects and allow resuming. Do not hammer GitHub (sequential fetches, small delay).
- Some fix references point to pull requests or non-GitHub hosts; count them rather than guessing commits.
- Large release ranges may exceed the commit cap; mark them `TRUNCATED` rather than silently cutting.

## Review notes

(The supervising assistant adds notes here if the state becomes `CHANGES_REQUESTED`.)
