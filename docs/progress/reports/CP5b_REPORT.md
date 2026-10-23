# CP5b report: lifting and caller/callee queries (Go helper)

Branch `claude/eloquent-shannon-baphva`. No pull request opened (as instructed). All numbers below were printed in this session or are in `docs/results/CP5B_LIFTING_RESULTS.md`, which is generated from the committed JSON.

## 1. Environment

- OS: Linux 6.18.44-fc-v153 x86_64, 4 CPU, 15 GB RAM; Python 3.13.16 (CI uses 3.12); git 2.43.0; Docker 29.9.1 (not used); `go version go1.24.7 linux/amd64` (the default, used for all tests).
- **The D1/D4 evaluation runs used `go1.26.10`** as the local toolchain on `PATH` (`GOTOOLCHAIN=local`, `CGO_ENABLED=0`). Reason: with go1.24.7, 31 of the 99 lifting cases failed with `go.mod requires go >= 1.25/1.26` (first pass, kept in the scratch area), nearly all post-cutoff advisories. The toolchain was fetched from the Go module proxy into a scratch directory (checksum verified by the Go checksum database), not installed system-wide. x/tools stays at v0.42.0; a go1.27.3 try made the SSA builder panic (`unexpected expr: *ast.KeyValueExpr`), go1.26.10 passes all helper tests.
- Network: Go proxy, GitHub (git fetch) and PyPI reachable. `pip install -e .` was also run once into the system Python before a venv was used (a small breach of "no system-wide installs"); all tests ran in a venv.
- Disk is a 40 GB allowance: the module cache reached 22 GB and one run was nearly stopped; module-cache zips were deleted during runs and the cache wiped once (results unaffected: per-case results were saved).

## 2. Files changed

- `helper/query.go` (new), `contract.go`, `main.go`: `lift`, `callers`, `callees` modes (library and app loading, closure folding, NEAREST/ALL, depth limit, ROOT_ONLY, generics, load report). `helper/query_test.go`: Go tests.
- `schemas/helper_request|response.schema.json` extended; `lift_record`, `neighbor_record` added; `src/vulntrace/schemas.py`.
- `src/vulntrace/methods/lift.py`: Python wrappers. `src/vulntrace/eval/lift_prep.py`, `lift_eval.py`, `lift_cli.py`, `lift_ceiling.py`, `lift_report.py`: `eval lift`, D4 ceiling, `results render --doc cp5b`; `__main__.py`, `results_doc.py`.
- `fixtures/lifting/` (17 cases + manifest).
- Task 0: `dataset/git_fetch.py` (0a), `llm/ollama_setup.py` + notebook (0b), `D4_cases.json` (0c), `D1_cases.json` (0a, see 7), `llm_report.py` + `CP5_LLM_RESULTS.md` (0d).
- Tests: `tests/unit/test_lift_*.py`, `test_ollama_setup.py`, `test_committed_case_lists.py`, `test_cp5_hyde_note.py`, `test_cp5b_committed_results.py`, `tests/contract/test_lift_contract.py` + `responses_cp5b/` + recorder, `tests/integration/test_lift_fixtures.py`, additions to `test_git_fetch.py`, `test_cp5_notebook.py`, `test_cp2_schemas.py` (see 7).
- Docs: `INTERFACES_AND_CONTRACTS.md`, `README.md`, `docs/results/cp5b/*`, `CP5B_LIFTING_RESULTS.md`.

## 3. Deliverables

Task 0a done (cause found, one pass converges, test, workaround removed). 0b done in code; **the Ollama path itself was not run** (no Ollama here), only its logic with fakes. 0c, 0d done. D1 `lift`: done. D2 `callers`/`callees` + wrappers + schemas: done. D3 fixtures: done (17, observed). D4 `eval lift` on D1, E1+L, D4 ceiling: done. D5 tests: done.

## 4. Test evidence

- `go vet`, `gofmt -l` (empty), `go test ./...` in `helper/` (go1.24.7): `ok vulntrace/helper 4.760s`.
- `pytest tests/unit tests/contract tests/integration --deselect tests/integration/test_network_smoke.py`: `661 passed, 9 skipped, 2 deselected in 179.65s` (9 skips = pgvector without a database).
- Fixture integration (`test_lift_fixtures.py`): 25 passed, including the diamond (NEAREST {Left, Right}, ALL adds Top), ROOT_ONLY and determinism.
- CI on the branch tip `08b5c62`: conclusion `success` (GitHub Actions run 39934360504).
- The new git test fails without the 0a fix (2 failed) and passes with it.

## 5. Acceptance criteria

1. Task 0: **Met** (0b not exercised against a real Ollama).
2. Modes and schemas: **Met**; the 12 older recordings still validate (test).
3. Both rules compared on fixtures and D1: **Met**.
4. Fixture truths by running: **Met**; one truth was wrong and changed: `method_value` only passed the method value to an unknown parameter (no call edge), the helper said ROOT_ONLY, the fixture now calls it.
5. `eval lift` on D1: **Met**. 99 of 150 D1 cases have `derived_symbols`; module loaded 97; lifted 86 (0.869); failures LOAD_FAILED 1, NO_MODULE 1, ROOT_ONLY 7, SEED_ERROR 4 (each with its first error line in the results document).
6. E1+L vs E1 vs E0, D4 ceiling: **Met** (a real run, on this machine, no Colab needed).
7. No analysed code executed, `GOTOOLCHAIN=local`, `CGO_ENABLED=0`: **Met by construction** (sources unpacked with `git archive`, only `go mod tidy -e` and `go list`-based loading; no generate/test/run). Not independently audited beyond the unit test that lists the `go` calls.
8. Tests pass locally and in CI, nothing bulky committed: **Met** (`git ls-files`: no data/, caches or third-party source; every result file under 512 KiB).
9. This report and STATUS: **Met**.

## 6. Results (from `docs/results/CP5B_LIFTING_RESULTS.md`)

- Lifting vs `derived_symbols`, cases that lifted (86), new symbols only: NEAREST precision 0.727 [0.613, 0.837] (n=53 with a prediction), recall 0.253 [0.186, 0.327]; ALL precision 0.473 [0.359, 0.587] (n=55), recall 0.466 [0.369, 0.569]. ALL minus NEAREST: recall +0.213 [0.153, 0.278], precision -0.097 [-0.159, -0.041], F1 no detectable difference. Mean lifted set 7.4 (NEAREST) vs 57.9 (ALL). Counting failures as nothing predicted, recall falls to 0.220 / 0.405 (99 cases).
- E1+L (headline groups, gold core ∪ derived, paired with E1): llama (104 cases) replace/NEAREST ΔF1 +0.030 [-0.021, 0.082], add/NEAREST +0.070 [0.032, 0.111], add/ALL +0.054 [0.006, 0.110]; qwen (124 cases) add/NEAREST +0.090 [0.054, 0.127]. Against E0, F1 is not better in any variant (differences include 0 or are below), and replace hurts core-only gold. Lifting applied to 88 of 104 (llama headline).
- D4 ceiling: 17 of 120 cases have no core symbol among candidates; the graph loaded in 17; a candidate within 1 hop in 1/17, within 2 hops in 4/17 (all via callees; 2 of those 4 are in the >100 candidate bucket where this is likely by chance).
- Time/machine: this 4-CPU box. D1 lifting ran in three invocations (551 s with 3 jobs on go1.24, then 1626 s with 2 jobs, then 964 s with 1 job on go1.26); 3724.9 s summed per-case compute for the final set; D4 ceiling 311.7 s; D4 materialize 1563 s, D1 413 s.

## 7. Design deviations

- **0a also corrected 4 D1 records** (GO-2024-3005 50→56 candidates, GO-2026-4360 4→5, GO-2026-6165 and -6237 UNAVAILABLE→AVAILABLE). The committed D1 list had been written under the same bug (each had an "unfetchable" commit that is fetchable), and the CP5 Colab second pass had reproduced that state. The CP5 E1/E0 result files are unchanged; those four cases are excluded from E1+L as "evidence changed".
- Cause of 0a: a cached commit that is only the shallow boundary of an earlier fetch was trusted by `fetch_commit`, so the parent was missing. A later fetch of another commit in the same clone can cut the parent off again, so the lift code re-fetches before reading the parent.
- `test_cp2_schemas` no longer expects `lift` to be an invalid mode (it is now valid).
- Synthesised `go.mod` for pre-module trees (7 of the 86 lifted cases) and dropping a tree's own `vendor/` when it cannot load: not in the spec, flagged per case.
- The spec's "seed already exported lifts to itself" makes the literal metric punish such cases; the document therefore also shows a "new only" view.
- E1+L is defined two ways (replace/add); the spec did not say which. Both are shown.
- A first aggregation had a bug (E1 seeds read back by origin, lost when equal to a core seed: "lifting applied" 45/104). It showed as `SELECTED_OUTSIDE_MODULE 51` and was fixed before committing results.

## 8. Blockers and limitations

- Ollama check (0b) untested against a real server. Colab not used.
- Callbacks through dependencies are not followed; promoted methods are not entry points; cgo/other-OS code not loaded; one tree per case (first fix commit's parent); name-level matching.
- Memory: two modules (GO-2026-6773, GO-2026-6786) were OOM-killed even alone; neither is in the 99-case population but they affect E1+L coverage (LOAD_FAILED 4-5 cases).
- 7 ROOT_ONLY and 4 SEED_ERROR cases are measured outcomes (cgo-only, server entry points called from `main`).
- The 17-case ceiling is small; intervals were not computed for it.
- Low recall mostly reflects curator convention (e.g. gin `Context.ClientIP` is exported, so it lifts to itself, while the curators added `Engine.Run`, `Engine.ServeHTTP`); worked examples are in the document. I read the examples, not every case.

## 9. Suggestions for CP6 (not implemented)

- Callers/callees as agent tools are ready; the ceiling suggests graph expansion helps few cases.
- Keep all changed functions in Mode 1; use lifting as an added target ("add"), not a replacement.
- Decide whether `derived_symbols` convention (go further up than the first exported function) should be a third rule.

## 10. Git

Branch `claude/eloquent-shannon-baphva`, every push succeeded.

```
08b5c62 CP5b: commit results - lifting vs derived_symbols, E1+L, D4 ceiling, rendered document
9646a07 CP5b: E1+L takes the selected functions from the evidence, not from seed origins
1a0b247 CP5b: E1+L reports why lifting did or did not apply; compact result files; applied counts only E1 seeds
1dbf116 CP5b: lifting evaluation robustness - vendor fallback, furthest-progress failure reason, parent re-fetch, memory limit
b646dbe CP5b: write E1+L per-case rows to one file per model (keeps result files small)
ff49a45 CP5b: README commands for eval lift and the cp5b results document
90ed2cc CP5b: app-mode query modes use the main module as the module under study (+ test)
3455683 CP5b: document the lift, callers and callees helper modes in the interfaces contract
6f378cc CP5b: eval lift (D1 lifting vs derived_symbols, E1+L) and D4 ceiling, module preparation, results renderer
e158488 CP5b: STATUS ticks (task 0, helper modes, fixtures)
02c64c4 CP5b 0a: remove the double-run D1 materialize workaround from the CP5 notebook
92aa1ef CP5b 0a: correct four D1_cases.json records written under the shallow-boundary bug
78365cf CP5b: helper lift, callers and callees modes, lifting fixtures, schemas, wrappers, tests
6457219 CP5b 0d: state how many comparisons each model's HyDE table holds
addbf2e CP5b 0c: correct GO-2020-0006 in D4_cases.json (PSEUDO_VERSION_UNRESOLVED -> AVAILABLE)
7c83402 CP5b 0b: Ollama install check is a real generate call, with one repair
081b532 CP5b 0a: deepen a commit that is only a shallow boundary (D1 first-pass mismatch)
7755c3c CP5b: start, STATUS IN_PROGRESS, task list
```
