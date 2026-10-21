# CP3 report: Advisory dataset, fix evidence, release ranges, baselines (+ CI)

## 1. Environment

Printed by `python -m vulntrace doctor` and direct version checks, this session:

```
python: 3.13.16
platform: Linux x86_64
go: go version go1.24.7 linux/amd64
go env GOOS GOARCH: linux amd64
go tool nm: runs
docker: present (informational in CP1)
git: present
all CP1 prerequisites present
```

```
uname -a: Linux vm 6.18.44-fc-v140 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
git --version: git version 2.43.0
docker --version: Docker version 29.9.1, build dfc520d
```

Network: reachable. GitHub was fetched from repeatedly and for real throughout this checkpoint (bounded fetches for fix commits and release ranges against dozens of real third-party repositories, plus two deliberate opt-in network smoke tests run live). No outbound call was ever made to a paid LLM or embedding API; `vt-helper`'s `go tool nm`/`go build` are the only subprocesses the dataset code invokes besides `git`.

## 2. Files changed

Changes since this checkpoint's first commit (`a181a2f`), 66 files, +8513/-134 lines:

- `.github/workflows/ci.yml` (new) — CI: unit/contract, Go, integration jobs on push/PR.
- `helper/symbols.go`, `helper/reach.go`, `helper/contract.go`, `helper/load_test.go` — task 0a contract change (package-not-in-program → `NO_PATH`).
- `src/vulntrace/methods/linker.py`, `src/vulntrace/methods/callgraph.py` — task 0c generic-function prefix match; contract-change plumbing.
- `schemas/helper_response.schema.json` — `package_not_in_program` field.
- `vulndb.json` (new) — pinned vulndb commit, licence finding.
- `src/vulntrace/dataset/__init__.py`, `vulndb.py`, `govers.py`, `report.py`, `git_fetch.py`, `diffparse.py`, `fix_evidence.py`, `release_range.py`, `datasets.py`, `baselines.py`, `metrics.py`, `ceiling.py`, `build.py` (all new) — deliverables 1-7.
- `schemas/vuln_case.schema.json`, `fix_evidence.schema.json`, `release_range.schema.json` (new).
- `src/vulntrace/eval/symbols_score.py` (new), `src/vulntrace/eval/results_doc.py` (extended) — baseline scoring CLI and the CP3 results-doc generator.
- `src/vulntrace/__main__.py` — `dataset fetch|build`, `eval symbols` subcommands.
- `src/vulntrace/schemas.py` — registers the three new schemas.
- `pyproject.toml` — adds `pyyaml`.
- `tests/unit/test_govers.py`, `test_vulndb.py`, `test_report.py`, `test_diffparse.py`, `test_release_range_tags.py`, `test_datasets.py`, `test_metrics.py`, `test_baselines.py` (new); `test_symbols.py`, `test_scoring.py`, `test_results_doc.py` (extended) — deliverable 8 unit tests.
- `tests/integration/test_git_fetch.py`, `test_fix_evidence.py`, `test_release_range.py`, `test_ceiling.py` (new, no network); `test_network_smoke.py` (new, opt-in, `VULNTRACE_NETWORK_TESTS=1`, never in CI); `test_callgraph_fixtures.py`, `test_linker_fixtures.py` (extended for task 0a/0c) — deliverable 8 integration tests.
- `tests/contract/responses/*.json`, `test_helper_contract.py` — recordings updated for the `package_not_in_program` field.
- `fixtures/reachability/manifest.json` — regenerated after task 0a/0c.
- `docs/results/CP1_LINKER_RESULTS.md`, `CP2_CALLGRAPH_RESULTS.md` — regenerated after tasks 0a/0c.
- `docs/results/CP3_DATASETS_AND_BASELINES.md` (new) — deliverable 9.
- `docs/results/datasets/D1_cases.json`, `D4_cases.json` (new) — deliverable 5.
- `docs/results/notes/cp1_linker.json`, `cp2_callgraph.json` — regeneration notes.
- `README.md`, `docs/progress/STATUS.md` — commands, checklist, handoff notes.

## 3. Deliverables

| Item | Status |
|---|---|
| Task 0a: package-not-in-program → `NO_PATH` | Done |
| Task 0b: CI workflow | Done |
| Task 0c: generic symbols in linker | Done (partial by design — see below) |
| D1: vulndb snapshot pin + licence | Done |
| D2: report reader / `VulnCase` builder | Done |
| D3: Mode 1 `FixEvidence` | Done |
| D4: Mode 2 `ReleaseRange` | Done |
| D5: D1 + D4 datasets built and committed | Done |
| D6: E0 + B-ID baselines with metrics | Done |
| D7: Ceiling investigation (Q8) | Done |
| D8: Tests | Done |
| D9: Results document | Done |

Nothing was skipped or left unattempted.

## 4. Test evidence

Commands run in this session, with their printed summary lines:

```
$ .venv/bin/python -m pytest tests/unit tests/contract tests/integration -q
311 passed, 2 skipped in 140.04s (0:02:20)
```
(The 2 skips are the opt-in network smoke tests in `test_network_smoke.py`, gated by `VULNTRACE_NETWORK_TESTS`; they are not skipped in every run of this checkpoint — both were run live and passed earlier in this checkpoint's work, per the commit messages for D3/D4, but were not re-run in this final pass since they touch real third-party repositories and are explicitly out of CI.)

```
$ cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 go test -count=1 ./...
ok  	vulntrace/helper	0.389s
```

```
$ .venv/bin/python -u -m vulntrace dataset build --mode release
D4: 120 cases (eligible 500), status counts {'AVAILABLE': 103, 'EMPTY': 2, 'TRUNCATED': 14, 'PSEUDO_VERSION_UNRESOLVED': 1}
wrote /home/user/REPO-MIND/docs/results/datasets/D4_cases.json
```
(Third attempt; the first two were deliberately killed after finding real bugs — see Design deviations / Blockers.)

```
$ .venv/bin/python -m vulntrace eval symbols --strategy id-search
BASELINE_ID_SEARCH on D4: 120/120 scored
precision=0.490 recall=0.295 f1=0.193 exact_match=6
wrote results/cp3/id_search_score.json
```

```
$ .venv/bin/python -m vulntrace results render --doc cp3 --input results/cp3 --out docs/results/CP3_DATASETS_AND_BASELINES.md
wrote docs/results/CP3_DATASETS_AND_BASELINES.md
```

CI: all 14 runs on this branch are green (`conclusion: success`), including the task 0a/0b/0c commits and every dataset/baseline commit since, checked via the GitHub Actions API in this session. First CI run: https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39615369023 (green). Latest run: https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39637839032 (green, completed after this report's first draft — confirmed before the final commit).

## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Task 0a done; `build_tag_excluded` outcome reported; CP2 results regenerated | Met | `docs/results/CP2_CALLGRAPH_RESULTS.md` line 134: VTA now reports `NO_PATH`/`package_not_in_program=true`; combined with linker `ABSENT`, the verdict is `NOT_REACHABLE` (matches truth), where CP2 had abstained with `CANT_DETERMINE`/`ANALYSIS_FAILED`. |
| 2 | CI workflow exists; first run's URL and result reported; unit/contract/Go/integration jobs all run | Met | `.github/workflows/ci.yml`; first run https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39615369023, green; all 14/14 runs on this branch green, confirmed via the Actions API. |
| 3 | Task 0c attempted; outcome documented either way | Met | `docs/results/CP1_LINKER_RESULTS.md` line 83: bare generic functions now `PRESENT` via a prefix match (`pkg.Name[`); generic methods / methods on generic types still `UNSUPPORTED_SYMBOL_FORM` (no reliable rule found — the binary symbol is shape-specific, never the concrete type vulndb names). |
| 4 | vulndb commit pinned; licence finding recorded | Met | `vulndb.json`: commit `e0bad56276e98711a598adbab976de7cd914013a`, pinned 2026-10-21, 4710 reports; licence note: code BSD-3-Clause-style, `data/` CC-BY-4.0; project still commits only IDs/dates/counts/statuses, narrower than the licence requires, by choice. |
| 5 | D1 and D4 built with counts per status; nothing dropped silently | Met | D1: 150/506 eligible, 144 AVAILABLE/4 EMPTY/2 UNAVAILABLE. D4: 120/500 eligible, 103 AVAILABLE/2 EMPTY/14 TRUNCATED/1 PSEUDO_VERSION_UNRESOLVED. Malformed reports are counted in `load_all_cases`'s error count, never dropped silently. |
| 6 | Pseudo-version resolution works (tested), effect on D4 coverage reported | Met | Unit-tested against every real pseudo-version string observed in the corpus (897/898 resolve); only 1 D4 case (of 120) ended `PSEUDO_VERSION_UNRESOLVED` — reported in the status counts above and in the results doc. |
| 7 | E0 and B-ID reported with counts, intervals, date split | Met | `docs/results/CP3_DATASETS_AND_BASELINES.md`: E0 precision 0.584 [0.524,0.642] / recall 0.845 [0.788,0.900] / f1 0.631 [0.573,0.684] (core symbols, n=150, 144 scored); B-ID precision 0.490 [0.392,0.594] / recall 0.295 [0.215,0.378] / f1 0.193 [0.136,0.256] (n=120); both split by the `2026-06-30` placeholder cutoff. |
| 8 | Ceiling investigation reported with examples | Met | 119 D4 cases checked, 31 with a missing core symbol; `EXISTS_UNCHANGED` 57, `NOT_FOUND_EITHER_VERSION` 4, `MATCHING_PROBLEM` 0, `OTHER` 0 (symbol-level), 3 worked examples in the results doc. |
| 9 | All tests pass locally and in CI; no test needs network by default | Met | 311 passed, 2 skipped (opt-in only) locally; Go tests pass; CI green on every completed run on this branch. |
| 10 | No vulndb content, caches or bulky evidence committed | Met | `git ls-files \| grep -iE "data/reports\|vulndb-src\|\.yaml$"` returns nothing; `git ls-files \| grep "^data/"` returns nothing — checked this session. |
| 11 | CP3_REPORT.md in wrapper format; STATUS `AWAITING_REVIEW` | Met | This file; STATUS.md updated in the same commit as this report. |

## 6. Results

Copied from `docs/results/CP3_DATASETS_AND_BASELINES.md` (generated by code, not retyped by hand):

**D1**: 150 cases, eligible pool 506, seed 20261021. Status counts: AVAILABLE 144, EMPTY 4, UNAVAILABLE 2.

**D4**: 120 cases, eligible pool 500, seed 20261021. Status counts: AVAILABLE 103, EMPTY 2, PSEUDO_VERSION_UNRESOLVED 1, TRUNCATED 14. Explored 120/500 eligible (pool not exhausted) before the stop condition fired. Cases with >100 candidates: 38 (target 25).

**Candidate-set size distribution (D4, n=120)**: ≤10: 34, 11-100: 48, >100: 38. Gold-not-in-candidates (ceiling limit): 20/120.

**E0 (D1, core symbols, n=150/144 scored)**: precision 0.584 [0.524, 0.642], recall 0.845 [0.788, 0.900], f1 0.631 [0.573, 0.684]; exact match 46 (31%), any-hit 130 (87%), abstained 6 (4%). Against core∪derived: precision 0.605, recall 0.478, f1 0.440. Split at 2026-06-30: pre-cutoff f1 0.653 (n=61), post-cutoff f1 0.615 (n=89).

**B-ID (D4, core symbols, n=120)**: precision 0.490 [0.392, 0.594], recall 0.295 [0.215, 0.378], f1 0.193 [0.136, 0.256]; exact match 6 (5%), any-hit 36 (30%), abstained 80 (67%, no commit named the advisory). Split at 2026-06-30: pre-cutoff f1 0.211 (n=33), post-cutoff f1 0.186 (n=87).

**Ceiling investigation**: 119 cases checked, 31 with a missing core symbol. EXISTS_UNCHANGED 57, NOT_FOUND_EITHER_VERSION 4, MATCHING_PROBLEM 0, OTHER 0. Example: `GO-2022-0588` / `Policy.AllowElements` / EXISTS_UNCHANGED.

**Comparison with feasibility trials**: E0 recall 0.84 here vs. trial 2's 0.91 (n=150 vs 59); E0 precision 0.58 vs 0.70; cases with ≥100 changed functions 38/120 (32%) vs trial 5's 12/45 (27%); core symbols outside the candidate set 31/119 (26%) vs trial 5's 10/42 (24%). Differences attributed to the larger, differently-sampled case set, a later vulndb pin, and name-level symbol matching throughout (trial 2's own documented convention).

## 7. Design deviations

- **`VulnCase.modules` is a list**, not DATA_MODEL.md's single-module example — real advisories commonly affect several modules (sub-modules, major-version splits); generalizing was necessary to represent them at all.
- **Symbol matching is name-level**, not full-package-path, throughout (report parsing, baselines, ceiling investigation) — following feasibility trial 2's own validated precedent, which found a strict path matcher undercounts on `/vN` suffixes.
- **`touches_candidates` is file-level, not line-level** — avoids re-running the Go helper per intermediate commit across ranges with thousands of changed functions (feasibility trial 5 observed up to 2,558); documented as a simplification, not a correctness claim about per-commit attribution.
- **Pseudo-version resolution fetches by `--shallow-since` across all branches**, not by the embedded abbreviated hash directly — git's wire protocol will not fetch an unadvertised object by an abbreviated SHA, and at least one real case (`jwt-go`/v4) has its `vulnerable_at` commit only on a non-default branch.
- **Tag-naming tries the repo-root convention before the `vN/` subdirectory convention** for major version 2+, and resolves a sub-module's path prefix from the case's own fix-commit repository rather than the vulndb module path alone — vulndb's module path does not say where the repository root is for vanity import paths; this is a documented limitation, not a general solution.
- **Task 0c's prefix rule covers bare generic functions only**, not generic methods or methods on generic types — the binary symbol for those embeds the type argument inside the receiver's own brackets and is still shape-specific (`go.shape.string`, never the concrete type vulndb names), so no reliable rule was found; they remain `UNSUPPORTED_SYMBOL_FORM`, as specified for the "if no reliable rule exists" branch of the task.
- **vulndb data committed is narrower than its CC-BY-4.0 licence allows**: only advisory IDs, created dates, candidate counts and statuses are committed, never report text — a deliberate choice to keep `docs/results/` small and avoid redistributing advisory summaries as a standalone dataset, not a licence requirement.
- **`CONTAMINATION_CUTOFF = "2026-06-30"`** is an explicit placeholder (documented in `datasets.py` and the results doc) pending a real model training-cutoff date in CP5, per the checkpoint spec's own instruction.

## 8. Blockers and limitations

- **The D4 build was attempted three times.** The first (killed at ~70/500) and second (crashed at ~126/500, then killed again at 47/500 after restart) each surfaced a real bug that was fixed and committed before the next attempt, rather than trusting partial or buggy output:
  1. `d12c28a`: a TRUNCATED release range still carries a real (sometimes very large) candidate list from its two-tree diff, but `build_d4_case_list` only counted `AVAILABLE` cases toward "large" — undercounting exactly the cases this exploration exists to find.
  2. `c96d904`: an unhandled `subprocess.TimeoutExpired` from a slow `git fetch --depth=501` on a large active repository crashed the whole build; fixed by making `git_fetch.run_git` catch timeouts everywhere (5 call sites were exposed, not just the one that happened to trigger it).
  3. `48aec8a`: found by re-reading the code, not a test failure — the exploration order was supposed to explore forced (post-cutoff) cases first and shuffle the rest, but `stratified_sample`'s own "pool fits within target" short-circuit silently returned the pool sorted by id, unshuffled, so forced cases were not actually guaranteed early exploration. Fixed and regression-tested before the third (successful) attempt.
  This delayed D5/D6/D7/D9 well past the first attempt but did not reduce their scope — the real, final D4 run used both fixes.
- **`eligible_for_d1`/`eligible_for_d4`'s `CONTAMINATION_CUTOFF` placeholder puts a large share of both D1 and D4 in the forced (post-cutoff) bucket** (89/150 of D1, 87/120 of D4) — because the pinned vulndb snapshot (2026-10-21) has many advisories created after 2026-06-30. This is a real property of the data, confirmed by comparing the two datasets' forced fractions against each other, not a bug, but it means the "non-forced, stratified-by-year" part of the sample is a minority of each dataset until CP5 picks a real cutoff.
- **Ceiling investigation's "exists unchanged" classification is a `git grep -w` name-existence check**, not a precise parse — documented in `ceiling.py`'s own module docstring as a reasonable approximation for an exploratory question, not a validated classifier.

## 9. Suggestions for the next checkpoint

- CP5 should replace `CONTAMINATION_CUTOFF` with the real training-cutoff date of whichever model is chosen, then re-split and re-report D1/D4 rather than relying on the CP3 placeholder split.
- The `module_subdir` vanity-import limitation (tag resolution assumes the fix-commit repository is the module's real repository) is worth revisiting if CP4/CP5 need release ranges for modules this didn't cover well.
- Consider whether `touches_candidates`' file-level granularity is precise enough once CP5's root-cause selection needs to reason about individual commits within a large range, or whether it's worth the cost of per-commit helper calls at that point.

## 10. Git

Branch: `claude/lucid-fermi-9esjyw`.

Commits this checkpoint (`a181a2f`..HEAD, oldest first):

```
a181a2f CP3: set IN_PROGRESS on claude/lucid-fermi-9esjyw; record env check and vulndb pin
33b9bf2 CP3 task 0a: package-not-in-program is NO_PATH, not TARGET_NOT_FOUND
f4b7028 CP3 task 0a: regenerate CP2 results after the contract change
154973c CP3 task 0b: add GitHub Actions CI workflow
6f20b56 CP3 task 0c: linker method matches bare generic functions by prefix
a6c4df0 CP3: tick task 0c in STATUS.md checklist
25b651d CP3 task 0c: regenerate CP2 results after the generic-symbol linker fix
33348e3 CP3 task 0c: regenerate CP1 results after the generic-symbol linker fix
0cc37ec CP3 D1: pin golang/vulndb snapshot, add Go version parsing and fetch helpers
60b236d CP3 D2: report reader - golang/vulndb report YAML to VulnCase
8dba802 CP3 D3: Mode 1 FixEvidence extraction from GitHub fix commits
368949d CP3 D4: Mode 2 ReleaseRange extraction between module versions
7eaf67d CP3 D5/D6/D7: dataset construction, E0/B-ID baselines, metrics, ceiling investigation
d12c28a CP3 D5: count a truncated-but-large D4 case as large
4ae312f CP3: update README with D1-D4 commands; update STATUS.md handoff notes
c96d904 CP3: fix unhandled git-subprocess timeout that crashed the D4 build
48aec8a CP3 D5: fix D4 exploration order to guarantee forced-case coverage
c695235 CP3: update STATUS.md handoff notes for third D4 build attempt
30b37dc CP3 D5: build and commit D4 (release-range) dataset
0fe7171 CP3 D6/D7/D9: score B-ID baseline, run ceiling investigation, render results doc
```

All 20 commits pushed successfully to `origin/claude/lucid-fermi-9esjyw` (verified after each push in this session; no push failed).
