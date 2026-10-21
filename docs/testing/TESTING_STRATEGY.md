# Testing strategy

Testing checks that code does what it is specified to do. Evaluation measures how well the approach works. Both are required, and they are kept separate: tests never run real models, and evaluations never replace tests.

## Test layers

| Layer | What it covers | Needs Go? | Needs network? | Needs real models? |
|---|---|---|---|---|
| Unit | Pure Python logic: symbol mapping, `nm` parsing, diff parsing, verdict table, schema validation, metrics maths, RRF, BM25 tokeniser | No | No | No |
| Contract | Recorded Go-helper and model responses validated against schemas; error handling | No | No | No (fakes) |
| Integration | Real `go build`, `go tool nm`, helper on fixtures; pgvector store against a local PostgreSQL if available; LangGraph agent loop with the fake LLM | Yes | No | No (fakes) |
| Pipeline | End-to-end on 2-3 fixed cases with cached model outputs | Yes | Only for the first git fetch | No (cached) |
| Evaluation | Full datasets with real models in Colab or on the laptop | Yes | Yes | Yes |

## Rules

1. Unit and contract tests pass on a machine with only Python installed.
2. Integration tests skip, not fail, when a tool (Go, PostgreSQL, Docker) is missing, with a message naming the tool. A report with skipped integration tests is not evidence that a checkpoint passed.
3. No test downloads a model or calls a model endpoint. Fakes are deterministic.
4. LLM and agent behaviour is tested with scripted fake responses, including invalid ones: out-of-set IDs, malformed JSON, tool calls with bad arguments, endless tool loops (budget must stop them).
5. No test depends on internet access. Git tests use small local repositories created inside the test.
6. Every bug found later gets a regression test before it is fixed.
7. Paths are tested with Windows-style input.
8. Determinism: the same input twice gives identical results (excluding timing fields).
9. A test asserts that the configured LLM endpoint is not a known paid API host.

## What each checkpoint must test

- **CP1:** symbol-to-`nm` mapping, `nm` parsing, schemas, linker method on fixtures, determinism, `doctor` with Go missing.
- **CP2:** helper contract and every error code, VTA on fixtures, naive control, every row of the verdict table.
- **CP3:** report parsing (`/vN` paths, multi-package, pseudo-versions, missing fields), diff-to-function mapping, release-range extraction on a local test repository, baseline metrics on hand-computed examples.
- **CP4:** chunk construction, BM25 tokenisation, RRF on hand-computed lists, both vector-store backends behind one interface test suite, retrieval metrics on hand-computed rankings, index freshness (changed hash → re-embed; unchanged → skip).
- **CP5:** LLM client request building, output validation (valid / invalid ID / malformed / empty), cache keys, HyDE switch, lifting on fixtures.
- **CP6:** each agent tool in isolation, budget enforcement, rejection of out-of-set answers, trace completeness, recovery from tool errors.
- **CP7:** each verifier check failing independently, downgrade-only behaviour, full pipeline on cached cases, demo page starts.
- **CP8:** the multi-agent variant reuses the same validation and budgets; it cannot bypass them.

## Commands

Fixed in CP1 and recorded in the README. Expected form:

```
python -m pytest tests/unit                  # plus tests/contract from CP2
python -m pytest tests/integration
python -m vulntrace doctor
```

## Reporting

Every checkpoint report lists exact commands, the printed pass / fail / skip summary, and every skipped test with its reason.
