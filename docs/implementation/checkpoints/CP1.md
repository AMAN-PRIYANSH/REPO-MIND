# CP1 - Ground truth and linker presence

- Recommended model: **Sonnet 5.5**, effort **medium**
- Branch: `cp1-ground-truth-linker`
- Target duration: 2-3 days
- Required reading: `CLAUDE.md`, `docs/PROJECT_DEFINITION.md`, `docs/research/FEASIBILITY_FINDINGS.md` (trial 3), `docs/architecture/SYSTEM_ARCHITECTURE.md`, `docs/design/DATA_MODEL.md` (MethodResult, FixtureManifest), `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 1 and 3), `docs/design/PROJECT_STRUCTURE.md`, `docs/testing/TESTING_STRATEGY.md`

## Goal

Create the synthetic reachability suite (truth known by construction) and the first reachability method, linker presence, with tests and an honest results report.

CP1 contains no LLM, no embeddings, no call-graph helper, no advisory data, no database and no network access. It is small on purpose: every later method is scored against this suite, so the ground truth must be right first.

## Deliverables

1. **Python package skeleton**
   - `pyproject.toml` (Python 3.11+), `src/vulntrace/`, `tests/`.
   - Allowed dev dependencies: `pytest`, `jsonschema`. Nothing else without a written reason.
   - `.gitignore` covering `results/`, caches, virtual environments, `.env`, model files and built binaries.

2. **`doctor` command** - `python -m vulntrace doctor`
   - Prints Python version, `go version` (or "not found"), `go env GOOS GOARCH`, whether `go tool nm` runs, and whether `docker` is present (informational only in CP1).
   - Exit code `0` if all CP1 prerequisites (Python, Go) are present, `3` otherwise.
   - Never installs or downloads anything.

3. **Schemas** in `schemas/`
   - `fixture_manifest.schema.json` and `method_result.schema.json`, matching [data model](../../design/DATA_MODEL.md). Both carry `schema_version`.

4. **Fixture suite** in `fixtures/reachability/`
   - One Go module (suggested module path `vtfixtures`) with no external dependencies.
   - A fake vulnerable package `vulnlib`: a vulnerable function, a safe function, and a type with a method that calls the vulnerable function.
   - At least 12 cases, one `package main` each. The five cases from feasibility trial 3 are mandatory: direct call; safe function only; function value in a map; reflection `MethodByName`; dead code. Choose the rest from the category list in [dataset strategy](../../evaluation/DATASET_STRATEGY.md).
   - One case where the vulnerable function is small enough to be inlined. Run it with and without `-gcflags=all=-l` and record both observed results in the results document. Only the inlining-disabled run counts for scoring.
   - `fixtures/reachability/manifest.json`, valid against the schema, with `truth` and `rationale` for every case.

5. **Linker-presence method** - suggested `src/vulntrace/methods/linker.py`
   - `go build -gcflags=all=-l -o <temporary path> <main package>` with `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY=off`, `GOFLAGS` unset.
   - `go tool nm` on the binary; match target symbols with the rules in [interfaces](../../design/INTERFACES_AND_CONTRACTS.md) section 3.
   - One `MethodResult` per target symbol: `PRESENT`, `ABSENT` or `ERROR`, with matched binary symbol names, build flags, Go version, GOOS, GOARCH.
   - Generic symbols return `ERROR` with code `UNSUPPORTED_SYMBOL_FORM` unless a rule is verified and documented.
   - Temporary binaries are deleted afterwards (including `.exe` on Windows).

6. **Scoring command** - `python -m vulntrace fixtures score --method linker [--out <dir>]`
   - Runs the method on every manifest case; writes a JSON report (MethodResults plus truth) and a short Markdown table.
   - Scores `PRESENT` as a `REACHABLE` prediction and `ABSENT` as `NOT_REACHABLE`, for scoring only. These are not verdicts; verdicts start in CP2.
   - Prints counts: agreements, false `NOT_REACHABLE`, false `REACHABLE`, errors.

7. **Tests**
   - Unit: symbol-to-pattern mapping (function, value method, pointer method, generic → unsupported); `nm` output parsing from recorded sample text; schema validation of the manifest and example MethodResults; Windows-style paths.
   - Integration (skipped with a clear message if `go` is missing): linker method on every fixture case; determinism (two runs identical apart from timing); the five trial-3 cases reproduce the observed outcomes (direct `PRESENT`, safe-only `ABSENT`, function value `PRESENT`, reflection `PRESENT`, dead code `ABSENT`).

8. **Results document** - `docs/results/CP1_LINKER_RESULTS.md`
   - Environment, exact commands, per-case table (category, truth, observed), inlining comparison.
   - Every mismatch between truth and the linker result, explained. A mismatch is a finding about the method, not a bug to hide.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Unit tests pass with only Python installed. | Command and printed pytest summary. |
| 2 | Integration tests pass where Go is available. | Command, summary, `go version`. |
| 3 | Manifest and all written MethodResults validate against their schemas. | Test names and output. |
| 4 | The five trial-3 cases reproduce the feasibility observations, or the difference is reported and explained. | Results table. |
| 5 | Two scoring runs give identical results apart from timing. | Determinism test output. |
| 6 | No network use by tests or scoring. | Environment settings shown; `GOPROXY=off`. |
| 7 | `doctor` reports a missing Go toolchain correctly (tested by simulation). | Test name and output. |
| 8 | Scope respected: no LLM, embeddings, helper, dataset, database, retrieval or UI code. | File list in report. |
| 9 | `docs/results/CP1_LINKER_RESULTS.md` contains only observed numbers. | The file. |
| 10 | Report written to `docs/progress/reports/CP1_REPORT.md` in the wrapper format; STATUS.md set to `AWAITING_REVIEW`. | The files. |

## Out of scope

The Go helper and `golang.org/x/tools`; verdicts; vulndb, advisories and git fetching; any model; any database; performance tuning.

## Known risks

- Windows behaviour of `go tool nm` is unverified (cloud sessions run Linux; note this as untested on Windows).
- Generic and `unsafe` categories may disagree with truth. That is expected and informative.

## Review notes

(The supervising assistant adds notes here if the state becomes `CHANGES_REQUESTED`.)
