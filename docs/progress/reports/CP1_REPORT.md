# CP1 report - Ground truth and linker presence

Branch: `claude/vulntrace-checkpoint-continue-ia7tx5`. Session started from `main` at `06d921d` (fast-forwarded as instructed). No earlier CP1 branch existed (the only other remote branches were `main` and `design/vulntrace-blueprint`, both `READY` with no work).

## 1. Environment

```
OS:      Linux vm 6.18.44-fc-v140 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 GNU/Linux
Python:  3.13.16 (project venv .venv, pytest 9.1.1, jsonschema 4.26.0)
Go:      go version go1.24.7 linux/amd64   (go env GOOS GOARCH: linux amd64; default GOTOOLCHAIN=auto, overridden to local by the project)
git:     git version 2.43.0
Docker:  Docker version 29.9.1, build dfc520d   (present; not used in CP1)
```

`python -m vulntrace doctor` printed (exit 0): python 3.13.16, go1.24.7 linux/amd64, `go tool nm: runs`, docker present, git present, "all CP1 prerequisites present".

Network: the sandbox has outbound access through a proxy. It was used once, by `pip install pytest jsonschema` into `.venv` (project-local). Tests and scoring do not use it (see criterion 6).

## 2. Files changed

- `docs/progress/STATUS.md` - IN_PROGRESS, branch, task list, then AWAITING_REVIEW.
- `pyproject.toml` - package metadata, Python >= 3.11, dev extras `pytest`, `jsonschema`, pytest config.
- `.gitignore` - results/, caches, venvs, `.env`, model files, binaries.
- `README.md` - appended development commands.
- `src/vulntrace/{__init__,paths,schemas,env,__main__}.py` - package, repo paths, schema validation helpers, doctor, CLI.
- `src/vulntrace/methods/{__init__,linker}.py` - linker-presence method.
- `src/vulntrace/eval/{__init__,fixture_score}.py` - scoring, report JSON and Markdown writers.
- `schemas/fixture_manifest.schema.json`, `schemas/method_result.schema.json` - JSON Schemas.
- `fixtures/reachability/go.mod`, `vulnlib/vulnlib.go`, `initdep/initdep.go` - fixture Go module and fake vulnerable library.
- `fixtures/reachability/cmd/<18 cases>/main.go` (+ `tagged.go` in `build_tag_excluded`, `main_test.go` in `test_file_only`) - fixture programs.
- `fixtures/reachability/manifest.json` - 18 cases with truth and rationale.
- `tests/__init__.py`, `tests/unit/test_{symbols,nm_parse,schemas,doctor,scoring}.py`, `tests/integration/test_linker_fixtures.py` - tests.
- `docs/results/CP1_LINKER_RESULTS.md` - results document.
- `docs/progress/reports/CP1_REPORT.md` - this report.

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Package skeleton, `.gitignore` | Done |
| 2 | `doctor` command | Done |
| 3 | Two schemas with `schema_version` | Done |
| 4 | Fixture suite (>= 12 cases, 5 mandatory, inlining case, manifest) | Done (18 cases) |
| 5 | Linker-presence method | Done |
| 6 | Scoring command | Done (plus `--compare-inlining`, see deviations) |
| 7 | Unit and integration tests | Done |
| 8 | Results document | Done |

## 4. Test evidence

```
$ python -m pytest tests/unit
============================== 49 passed in 0.12s ==============================
$ python -m pytest tests/integration -v
============================== 7 passed in 8.02s ===============================
$ python -m pytest -q          (earlier full run)
56 passed in 8.70s
$ PATH=<empty dir> python -m pytest tests -q -rs     (Go hidden from PATH)
49 passed, 7 skipped in 0.12s     (skip reason: "SKIPPED: Go toolchain (`go`) not found on PATH")
$ PATH=<empty dir> python -m vulntrace doctor; echo $?
... go: not found ... missing prerequisites: go     -> exit code 3
$ python -m vulntrace fixtures score --method linker --compare-inlining --out results/cp1
agreements=17 false_not_reachable=0 false_reachable=0 errors=1 (of 18 cases)     (exit 0)
$ gofmt -l fixtures        (no output)
```

The skipped integration tests in the Go-hidden run are not evidence of anything; the 7 integration tests that matter passed in the run with Go present.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Unit tests pass with only Python installed | Met | `49 passed` with `go` removed from PATH (pytest and jsonschema were installed in the venv) |
| 2 | Integration tests pass where Go is available | Met | `7 passed`, go1.24.7 linux/amd64 |
| 3 | Manifest and all written MethodResults validate | Met | `test_manifest_file_validates`, `test_all_method_results_validate_against_schema`, `test_example_*` |
| 4 | Five trial-3 cases reproduce observations | Met | `test_trial3_cases_reproduce_observations`: direct PRESENT, safe-only ABSENT, function value PRESENT, reflection PRESENT, dead code ABSENT. `Impl.Run` was also PRESENT in the reflection binary (`test_reflection_case_keeps_method_symbols`) |
| 5 | Two scoring runs identical apart from timing | Met | `test_determinism_apart_from_timing` |
| 6 | No network use by tests or scoring | Met, with limit | Every go call uses `GOPROXY=off`, `GOTOOLCHAIN=local`, no `GOFLAGS` (`test_go_env_is_offline_and_local`, and the fake-runner tests assert these in the env passed to every call). The fixture module has no dependencies. I did not block the network to prove it; the evidence is the settings |
| 7 | `doctor` reports missing Go correctly (simulated) | Met | `test_doctor_simulated_missing_go`; also run for real with `go` hidden: exit 3 |
| 8 | Scope respected | Met | File list in section 2: no LLM, embeddings, helper, dataset, DB, retrieval or UI code |
| 9 | Results doc contains only observed numbers | Met | Built from `results/cp1/linker_score.json/.md`; the one nm observation for generics was printed by `go tool nm` in this session |
| 10 | Report written, STATUS `AWAITING_REVIEW` | Met | This file and STATUS.md |

## 6. Results

See `docs/results/CP1_LINKER_RESULTS.md`. Summary as produced: 18 cases, 17 agreements, 0 false NOT_REACHABLE, 0 false REACHABLE, 1 error (`generic_target`, `UNSUPPORTED_SYMBOL_FORM` by design). With inlining enabled, three cases (`inlined_small`, `method_value_receiver`, `method_pointer_receiver`) flip from PRESENT to ABSENT.

These results show the method is consistent with truth on friendly hand-built cases only. Two agreements are trivial (`build_tag_excluded`, `test_file_only`) and `unsafe_func_pointer` is not a real test of the method (it takes the function value). The suite contains no case where the symbol is in the binary but unreachable, which is the known weakness of presence checks. Do not read 17/18 as accuracy.

## 7. Design deviations

- **18 cases, not 12.** Added `method_value_receiver`, `method_pointer_receiver` (method targets, needed to exercise the method patterns on a real binary) and `generic_target` (documents the unsupported generic form).
- **Extra CLI flag `--compare-inlining`** on `fixtures score`, so the inlining comparison comes from code and applies to all cases rather than one. The spec said to record both runs for the inlining case; this is a superset. Scoring still uses only the `-l` run.
- **`Parse` is `//go:noinline`; `ParseTiny` is the inlinable function.** Without this, the five trial-3 cases would also be affected by inlining.
- **Extra error codes** `BUILD_FAILED`, `NM_FAILED`, `GO_NOT_FOUND` (the contract only names `UNSUPPORTED_SYMBOL_FORM`).
- **Generic detection** is by `[` / `]` in the symbol string; other unrecognised forms (e.g. `a.b.c`) also return `UNSUPPORTED_SYMBOL_FORM`.
- **Package-path escaping rule** (dots in the last path element become `%2e`, as in `gopkg.in/yaml%2ev3`) is implemented and unit-tested from my knowledge of Go's symbol encoding, **not observed in this session**. Treat as unverified until a fixture with a dotted package name exists.
- **Case-level prediction** for multi-target cases (any PRESENT -> REACHABLE, else any ERROR -> ERROR, else NOT_REACHABLE) is my choice; all current cases have one target.
- `go tool nm` availability in `doctor` is tested by running `go tool nm -h` and looking for its usage text.
- `GOWORK` is not set. The fixture module has no go.work above it in this repo.
- `duration_ms` of each MethodResult is the whole build plus nm for that package, shared by all targets of the case.

## 8. Blockers and limitations

- Not tested on Windows or macOS (the Windows `.exe` handling is tested only with a fake runner).
- One Go version (1.24.7) only.
- `interface_dispatch` truth: the quiet branch exists, so truth rests on the default execution path; the rationale says so.
- Commit messages for D1-D7 have the attribution trailers on the same paragraph as the subject line (shell quoting slip). Already pushed; not rewritten, per the no-history-rewrite rule.
- `results/` is git-ignored, so the raw JSON is not committed; the committed results doc was generated from it.

## 9. Suggestions for the next checkpoint

- Add a fixture where the symbol is linked in but unreachable (e.g. kept alive by another used function that does not reach it) to test the presence method's known weakness before CP2 builds the combined verdict on it.
- Add a dotted-package-name fixture to verify the `%2e` rule.
- Decide whether to derive a generic-symbol rule from several instantiations.

## 10. Git

Branch `claude/vulntrace-checkpoint-continue-ia7tx5`. All pushes up to commit `44f2af5` succeeded (branch was in sync with origin when checked). The final commit adding the results doc, README, report and STATUS is pushed after this file was written; its hash and push result are in the final session message.

```
44f2af5 CP1 D6/D7: scoring command and tests
2014a03 CP1 D5: linker-presence method
adbab56 CP1 D4: fixture suite (18 cases) and manifest
eeba9b0 CP1 D3: JSON schemas and validation helpers
2a8d667 CP1 D2: doctor command
59aab92 CP1 D1: Python package skeleton, .gitignore
ddfae3f CP1: start, record session branch and task list
```

## Correction (added in CP2, task 0)

Criterion 9 ("`docs/results/CP1_LINKER_RESULTS.md` contains only observed numbers") was **not met in the repository at review time**: the file was never committed. The `.gitignore` pattern `results/` matched every directory named `results`, including `docs/results/`, so `git add` skipped the file silently, and the CP1 session did not check `git ls-files` before marking the criterion Met. The CP1 document was also assembled by hand from the score output rather than generated.

Fix: commit `c67edde` changes the pattern to `/results/` (top-level only) and adds `python -m vulntrace results render --doc cp1`, which generates the document from `results/cp1/linker_score.json`. The regenerated document is committed together with this correction; an integration test (`test_committed_cp1_results_doc_matches_a_fresh_run`) checks that its tables match a fresh scoring run. The CP1 numbers did not change (18 cases, 17 agreements, 0 false NOT_REACHABLE, 0 false REACHABLE, 1 error).
