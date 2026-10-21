# Testing strategy

Testing and evaluation are different. Tests check that code does what it is specified to do. Evaluation measures how well the approach works. Both are required.

## Test layers

| Layer | What it covers | Needs Go? | Needs network? | Needs LLM? |
|---|---|---|---|---|
| Unit | Pure Python logic: symbol-name mapping, `nm` output parsing, diff hunk parsing, verdict rule table, schema validation | No | No | No |
| Contract | Recorded helper JSON responses validated against schemas; error-code handling | No | No | No |
| Integration | Real `go build`, `go tool nm`, helper runs on the fixture module | Yes | No (`GOPROXY=off`) | No |
| Pipeline | End-to-end on 2-3 fixed cases with cached LLM responses | Yes | Only for first git fetch | No (cached) |
| Evaluation | Full datasets, metrics, reports | Yes | Yes | Yes (milestone 4+) |

## Rules

1. Unit and contract tests must pass on a machine with only Python installed.
2. Integration tests that need Go are skipped, not failed, when `go` is missing. The skip message must say why. A test report with skipped integration tests is not evidence that a milestone passed.
3. No test calls a live LLM API. LLM behaviour is tested with recorded responses, including deliberately invalid ones (wrong IDs, bad JSON).
4. No test depends on internet access. Git-based tests use small local repositories created inside the test.
5. Every bug found later gets a regression test before it is fixed.
6. Tests must run on both Linux and Windows. Path handling is tested with Windows-style input paths.
7. Determinism: running a method twice on the same input must produce identical results (excluding timing fields). This is an explicit test.

## What each milestone must test

- **M1:** symbol-to-`nm`-pattern mapping (functions, value methods, pointer methods, unsupported generic forms), `nm` output parsing from recorded samples, manifest and method-result schema validation, linker method on every fixture case, determinism.
- **M2:** helper contract (requests and responses), each helper error code, VTA results on fixtures, verdict rule table (every row), naive call-graph control.
- **M3:** vulndb report parsing on recorded YAML samples (including multi-module and `/vN` paths), diff-to-function mapping on a local test repository, E0 scoring maths on hand-computed examples.
- **M4:** LLM output validation (valid, invalid ID, invalid hunk, malformed JSON, empty selection), prompt construction is deterministic, cache keys, lifting on fixtures.
- **M5:** verifier checks (each check can fail independently), downgrade-only behaviour, full pipeline on cached cases.
- **M6:** experiments reuse the M4 validation path; strategies cannot bypass it.

## Commands

The exact commands are fixed in milestone 1 and recorded in the README. The expected form is:

```
python -m pytest tests/unit                 # plus tests/contract from M2 onward
python -m pytest tests/integration
python -m vulntrace doctor
python -m vulntrace fixtures score --method linker
```

## Reporting

Every milestone report lists the exact commands run, the pass / fail / skip counts as printed, and any test that was skipped with its reason. Claims like "all tests pass" without the printed output are not accepted.
