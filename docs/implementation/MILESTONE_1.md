# Milestone 1 - Ground truth and linker presence

## Goal

Create the synthetic reachability suite (truth known by construction) and the first reachability method, linker presence, with tests and an honest results report.

Milestone 1 contains no LLM, no call-graph helper, no advisory data, no network access and no database. It is deliberately small so it can be fully tested and reviewed.

## Why this milestone comes first

- Every later method is scored against this suite. If the ground truth is wrong, every later number is wrong.
- Linker presence uses only the Go toolchain, so it has the fewest moving parts.
- Feasibility trial 3 already observed five fixture outcomes. Reproducing them checks the implementation against known behaviour.

## Deliverables

1. **Python package skeleton**
   - `pyproject.toml` (Python 3.11+), `src/vulntrace/`, `tests/`.
   - Dev dependencies: `pytest`, `jsonschema`. No others without a written reason.
   - `.gitignore` covering `results/`, caches, virtual environments, `.env`, and built binaries.

2. **`doctor` command** - `python -m vulntrace doctor`
   - Prints Python version, `go version` (or "not found"), `go env GOOS GOARCH`, and whether `go tool nm` runs.
   - Exit code `0` if all M1 prerequisites are present, `3` otherwise.
   - Never installs or downloads anything.

3. **Schemas** in `schemas/`
   - `fixture_manifest.schema.json`
   - `method_result.schema.json`
   - Shapes as in [data model](../design/DATA_MODEL.md). Both carry `schema_version`.

4. **Fixture suite** in `fixtures/reachability/`
   - One Go module (suggested module path `vtfixtures`), Go version directive no newer than the oldest Go version you verify it with.
   - A fake vulnerable package (`vulnlib`) with at least a vulnerable function, a safe function, and a type with a method that calls the vulnerable function.
   - At least 12 cases, one `package main` per case. The five cases from feasibility trial 3 are mandatory. Choose the rest from the category list in [dataset strategy](../evaluation/DATASET_STRATEGY.md).
   - One case where the vulnerable function is small enough for the Go compiler to inline. Run it once with and once without `-gcflags=all=-l` and record both observed results in the results document (this validates [ADR-013](../decisions/ARCHITECTURE_DECISIONS.md)). Only the inlining-disabled run counts for scoring.
   - `fixtures/reachability/manifest.json` valid against the schema, with `truth` and a `rationale` for every case.
   - No external Go dependencies.

5. **Linker-presence method** - Python module (suggested `src/vulntrace/methods/linker.py`)
   - Builds a main package with `go build -gcflags=all=-l -o <temporary path>`.
   - Environment for the build: `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY=off`, `GOFLAGS` unset.
   - Runs `go tool nm` on the binary and matches target symbols using the rules in [interfaces and contracts](../design/INTERFACES_AND_CONTRACTS.md) section 3.
   - Returns one `MethodResult` per target symbol (`PRESENT`, `ABSENT`, `ERROR`), with matched binary symbol names, build flags, Go version, GOOS and GOARCH.
   - Generic symbols return `ERROR` with code `UNSUPPORTED_SYMBOL_FORM` unless the implementer verifies a matching rule and documents it.
   - Temporary binaries are deleted afterwards, including on Windows (`.exe` suffix).

6. **Scoring command** - `python -m vulntrace fixtures score --method linker [--out <dir>]`
   - Runs the method on every manifest case.
   - Writes a JSON report (list of `MethodResult` plus truth per case) and a short Markdown table.
   - Treats `PRESENT` as a `REACHABLE` prediction and `ABSENT` as `NOT_REACHABLE` for scoring only. It must not call these "verdicts"; verdicts start in M2.
   - Prints counts: agreements, false `NOT_REACHABLE`, false `REACHABLE`, errors.

7. **Tests** (see [testing strategy](../testing/TESTING_STRATEGY.md))
   - Unit: symbol-to-pattern mapping (function, value method, pointer method, generic → unsupported); `nm` output parsing from recorded sample text (include a Windows-style sample if one can be obtained, otherwise mark the gap); schema validation of the manifest and of example `MethodResult` objects; Windows-style path handling.
   - Integration (skipped with a clear message if `go` is not found): linker method on every fixture case; determinism (two runs give identical results apart from timing).
   - A test that asserts the five trial-3 cases produce the outcomes observed in the feasibility trial: direct `PRESENT`, safe-only `ABSENT`, function-value `PRESENT`, reflection `PRESENT`, dead-code `ABSENT`.

8. **Results document** - `docs/results/M1_LINKER_RESULTS.md`
   - Environment (OS, Go version, Python version).
   - Exact commands run.
   - The per-case table: category, truth, observed result.
   - Every mismatch between truth and the linker result, with an explanation. A mismatch is a finding about the method, not a bug to hide. Do not change fixture truth or code to make a mismatch disappear unless the fixture itself was wrong; if so, explain the change.

## Acceptance criteria

| # | Criterion | Evidence required |
|---|---|---|
| 1 | Unit tests pass with only Python installed. | Command and printed pytest summary. |
| 2 | Integration tests pass where Go is available. | Command, printed summary, `go version` output. |
| 3 | Manifest and all written `MethodResult` objects validate against their schemas. | Test names and output. |
| 4 | The five trial-3 cases reproduce the feasibility observations, or any difference is reported and explained. | Results table. |
| 5 | Two consecutive scoring runs produce identical results (apart from timing). | Determinism test output. |
| 6 | No network access is needed or used by tests or scoring. | Environment settings shown; `GOPROXY=off` used. |
| 7 | `doctor` correctly reports a missing Go toolchain (tested by simulation). | Test name and output. |
| 8 | Scope respected: no LLM, call-graph helper, dataset code, database, retrieval or UI. | File list in the report. |
| 9 | `docs/results/M1_LINKER_RESULTS.md` exists with real observed numbers only. | The file. |
| 10 | The implementer's report follows the format in the Round 1 prompt. | The report. |

## Out of scope for milestone 1

- The Go helper and any `golang.org/x/tools` dependency.
- Verdicts and the verdict rule.
- Advisories, vulndb, fix commits, git fetching.
- LLM calls, embeddings, retrieval, agents.
- Any database.
- Performance tuning.

## Known risks for milestone 1

- Windows behaviour of `go tool nm` and `.exe` handling is unverified.
- Some categories (generics, `unsafe`) may produce linker results that disagree with truth. That is expected to be informative.
- If Go is not installed where Claude Code runs, integration criteria cannot be met; the report must say so rather than claim success.
