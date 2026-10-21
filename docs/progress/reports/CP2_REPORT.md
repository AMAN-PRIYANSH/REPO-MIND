# CP2 report - Go call-graph helper and verdict rule

Branch: `claude/optimistic-shannon-397w1q`, started from `main` at `3963e75`. No continuation candidate existed: the other remote branches (`claude/vulntrace-checkpoint-continue-ia7tx5`, `design/vulntrace-blueprint`) carry CP1 states (`AWAITING_REVIEW` / `READY`), not CP2.

## 1. Environment

```
OS:      Linux vm 6.18.44-fc-v140 #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux  (platform: Linux-6.18.44-fc-v140-x86_64-with-glibc2.39)
Python:  3.13.16 (project venv .venv: pytest, jsonschema)
Go:      go version go1.24.7 linux/amd64 (go env GOOS GOARCH: linux amd64)
git:     git version 2.43.0
Docker:  Docker version 29.9.1, build dfc520d (present; not used)
Machine: 4 CPUs, 16 GB RAM
```

Network checks (outbound HTTPS goes through the sandbox proxy):

- `https://proxy.golang.org/golang.org/x/tools/@v/list` -> HTTP 200; `@latest` -> v0.52.0. `https://sum.golang.org/latest` -> 200. `https://pypi.org/simple/pytest/` -> 200.
- **Go module proxy worked from the session**: `go mod tidy` in `helper/` printed `go: downloading golang.org/x/tools v0.42.0` (plus `go-cmp`, `x/sync`, `x/mod`) and wrote `go.sum`. This was the only network use by Go. Helper builds, helper runs, tests and scoring all use `GOPROXY=off`.
- PyPI was used once, for `pip install -e ".[dev]"` into `.venv`.

## 2. Files changed

Task 0
- `.gitignore` - `results/` -> `/results/` (top level only); later also `/helper/helper`, `/helper/vt-helper`.
- `src/vulntrace/eval/run_info.py` - records command, OS, Python, Go, repo commit and dirty flag in every score report.
- `src/vulntrace/eval/results_doc.py` - generators for `docs/results/` (CP1 and CP2 documents).
- `docs/results/notes/cp1_linker.json` - hand-written per-case explanation prose for the CP1 document (no numbers).
- `docs/results/CP1_LINKER_RESULTS.md` - regenerated CP1 results document (now tracked).
- `docs/progress/reports/CP1_REPORT.md` - appended "Correction" section only.

D1 Go helper (`helper/`, module `vulntrace/helper`)
- `go.mod`, `go.sum` - `golang.org/x/tools v0.42.0` pinned.
- `main.go` - CLI, request decoding and validation, mode dispatch, panic -> INTERNAL, toolchain and peak RSS.
- `contract.go` - request/response types, error codes.
- `load.go` - go/packages loading with the safe environment, error classification, path relativisation.
- `reach.go` - SSA, CHA-seeded two-pass VTA, graph reduction, `reach` and `edges` modes.
- `graph.go` - deterministic reduced graph, multi-source BFS, up to k shortest paths, edge checks.
- `symbols.go` - vulndb symbol parsing, target lookup (TARGET_NOT_FOUND), wrapper exclusion, function naming.
- `naive.go` - name-only go/ast call graph (R1 control).
- `funcs.go` - `funcs` mode.
- `graph_test.go`, `symbols_test.go`, `main_test.go`, `load_test.go` - Go unit tests.

D2 Python wrapper
- `src/vulntrace/methods/helper.py` - cached offline build outside the repo, explicit `fetch`, process-group timeout kill, response parsing and validation.
- `src/vulntrace/methods/callgraph.py` - CALLGRAPH_VTA MethodResults, error mapping.
- `src/vulntrace/methods/naive.py` - CALLGRAPH_NAIVE MethodResults.
- `src/vulntrace/__main__.py` - `helper build|fetch`, `fixtures score --method vta|naive|combined`, `--timeout`, `results render`.
- `pyproject.toml` - `jsonschema` moved into runtime dependencies (see deviations).

D3 Schemas
- `schemas/helper_request.schema.json`, `schemas/helper_response.schema.json`, `schemas/verdict.schema.json` - new.
- `schemas/method_result.schema.json` - added the value `CALLGRAPH_NAIVE` only.
- `src/vulntrace/schemas.py` - registers the new schemas.

D4 Verdict rule
- `src/vulntrace/verdict.py` - rule table, case aggregation, Verdict builder.

D5 Fixtures
- `fixtures/reachability/cmd/{present_but_unreachable,closure_never_called,method_expression,interface_two_impls_one_used}/main.go` - new cases.
- `fixtures/reachability/manifest.json` - four new cases; `unsafe_func_pointer` rationale annotated (truth unchanged).

D6 Scoring
- `src/vulntrace/eval/callgraph_score.py` - VTA, naive and combined scoring, counts, confusion matrix, Markdown.
- `src/vulntrace/eval/fixture_score.py` - `only=` case filter; `strip_timing` also drops `peak_rss_kb`, `created_at`.

D7 Tests
- `tests/unit/test_verdict.py`, `test_cp2_schemas.py`, `test_helper_build.py`, `test_callgraph_scoring.py`, `test_results_doc.py` - unit tests.
- `tests/contract/test_helper_contract.py`, `tests/contract/record_responses.py`, `tests/contract/responses/*.json` (12 responses + `index.json`) - contract tests and recordings.
- `tests/integration/test_callgraph_fixtures.py` - new; `tests/integration/test_linker_fixtures.py` - CP1-doc regeneration test added (CP1 case set only).

D8 and docs
- `docs/results/CP2_CALLGRAPH_RESULTS.md` - generated results document.
- `docs/results/notes/cp2_callgraph.json` - hand-written explanation prose for the CP2 document.
- `README.md` - CP2 development commands.
- `docs/progress/STATUS.md` - state, branch, task list.
- `docs/progress/reports/CP2_REPORT.md` - this report.

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| T0 | CP1 carry-over | Done |
| 1 | Go helper (`funcs`, `reach`, `edges`, `naive`) | Done (generic targets supported, see deviations) |
| 2 | Python wrapper | Done |
| 3 | Schemas | Done |
| 4 | Verdict rule | Done (verifier column not applicable, `verification.status = NOT_RUN`) |
| 5 | New fixture cases (>= 4) and `unsafe_func_pointer` annotation | Done (4 cases) |
| 6 | Scoring `--method vta / naive / combined` | Done |
| 7 | Tests (unit, contract, integration, Go) | Done |
| 8 | Results document | Done |

## 4. Test evidence

All commands run in this session, on the final tree unless noted.

```
$ .venv/bin/python -m pytest tests/unit tests/contract -q
138 passed in 0.42s
$ PATH=<empty dir> .venv/bin/python -m pytest tests/unit tests/contract -q      # Go hidden
138 passed in 0.41s
$ PATH=<empty dir> .venv/bin/python -m pytest tests/integration -q -rs         # Go hidden
22 skipped in 0.04s     (each: "SKIPPED: Go toolchain (`go`) not found on PATH")
$ .venv/bin/python -m pytest tests/integration -q -rs -p no:cacheprovider
22 passed in 165.30s (0:02:45)
$ (cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 GOPROXY=off GOFLAGS= go test -count=1 ./...)
ok  	vulntrace/helper	0.412s
$ go vet ./... (helper/ and fixtures/reachability/)    -> no output, exit 0
$ gofmt -l helper fixtures                              -> no output
$ python -m vulntrace fixtures score --method naive     (at clean commit 77d731c)
false_not_reachable=6 false_reachable=4 agreements=11 cant_determine=0 errors=1 (of 22 cases)
$ python -m vulntrace fixtures score --method vta
false_not_reachable=2 false_reachable=0 agreements=19 cant_determine=0 errors=1 (of 22 cases)
$ python -m vulntrace fixtures score --method combined
false_not_reachable=0 false_reachable=0 agreements=16 cant_determine=6 errors=0 (of 22 cases)
$ python -m vulntrace fixtures score --method linker --out results/cp2
false_not_reachable=0 false_reachable=2 agreements=19 cant_determine=0 errors=1 (of 22 cases)
$ python -m vulntrace fixtures score --method linker --compare-inlining --out results/cp1   (Task 0, at c67edde)
agreements=17 false_not_reachable=0 false_reachable=0 errors=1 (of 18 cases)
```

The skipped run with Go hidden is evidence for criterion 2 only. It says nothing about criterion 3, which rests on the `22 passed` run with Go present.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Task 0 done | Met | `git ls-files docs/results` lists `CP1_LINKER_RESULTS.md`; `.gitignore` has `/results/` (`c67edde`); document generated by `results render --doc cp1` and committed in `9dc1a8a` with the CP1 report correction. `test_committed_cp1_results_doc_matches_a_fresh_run` regenerates its tables from a fresh linker run (CP1's 18 cases). |
| 2 | Unit and contract tests pass with only Python | Met | `138 passed` with Go removed from PATH (pytest and jsonschema in the venv). |
| 3 | Integration and `go test ./...` pass where Go is available | Met | `22 passed in 165.30s`; `ok vulntrace/helper`. Go 1.24.7 linux/amd64. |
| 4 | Every helper error code and TIMEOUT / HELPER_MISSING has a test | Met | BAD_REQUEST, CONTRACT_MISMATCH, LOAD_FAILED, TYPE_ERRORS, INTERNAL, TARGET_NOT_FOUND (response level): `test_response_level_errors_map_to_error_results[error_*.json]`, `test_recordings_cover_every_helper_error_code`; Go `TestRequestErrors`, `TestUsageErrors`, `TestLoadErrorsAreClassified`, `TestPanicBecomesInternal`. Per target TARGET_NOT_FOUND / UNSUPPORTED_SYMBOL_FORM: `test_per_target_errors_never_become_no_path`, Go `TestReachTargetNotFoundIsNotNoPath`, `TestParseSymbol`. TIMEOUT: `test_timeout_maps_to_timeout`, integration `test_timeout_is_reported_as_timeout`. HELPER_MISSING: `test_unrunnable_binary_maps_to_helper_missing`, `test_unbuildable_helper_maps_to_helper_missing`, `test_build_failure_and_missing_go_are_helper_missing`. Extra BAD_RESPONSE: `test_malformed_responses`, `test_response_for_other_targets_is_rejected`. INTERNAL and response-level TARGET_NOT_FOUND recordings are **synthesised** (marked in `index.json`); INTERNAL from the real code path is covered by Go `TestPanicBecomesInternal`. |
| 5 | R1-R4 scored on all fixtures and reported | Met | `docs/results/CP2_CALLGRAPH_RESULTS.md`, 22 cases each. |
| 6 | Combined verdict: zero false NOT_REACHABLE, or explained | Met | 0 false NOT_REACHABLE (summary table; `test_combined_has_no_false_not_reachable`). The rule was implemented as written and not changed. |
| 7 | Naive control's false NOT_REACHABLE shown | Met | 6 cases: `func_value_map`, `reflect_method`, `method_value`, `generic_call`, `unsafe_func_pointer`, `method_expression` (per-case table; `test_naive_control_misses_function_value_and_reflection_paths`). |
| 8 | Disagreements produce CANT_DETERMINE / METHOD_DISAGREEMENT | Met | `reflect_method`, `unsafe_func_pointer`, `present_but_unreachable`, `closure_never_called` (per-case table; `test_method_disagreement_gives_cant_determine`). No PATH_FOUND + ABSENT anomaly occurred. |
| 9 | TARGET_NOT_FOUND never becomes NO_PATH | Met | `test_target_not_found_is_never_no_path` (integration), `test_per_target_errors_never_become_no_path` (contract), Go `TestReachTargetNotFoundIsNotNoPath`. |
| 10 | Helper peak memory and time on the largest fixture recorded | Met | Results document, "Helper resources": the largest is `reflect_method` (1414 call-graph nodes), helper time 1394 ms, peak RSS 233 MB. Linux `VmHWM` only; one run, no repeat statistics. |
| 11 | No binaries, caches or `results/` committed; `docs/results/` committed | Met | `git ls-files | grep ^results/` -> none; no `vt-helper`, `.exe`, `__pycache__`, `.venv` tracked; the helper cache is `~/.cache/vulntrace/helper/<hash>/vt-helper` (outside the repo; `ensure_helper` refuses a cache inside it, `test_cache_inside_repository_is_refused`). `docs/results/` holds both documents and both notes files. |
| 12 | Report written; STATUS `AWAITING_REVIEW` | Met | This file; STATUS.md. |

## 6. Results

Copied from `docs/results/CP2_CALLGRAPH_RESULTS.md` (generated from `results/cp2/*.json`, runs at clean commit `77d731c`):

### Summary (false NOT_REACHABLE first)

| Experiment | Method | Cases | False NOT_REACHABLE | False REACHABLE | Agreements | CANT_DETERMINE | Errors |
|---|---|---|---|---|---|---|---|
| R1 | Naive name-only graph (control) | 22 | 6 | 4 | 11 | 0 | 1 |
| R2 | Linker presence | 22 | 0 | 2 | 19 | 0 | 1 |
| R3 | VTA call graph | 22 | 2 | 0 | 19 | 0 | 1 |
| R4 | Combined verdict (VTA + linker) | 22 | 0 | 0 | 16 | 6 | 0 |

Single methods never abstain: their `ERROR` results are counted as errors. The combined verdict turns every error into `CANT_DETERMINE` / `ANALYSIS_FAILED`, so it has no errors column of its own.

Combined `CANT_DETERMINE` by reason code: `ANALYSIS_FAILED` 2, `METHOD_DISAGREEMENT` 4.

Combined verdict against truth (rows: truth; columns: verdict):

| Truth | REACHABLE | NOT_REACHABLE | CANT_DETERMINE |
|---|---|---|---|
| REACHABLE | 11 | 0 | 3 |
| NOT_REACHABLE | 0 | 5 | 3 |

These are hand-built cases with truth known by construction. They show where each method breaks; they are not an accuracy estimate.

### Per-case results

| Case | Category | Truth | R1 naive | R2 linker | R3 VTA | R4 verdict | Reason codes |
|---|---|---|---|---|---|---|---|
| direct_call | DIRECT | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| safe_only | SAFE_ONLY | NOT_REACHABLE | NO_PATH | ABSENT | NO_PATH | NOT_REACHABLE | - |
| func_value_map | FUNC_VALUE | REACHABLE | NO_PATH | PRESENT | PATH_FOUND | REACHABLE | - |
| reflect_method | REFLECTION | REACHABLE | NO_PATH | PRESENT | NO_PATH | CANT_DETERMINE | METHOD_DISAGREEMENT |
| dead_code | DEAD_CODE | NOT_REACHABLE | NO_PATH | ABSENT | NO_PATH | NOT_REACHABLE | - |
| interface_dispatch | INTERFACE_DISPATCH | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| interface_not_instantiated | INTERFACE_NOT_INSTANTIATED | NOT_REACHABLE | PATH_FOUND | ABSENT | NO_PATH | NOT_REACHABLE | - |
| method_value | METHOD_VALUE | REACHABLE | NO_PATH | PRESENT | PATH_FOUND | REACHABLE | - |
| goroutine | GOROUTINE | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| init_imported | INIT_IMPORTED | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| build_tag_excluded | BUILD_TAG_EXCLUDED | NOT_REACHABLE | ERROR (TARGET_NOT_FOUND) | ABSENT | ERROR (TARGET_NOT_FOUND) | CANT_DETERMINE | ANALYSIS_FAILED |
| test_file_only | TEST_FILE_ONLY | NOT_REACHABLE | NO_PATH | ABSENT | NO_PATH | NOT_REACHABLE | - |
| generic_call | GENERIC_CALL | REACHABLE | NO_PATH | PRESENT | PATH_FOUND | REACHABLE | - |
| inlined_small | INLINED_SMALL | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| unsafe_func_pointer | UNSAFE_FUNC_POINTER | REACHABLE | NO_PATH | PRESENT | NO_PATH | CANT_DETERMINE | METHOD_DISAGREEMENT |
| method_value_receiver | METHOD_TARGET_VALUE | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| method_pointer_receiver | METHOD_TARGET_POINTER | REACHABLE | PATH_FOUND | PRESENT | PATH_FOUND | REACHABLE | - |
| generic_target | GENERIC_TARGET | REACHABLE | PATH_FOUND | ERROR (UNSUPPORTED_SYMBOL_FORM) | PATH_FOUND | CANT_DETERMINE | ANALYSIS_FAILED |
| present_but_unreachable | PRESENT_BUT_UNREACHABLE | NOT_REACHABLE | PATH_FOUND | PRESENT | NO_PATH | CANT_DETERMINE | METHOD_DISAGREEMENT |
| closure_never_called | CLOSURE_NEVER_CALLED | NOT_REACHABLE | PATH_FOUND | PRESENT | NO_PATH | CANT_DETERMINE | METHOD_DISAGREEMENT |
| method_expression | METHOD_EXPRESSION | REACHABLE | NO_PATH | PRESENT | PATH_FOUND | REACHABLE | - |
| interface_two_impls_one_used | INTERFACE_TWO_IMPLS_ONE_USED | NOT_REACHABLE | PATH_FOUND | ABSENT | NO_PATH | NOT_REACHABLE | - |

Largest fixture by call-graph size: `reflect_method` (1414 nodes, 4680 edges): helper time 1394 ms, wall time 1417 ms, peak RSS 233 MB. Highest peak RSS over all cases: 245 MB.

The per-case table, the VTA paths, the resource table for every case, and the explanation of every mismatch are in the results document.

How to read these numbers. The cases are hand-built, with truth known by construction, and several were designed to break a specific method. The counts show where each method fails, not how accurate it is. The headline finding is a qualitative one: VTA alone gives a false NOT_REACHABLE on reflection and on `unsafe.Pointer`, and the linker alone gives a false REACHABLE on present-but-unreachable code. The verdict rule converts both kinds of failure into CANT_DETERMINE on this suite.

## 7. Design deviations

- **x/tools v0.42.0, not the newest release (v0.52.0).** Releases from v0.43.0 on declare `go 1.25.0` or later in `go.mod` (checked on the proxy for v0.41.0-v0.52.0). They cannot be built with `GOTOOLCHAIN=local` on the installed Go 1.24.7. v0.42.0 is the newest release that declares `go 1.24.0`.
- **VTA construction follows govulncheck**: a CHA graph, then VTA over the functions CHA reaches from the roots, then a second VTA pass over what the first pass reaches. The spec says only "VTA seeded from CHA". Roots are `main` and the main package's synthetic `init` (package initialiser), which calls every imported package's initialisers.
- **Generic targets are supported in `reach`**, not refused. `ParseAny[T]` and `ParseAny` both match the declared generic function and all its instances (`ParseAny[string]`). Go tests cover generic functions and methods of generic types. The linker still returns UNSUPPORTED_SYMBOL_FORM.
- **TARGET_NOT_FOUND is per target** (`result: ERROR`, `error.code: TARGET_NOT_FOUND`), so the other targets of a request still get answers. The response-level form stays in the schema because the contract lists it, but the helper does not emit it.
- **Paths longer than `max_path_length`** are reported as `PATH_FOUND` with `paths: []`, `shortest_length` set, and `paths_omitted: "MAX_PATH_LENGTH"`. Reporting them as NO_PATH would create a false NOT_REACHABLE.
- **Extra response fields**: `shortest_length`, `paths_omitted`, `matched_functions`; `stats.callgraph_edges` and `stats.peak_rss_kb`. **`edges` mode format** (not specified in the contract): queries use the CallPath edge names (`"pkgpath.Symbol"`) with an optional `call_site`. Results carry `exists`, `caller_found`, `callee_found`, `call_sites` and `kinds`.
- **Synthetic call sites**: calls inside compiler-generated package initialisers have no source position and are reported as `{"file": "", "line": 0}`. The schemas therefore allow `line: 0`.
- **Function names for nodes vulndb never names**: closures `main$1`, bound-method wrappers `T.M$bound`, thunks `T.M$thunk`, pointer wrappers `T.M$wrapper`, instances `F[string]`, user `init` functions `init#1`. Wrappers never match a target.
- **Extra Python-side codes**: `BAD_RESPONSE` (stdout not one JSON object, schema violation, wrong mode, or results for other targets); `CONTRACT_MISMATCH` is also raised by Python when the response major version differs.
- **`jsonschema` is now a runtime dependency** (`pyproject.toml`), because the wrapper validates every helper response at run time as the spec requires. CP1 had it only as a dev dependency.
- **Helper build is offline** (`GOPROXY=off`). Downloading the helper's own dependencies is an explicit step, `python -m vulntrace helper fetch`, following the contract rule that downloads happen only in an explicit, user-allowed step. The cache key is a hash of `go.mod`, `go.sum` and the non-test `.go` files plus `go version`.
- **The timeout kills the whole process group** (POSIX) so `go list` children do not outlive the helper. On Windows only the helper process is killed (untested).
- **Verdict additions**: `target_app.main_package` (optional) and `per_symbol[].method_errors` (optional, the error code of each failing method). `verified_path` is always `null` in CP2, because nothing is verified before CP7. `reason_codes` is empty for REACHABLE and NOT_REACHABLE; for CANT_DETERMINE it is the sorted set of the symbols' reason codes.
- **Naive control semantics**, chosen because the spec only says "calls written by name": `f()` resolves to the same package's function, `pkg.F()` to the imported package's function, and `x.M()` to every method named `M` in every analysed package (marked DYNAMIC). Calls inside function literals are attributed to the enclosing declaration. Only non-standard-library packages are parsed. Roots are `main` and every `init`.
- **Fixture construction change, observed and recorded.** In my first version of `present_but_unreachable` and `interface_two_impls_one_used`, the compiler devirtualised `r.Run`; `-gcflags='-l -m'` printed `devirtualizing r.Run to quiet` / `to echo`. With no interface call left, the linker dropped `loud.Run` (observed linker ABSENT), so the case did not do what the spec designs it for. Both cases now get `r` from a constructor. Truth labels are unchanged, and the rationale and the results notes describe this.
- **CP1 results document generator.** The original CP1 document was never committed, so it was rebuilt by a generator. The tables come from the score JSON. The explanation prose lives in `docs/results/notes/*.json` and is inserted only for cases the data flags; a test fails if any flagged case has no note. The CP1 document stays CP1's record: its regeneration test runs only CP1's 18 cases. The CP2 document reports the linker on all 22 cases.
- `unsafe_func_pointer` was **annotated, not renamed** (id and category kept, so CP1 and CP2 results stay comparable). The CP2 observation changes the CP1 review conclusion in one respect: the case does exercise `unsafe` for VTA (NO_PATH), though not for the linker.

## 8. Blockers and limitations

- **I pushed one commit with a failing test.** `35c50b9` (D6) was committed and pushed while `tests/unit/test_callgraph_scoring.py::test_write_score_and_markdown` failed. My shell chain `pytest ... | tail -1 && git commit` took `tail`'s exit status, not pytest's. The test itself was wrong: it replayed a `reach` response for a `naive` request, and the wrapper correctly rejected the mismatch. Fixed in `44c6d7f`, which also adds a test for that rejection. Every later commit chain ran with `set -o pipefail`. History was not rewritten.
- `build_tag_excluded` (truth NOT_REACHABLE) ends as CANT_DETERMINE / ANALYSIS_FAILED. The target package is not part of the loaded program, and the contract requires TARGET_NOT_FOUND there, not NO_PATH. This is safe, but on real applications that never import the vulnerable package it will cost answers. A proposed change is in the results notes; I did not implement it, because it changes the contract.
- `generic_target` ends as CANT_DETERMINE / ANALYSIS_FAILED because the linker has no generic rule, although VTA found the path.
- Explanations of linker behaviour cite the dead-code pass's data structures in Go 1.24.7 `cmd/link/internal/ld/deadcode.go` (`ifaceMethod`, `markableMethods`, `reflectSeen`). I did not trace the linker for each case. Why the type assertion in `interface_two_impls_one_used` did not keep `Impl.Run` was observed, not explained.
- One Go version (1.24.7) and one OS (Linux). Windows paths are tested only as input normalisation; the `.exe` name, `LOCALAPPDATA` cache and Windows timeout kill are untested.
- Peak RSS comes from Linux `/proc/self/status` `VmHWM`; it is `null` on other systems. Times are from single runs.
- With the verifier missing, `PATH_FOUND + PRESENT` gives REACHABLE without verification. Dynamic edges in the reported paths (for example `main -> Parse [DYNAMIC]` in `func_value_map`) have not been checked.
- Contract recordings contain absolute paths of this sandbox in some error messages (for example `/usr/local/go1.24.7/...`). They are data, not secrets.

## 9. Suggestions for the next checkpoint

- Decide the contract question raised by `build_tag_excluded`: should "target package not imported by the program" be a distinct helper result, and may the verdict rule treat it as NO_PATH when the package path is trusted (curated)?
- Build a verified generic-symbol rule for the linker (from several instantiations' `nm` names), so generic targets can be answered.
- Add a fixture whose interface conversion is visible only through a package-level initialiser, and one where devirtualisation happens with inlining enabled, to measure how much linker presence depends on compiler optimisation.
- Design the CP7 verifier rule for synthetic call sites (`file: ""`, `line: 0`).
- Record helper resources on at least one real application. The fixtures (about 60 packages) say nothing about memory on large programs.

## 10. Git

Branch `claude/optimistic-shannon-397w1q`. Every push below succeeded (each `git push` printed `<old>..<new> claude/optimistic-shannon-397w1q -> claude/optimistic-shannon-397w1q`). The final commit, which adds this report and sets `AWAITING_REVIEW`, is pushed after this file is written. Its hash is in the session's final message.

```
74d2469 CP2 D8: generated CP2 results document; README commands
77d731c CP2 D7/D8: integration tests for VTA, naive, combined, edges, funcs; CP2 results-doc generator
44c6d7f CP2 D6: fix scoring unit test that replayed a reach response for a naive request
35c50b9 CP2 D6: fixtures score --method vta|naive|combined
0691cda CP2 D5: four new fixture cases; annotate unsafe_func_pointer rationale
05da4ee CP2 D4: verdict rule (rule table, case aggregation, reason codes, fixed statement)
60ba0f8 CP2 D2: Python wrapper for vt-helper (VTA and naive methods), contract tests
f327743 CP2 D3: helper request/response and verdict schemas; CALLGRAPH_NAIVE method value
68a0626 CP2 D1: Go helper vt-helper (funcs, reach, edges, naive)
9dc1a8a CP2 T0: commit generated CP1 results doc; correction note in CP1 report
c67edde CP2 T0: ignore only top-level /results/; generator for CP1 results doc
5dba1f1 CP2: start, record session branch and task list
```
