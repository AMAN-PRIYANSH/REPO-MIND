# CP7 report - End-to-end triage and evidence verifier

State: **`AWAITING_REVIEW`**. Session: Claude Code cloud session on `claude/vulntrace-ai-build-exhh01` (fresh from `main` at `eb4d996`; no earlier CP7 branch existed), 26 Oct 2026.

**Summary.** `python -m vulntrace triage` works end to end in Mode 1, Mode 2 and with given targets. On the 22 fixtures it has **0 false NOT_REACHABLE in every mode**, and the verifier rejected **0 correct outputs and 36 of 36 corrupted paths**. On real modules (D1, D4) most cases end in CANT_DETERMINE, mostly because the module is a library with no `main` package, or because its `go.mod` needs Go ≥ 1.25 while this environment (and CI) has 1.24.7. These are distributions, not accuracy. **Mode 2 NOT_REACHABLE policy: DOWNGRADE**, decided by a rule fixed in code before the results. D4 produced only 5 raw Mode 2 NOT_REACHABLE verdicts, and the rule needs at least 20.

The real runs found **four defects in the analysis that the fixtures did not show**. All four are fixed, tested, and everything was re-run afterwards:

1. The linker method was blind to generic functions written in vulndb form.
2. The linker method was blind to symbols of the main package (named `main.` in the binary).
3. The verifier wrongly rejected wrappers of promoted methods.
4. The verifier wrongly rejected symbols that exist only in build-constraint-excluded files.

Defects 1 and 2 could have produced an unguarded false NOT_REACHABLE.

## 1. Environment

| Item | Printed value |
|---|---|
| OS | `Linux vm 6.18.44-fc-v153 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux`, `PRETTY_NAME="Ubuntu 24.04.5 LTS"` |
| Python | `Python 3.13.17` (project-local `.venv`, `pip install -e ".[dev,db,agent]"`; nothing installed system-wide) |
| Go | `go version go1.24.7 linux/amd64` (`/usr/local/go/bin/go`); `golang.org/x/tools` v0.42.0 (helper) |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.9.2, build a82e528` (not used) |
| `vulntrace doctor` | `python: 3.13.17`, `go env GOOS GOARCH: linux amd64`, `go tool nm: runs`, `all CP1 prerequisites present` |
| Network | proxy.golang.org 200 (`helper fetch`, `go mod tidy` worked); pypi.org 200; `git ls-remote https://github.com/golang/vulndb HEAD` -> `e0bad562...` (= the pinned commit); github.com cloning worked (`dataset materialize`). **huggingface.co: `CONNECT tunnel failed, response 403`**; download.pytorch.org: 403; go.googlesource.com: 403 (not needed, vulndb is pinned to GitHub). |
| Evidence rebuild | `dataset materialize --set d1`: 150 cases, status counts AVAILABLE 146 / EMPTY 4 = the committed list. `--set d4`: "120 cases in 1875.6s ... 0 case(s) differ". |

No model was called anywhere in this checkpoint (no LLM; the embedding model could not be loaded, see deviation 1).

## 2. Files changed (vs `origin/main`)

| File | Purpose |
|---|---|
| `src/vulntrace/pipeline/__init__.py` | package docstring (stages; no LLM, no agent) |
| `src/vulntrace/pipeline/triage.py` | `run_triage`: mode choice, symbols, lifting, methods, verifier, policy, output (coverage, toolchain, limitations, timing) |
| `src/vulntrace/pipeline/symbols.py` | Mode 1 (every changed non-test function, `context_only` flag), Mode 2 top-k, import paths, not-covered records |
| `src/vulntrace/pipeline/analyse.py` | linker + VTA per (symbol, main package), rule table per entry, per-main facts, build timeout |
| `src/vulntrace/pipeline/aggregate.py` | case aggregation, Mode 2 policy, `assert_downgrade_only` guard |
| `src/vulntrace/pipeline/app.py` | app facts: module path, git commit/dirty, main packages via `go list` |
| `src/vulntrace/pipeline/retrieve.py` | fixed retriever (hybrid:bge-small, code+commits, k=10), offline model load, recorded BM25 fallback |
| `src/vulntrace/pipeline/inputs.py` | advisory (vulndb snapshot or file) and evidence loading from `data/` |
| `src/vulntrace/pipeline/cli.py` | `triage` command, default runners |
| `src/vulntrace/verifier/__init__.py` | package docstring (downgrade-only) |
| `src/vulntrace/verifier/checks.py` | pure checks: path structure, call sites, synthetic edges, symbol forms |
| `src/vulntrace/verifier/verify.py` | `verify`: TARGET_EXISTS, CALL_SITE, EDGE_EXISTS, PATH_STRUCTURE, REACHABLE_HAS_PATH; `go list` locator; helper `funcs`/`edges` |
| `src/vulntrace/verifier/sources.py` | reading files at the recorded commit (git) or from the analysed tree, `$GOROOT`, module cache |
| `src/vulntrace/methods/linker.py` | generic-instance matching for vulndb-form symbols; `main.` names for targets in the built main package |
| `src/vulntrace/verdict.py` | CP7 reason-code constants; docstring |
| `src/vulntrace/__main__.py` | `triage`, `eval triage`, `results render --doc cp7` |
| `src/vulntrace/eval/triage_eval.py` | evaluation: fixtures (3 modes, stability, corruption probe), D1/D4 (reference, stability, disk guard, load causes), Mode 2 policy rule |
| `src/vulntrace/eval/triage_fixtures.py` | synthetic fixture advisories (local git repo, fix commits, decoy) through the CP3 evidence builders |
| `src/vulntrace/eval/triage_cli.py` | `eval triage` command; writes `docs/results/cp7/` (paths sanitised, size-checked) |
| `src/vulntrace/eval/triage_report.py` | renderer of `docs/results/CP7_TRIAGE_RESULTS.md` (headline fixed before results) |
| `src/vulntrace/eval/results_doc.py` | dispatch for `cp7` |
| `schemas/verdict.schema.json` | optional properties and enum values only (CP2 verdicts still validate) |
| `tests/unit/cp7_support.py` | fakes for methods, verifier context, evidence |
| `tests/unit/test_cp7_aggregate.py` | aggregation, policy, guard, exhaustive monotonicity |
| `tests/unit/test_cp7_symbols.py` | Mode 1/Mode 2 symbol selection, import paths, context-only |
| `tests/unit/test_cp7_verifier_checks.py` | structure, call-site and synthetic-edge rules |
| `tests/unit/test_cp7_verifier.py` | corrupted paths rejected; exhaustive and random "never stronger"; locator classes |
| `tests/unit/test_cp7_triage.py` | pipeline with fakes: modes, all changed functions, failures as results, Mode 2, lifting, no LLM imports |
| `tests/unit/test_cp7_linker_generics.py` | generic-instance and main-package linker matching |
| `tests/unit/test_cp7_eval.py` | policy rule, Wilson, memo, corruptions, disk guard, load causes, headline pinned, doc = render |
| `tests/unit/test_cp6_notebook.py` | stale test repointed at the frozen CP6 report (task 0) |
| `tests/contract/record_cp7_verdicts.py` | recorder of real pipeline outputs (needs Go; run by hand) |
| `tests/contract/verdicts_cp7/*.json` | 14 recorded verdicts (3 verdicts, all 10 reason codes) + index |
| `tests/contract/test_cp7_verdict_contract.py` | schema, invariants, coverage of every reason code, CP2 backward compatibility |
| `tests/integration/test_cp7_triage.py` | CLI, three modes on fixtures, real verifier on corrupted paths, generics and main-package targets on real binaries, determinism |
| `docs/results/cp7/{fixtures,d1,d4,mode2_policy}.json` | results (each < 512 KiB) |
| `docs/results/cp7/examples/{d1_GO-2020-0023,d4_GO-2022-0400}.verdict.json` | one real verdict per dataset (no code text) |
| `docs/results/CP7_TRIAGE_RESULTS.md` | results document, generated by code |
| `docs/design/INTERFACES_AND_CONTRACTS.md` | triage CLI options, `eval triage`, verifier implementation, policy default |
| `docs/design/DATA_MODEL.md` | Verdict extension |
| `docs/architecture/SYSTEM_ARCHITECTURE.md` | rule as implemented; Mode 2 policy decision |
| `docs/progress/STATUS.md`, this report | progress |

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Pipeline `src/vulntrace/pipeline/` + `triage` | **Done.** Lifting is implemented, off by default and non-deciding (deviation 8). |
| 2 | Evidence verifier `src/vulntrace/verifier/` | **Done.** Downgrade-only, guarded in code and by tests; corrupted paths rejected. |
| 3 | Verdict schema extension + contract tests | **Done.** 14 recordings cover every verdict and every reason code. |
| 4 | Evaluation `eval triage`, results in `docs/results/cp7/` and `CP7_TRIAGE_RESULTS.md` | **Done.** The Mode 2 retriever ran in its BM25 fallback (deviation 1). |
| 5 | Tests; CI green; no network or model by default | **Done.** See section 4; CI on the last commit is checked in section 10. |

## 4. Test evidence

All run in this session on the final code (after `2eb9a7b`):

| Command | Printed summary |
|---|---|
| `python -m pytest tests/unit tests/contract -q` | `763 passed, 10 skipped in 15.09s` (the 10 skips are the pgvector tests: no database here; CI runs them) |
| `python -m pytest tests/integration -q` | `134 passed, 2 skipped in 266.05s (0:04:26)` (the 2 skips are the opt-in network smoke tests) |
| `go test ./...` in `helper/` (`GOTOOLCHAIN=local CGO_ENABLED=0`) | `ok  	vulntrace/helper	6.413s` (`go test -count=1 ./...`) |
| `python -m pytest tests/integration/test_cp7_triage.py tests/integration/test_linker_fixtures.py tests/integration/test_callgraph_fixtures.py -q` (after the main-package fix) | `38 passed in 267.41s (0:04:27)` |
| `python -m vulntrace eval triage --set fixtures` | `wrote .../docs/results/cp7/fixtures.json (111430 bytes)`; repo commit `ed46380`, dirty False |
| `python -m vulntrace eval triage --set d1 --jobs 2 --rerun --stability 10 --example GO-2020-0023` | `wrote .../docs/results/cp7/d1.json (249636 bytes)`; commit `2eb9a7b`, dirty False |
| `python -m vulntrace eval triage --set d4 --jobs 2 --rerun --stability 10 --gomodcache ~/.cache/vulntrace/gomod-d4` | `wrote .../docs/results/cp7/d4.json (225142 bytes)`; commit `2eb9a7b`, dirty False |
| `python -m vulntrace fixtures score --method combined` | `agreements 18, cant_determine 4, false_not_reachable 0, false_reachable 0` - identical to the CP7 TARGETS mode on all 22 cases |
| Mutation check: verifier downgrade disabled / Mode 2 policy disabled | `11 failed, 41 passed` / `2 failed, 45 passed` (the tests catch both); sources restored from git |

Before the fix in task 0, `pytest tests/unit tests/contract` on `main` printed `1 failed, 620 passed, 10 skipped` (`test_cp6_notebook.py::test_branch_is_this_checkpoints_branch`); CI run 99 (this branch's first commit) is red for the same reason.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `triage` works for Mode 1 and Mode 2 on fixtures and on at least one D1 and one D4 case with real evidence | **Met** | Fixtures: 22 cases x 3 modes (`fixtures.json`); D1: 143 runs, 38 REACHABLE; D4: 120 runs, 32 REACHABLE; examples `examples/d1_GO-2020-0023.verdict.json` (Mode 1, REACHABLE, verified path) and `examples/d4_GO-2022-0400.verdict.json` (Mode 2, REACHABLE, CANDIDATE_LEVEL); CLI integration test `test_cli_prints_one_verdict` |
| 2 | Mode 1 analyses all changed non-test functions; no LLM selection or agent in the verdict path | **Met** | `symbols.mode1_symbols`; `test_mode1_sends_every_changed_function_to_both_methods`; `test_no_llm_or_agent_on_the_verdict_path` (static import check of `pipeline/` and `verifier/`) |
| 3 | Two-method agreement rule applied; every REACHABLE has a verified path; Mode 2 results carry rank and CANDIDATE_LEVEL | **Met** | `test_two_method_agreement` (5 rows), `test_reachable_has_a_verified_path`, contract `test_reachable_entries_carry_a_verified_path`; "REACHABLE without verified path: 0" in fixtures, D1 and D4; `test_mode2_reachable_is_candidate_level_with_rank_and_score` (unit and contract); the schema requires `evidence_level = CANDIDATE_LEVEL` for a Mode 2 REACHABLE |
| 4 | Verifier downgrade-only, proven by tests including corrupted paths | **Met** | `test_wrong_line_is_rejected`, `test_missing_edge_is_rejected`, `test_fabricated_hop_is_rejected`, `test_real_verifier_rejects_corrupted_paths` (real helper); `test_exhaustive_never_stronger` (all 150 one-entry combinations of result x target outcome x path outcome x package flag, and 3000 sampled two-entry combinations), `test_random_inputs_never_stronger` (400 random verdicts); `assert_downgrade_only` runs on every pipeline output; fixture probe 36/36 rejected |
| 5 | Fixture evaluation: accuracy, REACHABLE precision, false NOT_REACHABLE count, verifier rejections | **Met** | Section 6 |
| 6 | D1/D4 distribution and coverage with CANT_DETERMINE reasons, stated as not accuracy | **Met** | Section 6; the results document says so in each D1/D4 section |
| 7 | Mode 2 NOT_REACHABLE policy decided from numbers, stated in report and docs | **Met** | Section 6; `mode2_policy.json`; `SYSTEM_ARCHITECTURE.md` and `INTERFACES_AND_CONTRACTS.md` |
| 8 | No analysed code executed; toolchain flags used; no `data/`, caches or third-party source committed | **Met** | Every `go` call uses `go_env()` (`GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY=off`; `go mod tidy` uses the proxy explicitly), recorded in every verdict's `toolchain.env`. Builds are only read with `go tool nm` and deleted; no `go generate`, no tests, no binaries run. `git ls-files` lists 454 files; none under `data/`, no `.gz`, no binaries or module caches; committed verdicts hold symbols, file paths and line numbers, no code text |
| 9 | All tests pass locally and in CI; report; STATUS AWAITING_REVIEW | **Met** (CI on the last commit: section 10) | Section 4 |

## 6. Results

All numbers below are copied from `docs/results/CP7_TRIAGE_RESULTS.md`, which `results render --doc cp7` generates from `docs/results/cp7/*.json`. The headline sentence was fixed in `eval/triage_report.py` (commit `5933c51`) before any result existed, and was not changed.

### Fixtures (D2, truth by construction)

| mode | false NOT_REACHABLE (final) | false NOT_REACHABLE (before policy) | false REACHABLE | CANT_DETERMINE | accuracy | coverage (answered) | selective accuracy | REACHABLE precision | verifier rejections on correct outputs | verifier downgrades (all) | verified paths | REACHABLE without verified path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TARGETS (the case's own target symbol) | 0 | 0 | 0 | 4 | 0.818 [0.615, 0.927] (18/22) | 0.818 [0.615, 0.927] (18/22) | 1.000 [0.824, 1.000] (18/18) | 1.000 [0.758, 1.000] (12/12) | 0 | 0 | 12 | 0 |
| FIX (Mode 1, synthetic fix commit) | 0 | 0 | 0 | 4 | 0.818 [0.615, 0.927] (18/22) | 0.818 [0.615, 0.927] (18/22) | 1.000 [0.824, 1.000] (18/18) | 1.000 [0.758, 1.000] (12/12) | 0 | 0 | 12 | 0 |
| RELEASE (Mode 2, synthetic release range) | 0 | 0 | 4 | 6 | 0.545 [0.347, 0.731] (12/22) | 0.727 [0.518, 0.868] (16/22) | 0.750 [0.505, 0.898] (12/16) | 0.750 [0.505, 0.898] (12/16) | 0 | 0 | 17 | 0 |

| corruption | paths | rejected (CANT_DETERMINE / VERIFIER_REJECTED) |
|---|---|---|
| BROKEN_CHAIN | 12 | 12 |
| EDGE_NOT_IN_GRAPH | 12 | 12 |
| WRONG_LINE | 12 | 12 |

Determinism: the 22 TARGETS runs were repeated without the method cache; 0 differed.

How to read the fixture results:

- The 4 CANT_DETERMINE in TARGETS and FIX are the CP2 disagreement cases: `reflect_method`, `unsafe_func_pointer`, `present_but_unreachable`, `closure_never_called` (METHOD_DISAGREEMENT). TARGETS reproduces CP2's `combined` scorer exactly.
- RELEASE's 4 false REACHABLE (`safe_only`, `dead_code`, `test_file_only`, `closure_never_called`) are the decoy `vulnlib.Safe` being reachable. That is the CANDIDATE_LEVEL caveat, measured on purpose.
- The 3 RELEASE raw NOT_REACHABLE (`interface_not_instantiated`, `build_tag_excluded`, `interface_two_impls_one_used`) are correct but are downgraded by the policy, which is the price of the policy.
- In the first fixture run, `generic_target` was CANT_DETERMINE in FIX mode (defect 1). It is REACHABLE in every mode after the fix.

### D1 and D4 (distributions only; the module under study is the app)

| | D1 (Mode 1) | D4 (Mode 2) |
|---|---|---|
| cases | 150 | 120 |
| tree preparation | READY 87, PREP_FAILED 56, NO_MODULE 7 | READY 69, PREP_FAILED 51 |
| run through the pipeline | 143 | 120 |
| verdict before policy | REACHABLE 38, NOT_REACHABLE 3, CANT_DETERMINE 102 | REACHABLE 32, NOT_REACHABLE 5, CANT_DETERMINE 83 |
| verdict final | REACHABLE 38, NOT_REACHABLE 3, CANT_DETERMINE 102 | REACHABLE 32, NOT_REACHABLE 0, CANT_DETERMINE 88 |
| CANT_DETERMINE reasons (final) | APP_LOAD_FAILED 65, UNSUPPORTED_TARGET 26, ANALYSIS_FAILED 13, INCOMPLETE_COVERAGE 6, NO_FIX_EVIDENCE 4, METHOD_DISAGREEMENT 1, VERIFIER_REJECTED 1 | APP_LOAD_FAILED 55, UNSUPPORTED_TARGET 22, ANALYSIS_FAILED 7, MODE2_NOT_REACHABLE_DOWNGRADED 5, INCOMPLETE_COVERAGE 2, NO_RELEASE_EVIDENCE 2 |
| APP_LOAD_FAILED by cause | GO_VERSION_TOO_OLD 58, MISSING_DEPENDENCY 4, GOPATH_STYLE_IMPORT 1, TYPE_ERRORS 1, VENDOR_INCONSISTENT 1 | GO_VERSION_TOO_OLD 52, MISSING_DEPENDENCY 2, TYPE_ERRORS 1 |
| method pairs (VTA + linker) | NO_PATH+ABSENT 888, ERROR+ERROR 308, PATH_FOUND+PRESENT 279, NO_PATH+PRESENT 30, PATH_FOUND+ERROR 2, ERROR+PRESENT 1 | NO_PATH+ABSENT 369, PATH_FOUND+PRESENT 284, ERROR+ERROR 68, NO_PATH+PRESENT 20, ERROR+PRESENT 5 |
| verifier | 12874 checks; 4 entries downgraded in 1 case (TARGET_EXISTS) | 11225 checks; 0 downgraded |
| curated reference (pipeline / reference) | CD/CD 102, NR/NR 3, R/CD 3, R/R 35 | CD/CD 82, CD/R 1, NR/NR 5, R/CD 2, R/R 30 |
| not analysed | ADDED_BY_FIX 340; context-only Mode 1 symbols 189 of 910 analysed | BEYOND_TOP_K 40838, ADDED_BY_FIX 243, OUTSIDE_MODULE 2 |
| seconds per case (prep + triage + reference) | p50 4.2, p95 173.1, max 562.2 | p50 5.2, p95 275.5, max 969.1 |
| fallbacks | Mode 1 -> 2: 0; synthesised go.mod 12; vendor set aside 4; mains over limit 16 | retriever EMBEDDER_UNAVAILABLE 118 (BM25); synthesised go.mod 2; vendor set aside 2; mains over limit 11 |
| stability (10 cases re-run from scratch) | 0 differed | 0 differed |

D4 clustering: the 9-case rclone pseudo-replicate cluster (`github.com/rclone/rclone@1.74.4..1.75.0`) is entirely APP_LOAD_FAILED (Go version), so excluding it leaves REACHABLE 32 and NOT_REACHABLE 5 (before policy) unchanged, over 111 cases. The share REACHABLE before policy, with a cluster bootstrap, is 0.267 [0.171, 0.376] over 120 cases in 94 clusters.

What this says, with the limits stated:

- **Coverage is the main problem on real code.** 58 of 150 D1 and 52 of 120 D4 cases fail because `go.mod` requires a Go newer than 1.24.7 (`GOTOOLCHAIN=local`), and 26/22 are libraries with no `main` package (module-as-app has no entry point). Of the D1 cases that load and have a `main` package, the pipeline answers in 41: 38 REACHABLE and 3 NOT_REACHABLE.
- **The two methods rarely disagree** (open question Q3). Derived from the method-pair counts above: among entries where both methods answered, NO_PATH+PRESENT is 30 of 1197 in D1 (2.5%) and 20 of 673 in D4 (3.0%). PATH_FOUND+ABSENT is 0 in both since the main-package fix (it was 13 and 7, all caused by defect 2). At case level, METHOD_DISAGREEMENT decides only 1 D1 case, because a REACHABLE entry elsewhere in the case decides first.
- **The curated reference never contradicts a NOT_REACHABLE** (D1 3/3, D4 5/5 agree). The pipeline's REACHABLE agrees with a REACHABLE reference in 35/38 (D1) and 30/32 (D4); the rest have a CANT_DETERMINE reference, all METHOD_DISAGREEMENT on the curated symbols in D1. This is consistency with our own analysis of the curated symbols, **not** correctness.
- **Mode 2 REACHABLE is candidate-level.** In 21 of the 32 D4 REACHABLE cases a curated core symbol is among the analysed top-10; in 11 it is not, so REACHABLE there says nothing about the vulnerable function. The best reachable candidate's rank is 1 in 21 cases, 2 in 8, and 3, 8 or 9 in one case each.
- **The verifier caught a real evidence problem in D1** (GO-2024-3005, moby). The advisory has 10 backport fix commits; `isAuthEndpoint`/`isChunked` are new in most of them and only "changed" in one. Mode 1 analyses the tree at the first commit's parent, where they do not exist. VTA/linker said NO_PATH/ABSENT, and the verifier refused a NOT_REACHABLE for functions that do not exist there.

### Mode 2 NOT_REACHABLE policy (decided by code)

Rule (fixed in `eval/triage_eval.py` before results): keep only if (1) fixtures Mode 2 raw false NOT_REACHABLE = 0, (2) at least 20 raw Mode 2 NOT_REACHABLE on D4, (3) none contradicted by the curated reference, (4) 95% Wilson upper bound of the share without a curated core symbol among the analysed candidates ≤ 0.05.

Inputs: (1) 0 of 22, pass; (2) 5, **FAIL**; (3) 0 contradicted, pass; (4) 0/5, upper bound 0.434, **FAIL**. **Decision: DOWNGRADE** (default `--mode2-policy DOWNGRADE`). The 5 raw NOT_REACHABLE were all consistent with the reference, which is encouraging but far too few to justify keeping them.

## 7. Design deviations

1. **Mode 2 ranked with BM25, not `hybrid:bge-small`, in every run of this session.** huggingface.co is refused by the egress proxy (403) and `sentence-transformers` is not installed, so the fixed retriever's embedder cannot load. The pipeline falls back to the fixed retriever's own `secondary_config` (`bm25`) and records `fallback: EMBEDDER_UNAVAILABLE` with the error in every Mode 2 verdict (118 of 120 D4 runs; the other 2 had no release evidence). CP4 found BM25, dense and hybrid statistically indistinguishable, so this is the documented second choice, not a new retriever. On fixtures it cannot change a verdict (2 candidates, k = 10). On D4 it can change which 10 candidates are analysed. The default stays `hybrid:bge-small`, loaded offline; `--retriever` overrides.
2. **Two fixes to the existing linker method**, because the spec says "use the existing methods" but both defects affect the CP7 verdict path. `symbol_patterns` and the CP1/CP3 tests are unchanged.
   - (a) vulndb and FixEvidence name generic functions without type parameters. A bracket-balanced rule now matches `pkg.F[...]`, `pkg.T[...].M` and `pkg.(*T[...]).M` (observed with Go 1.24.7, tested on a real binary).
   - (b) Go names every symbol of the main package `main.` in the binary. A target in the built main package now uses those names; a target in another main package keeps its import path.
   - Both defects made the linker answer ABSENT for reachable code, so a VTA miss there would have read as NOT_REACHABLE without the linker guard.
3. **Mode 1 keeps CP3's context-line attribution.** CP3 attributes a hunk to every function its span overlaps, including git's 3 context lines. The spec says Mode 1 is the E0 behaviour, so all candidates are kept and flagged `context_only`: 189 of 910 analysed D1 symbols. Changing CP3 would change committed CP3/CP5 results.
4. **One entry per (symbol, main package).** A VTA path from one main package and linker presence in another binary would not be agreement. At most 10 main packages by default (5 in the evaluation, for cost); more makes coverage incomplete (`INCOMPLETE_COVERAGE`: REACHABLE is possible, NOT_REACHABLE is not).
5. **Schema additions:**
   - reason codes `APP_LOAD_FAILED`, `NO_RELEASE_EVIDENCE`, `INCOMPLETE_COVERAGE`, `MODE2_NOT_REACHABLE_DOWNGRADED`;
   - `evidence_level` also labels Mode 1 (`CHANGED_FUNCTION_LEVEL`), because a reachable changed function need not be the root cause either;
   - origins `FIX_CHANGED`, `RANKED_CANDIDATE`, `USER`.
6. **Functions only added by the fix (side NEW) are not analysed:** they did not exist in the vulnerable version. They are listed as `ADDED_BY_FIX`, never dropped silently.
7. **`auto` falls back from Mode 1 to Mode 2** when the fix evidence is unusable and a release range exists (`FIX_EVIDENCE_UNUSABLE_FALLBACK_TO_RELEASE`). This happened 0 times in the evaluation: D1 runs `auto` and every usable case had fix evidence; D4 requests Mode 2.
8. **Lifting is off by default and never decides.** With `--lift`, LIFTED symbols are analysed with `decides_verdict: false`, and only when the app is the vulnerable module itself (lifting walks that module's callers). Not run in the evaluation.
9. **The verifier checks NOT_REACHABLE entries too** (target existence), beyond the rule table's "n/a". A symbol declared only in files the build configuration excludes passes for NOT_REACHABLE and never for REACHABLE.
10. **Verifier rules corrected after real runs:**
    - promoted-method wrappers (`stream.Write$wrapper -> sendStream.Write`) were wrongly rejected: a forwarder now only needs a callee method of the same name;
    - build-constraint exclusions were wrongly rejected: `IgnoredGoFiles` and `go list -m -e` are now used.

    Every D1/D4 result committed was produced after these fixes (commit `2eb9a7b`). Earlier partial runs were discarded.
11. **Fixture advisories are synthetic** (`eval/triage_fixtures.py`): a throw-away git repository from a copy of the fixtures, one fix commit per target, one decoy commit (`vulnlib.Safe`) per release range. Nothing in `fixtures/` and no truth label changed.
12. **The evaluation runs the pipeline on trees whose preparation failed**, so that the pipeline itself answers CANT_DETERMINE (APP_LOAD_FAILED). It does not run on cases with no tree (NO_SOURCE/NO_MODULE): there is no app to triage, and those are counted under preparation.
13. **Task 0 (stale test).** `test_branch_is_this_checkpoints_branch` compared the CP6 notebook's branch with STATUS.md, which stopped naming it in the CP6 approval commit `eb4d996`, so `main` was red. It now checks the frozen CP6 report (commit `8b0e760`); the assertion is the same.

## 8. Blockers and limitations

- **Go version.** 58/150 D1 and 52/120 D4 modules need Go ≥ 1.25; with `GOTOOLCHAIN=local` and Go 1.24.7 they are `APP_LOAD_FAILED`. CP5b worked around this with go1.26.10 in scratch. I did not, so that CP7 matches CI. Raising coverage needs a newer Go in the environment, and probably a newer `x/tools` pin.
- **Module-as-app is a weak stand-in for applications.** Libraries have no `main` package (UNSUPPORTED_TARGET 26/22), and a module's own commands are not representative users. Real applications are CP7b (D3).
- **No embedding model** (deviation 1); the D4 candidate lists come from BM25.
- **D1/D4 have no reachability truth.** The curated reference is our own analysis of the curators' symbols; agreement is consistency, not accuracy.
- **Changed functions named `init`** cannot be looked up by the helper (user `init` functions are not in package scope): `TARGET_NOT_FOUND` -> CANT_DETERMINE (6 entries in 2 D4 cases). Safe, but lost coverage.
- **Multi-commit advisories** are analysed at the first fix commit's parent only (as CP5b did); symbols from other backports may not exist there. The verifier rejects any such NOT_REACHABLE (GO-2024-3005).
- **One build configuration** (linux/amd64, `CGO_ENABLED=0`, no tags), stated in every verdict.
- **The site check's residual ambiguity:** a top-level function and a method of the same name in one file are told apart by the exact-site `edges` check, not by the site check alone. Documented in `verifier/checks.py`.
- **Cost:** the D1 + D4 evaluation takes about 2 hours of wall time on 4 vCPUs. The module cache can exceed 10 GB; the disk guard emptied the run's Go caches 2-4 times per run (counted in `disk_guard`).
- **Windows** `nm` behaviour (open question Q1) was not checked; that needs the owner's laptop.

## 9. Suggestions for the next checkpoint

- CP7b: run on real applications with a Go ≥ 1.25 toolchain available (and re-pin `x/tools` if needed); re-decide the Mode 2 policy once there are at least 20 raw Mode 2 NOT_REACHABLE verdicts.
- Run the D4 evaluation once with `hybrid:bge-small` (Colab or a machine that can reach Hugging Face) to see whether the candidate lists change any verdict.
- Support `init` targets in the helper (map to the package's user `init` functions).
- For multi-commit advisories, analyse each fix commit's parent, or restrict symbols to the commit whose parent is analysed.
- Consider fixing CP3's context-line attribution in a separate, measured change (189 context-only symbols in D1 Mode 1).

## 10. Git

Branch `claude/vulntrace-ai-build-exhh01`. `git log --oneline origin/main..HEAD` (newest first):

```
b236fca CP7: D4 pseudo-replicate exclusion covers exactly the 9-case rclone cluster (was all 16 rclone cases); renderer recomputes summaries from rows; stored summaries refreshed by code
4c021e3 CP7: results document rendered from the final result files
f2315f6 CP7: final fixture evaluation from a clean tree; Mode 2 policy DOWNGRADE; contract recordings refreshed (synthetic SHAs, commit and timing fields only)
ed46380 CP7: final D1 (150) and D4 (120) triage results from commit 2eb9a7b (clean tree; stability 10/10 each); examples refreshed
6e5319d CP7: STATUS handoff notes (final D1/D4 re-run in progress)
2eb9a7b CP7: linker method sees targets inside the analysed main package
086cd7a CP7: results document CP7_TRIAGE_RESULTS.md (rendered by code; renderer presentation fixes only), test that it matches a fresh render; Mode 2 NOT_REACHABLE policy (DOWNGRADE) stated in the architecture and interface docs
eb2e9f1 CP7: final fixture evaluation (clean tree), Mode 2 policy decided by code (DOWNGRADE: 5 raw D4 NOT_REACHABLE, rule needs 20), contract recordings refreshed from the final code (only commit and timing fields changed)
c7383b4 CP7: final D1 (150) and D4 (120) triage results from commit 13d9c07 (clean tree), stability 10/10 each; example D1 and D4 verdicts
13d9c07 CP7: verifier existence check handles build-constraint exclusions
a45f80b CP7: eval triage runs the pipeline on trees whose preparation failed (the pipeline must say CANT_DETERMINE itself)
8c32e0a CP7: D1 triage results (150 cases, module under study as the app; distributions only) and one example verdict
9f2cc23 CP7: verifier accepts the synthetic wrapper of a method promoted through an embedded field
a23939a CP7: architecture doc - the verdict rule as implemented (per main package, verifier column, case-level codes, evidence levels)
7197f79 CP7: disk guard for eval triage (clean this run's Go caches when free disk is low, only while no case is in flight); per-run GOCACHE
ec0707c CP7: count APP_LOAD_FAILED cases by coarse cause (Go version, missing dependency, GOPATH-style import, cgo, vendoring, timeout, type errors)
2f8cfc4 CP7: eval triage --stability (re-run triaged D1/D4 cases from scratch and compare), eval helper tests, renderer mode order
1d2e8c6 CP7: interfaces (triage CLI, eval triage, verifier implementation) and data model (verdict extension) docs
15528e2 CP7: STATUS - deliverables 1-3 ticked, handoff notes
3169739 CP7: results files never carry local absolute paths (error messages are reduced to <local>)
73b9186 CP7: contract tests with recorded outputs for every verdict and reason code; integration tests (CLI, three modes on fixtures, real verifier on corrupted paths, generic symbols on a real binary)
0d9a4d6 CP7: linker method matches generic instantiations of vulndb-form targets
cabf701 CP7: unit tests - aggregation and guard, symbols, verifier checks, verifier (corrupted paths, exhaustive and random never-stronger), pipeline with fakes
5933c51 CP7: pipeline, evidence verifier, verdict schema extension, triage CLI, eval harness and renderer (headline fixed before results)
8b0e760 CP7 task 0: fix stale CP6 notebook test (red on main since the CP6 approval commit)
c8e5045 CP7: start - STATUS IN_PROGRESS, branch claude/vulntrace-ai-build-exhh01, task list
(plus the report and STATUS commit that adds this file)
```

Every push succeeded (`git push`, no errors). CI (GitHub Actions `CI`): run 99 on the first commit `c8e5045` failed (the pre-existing stale test, fixed in `8b0e760`); runs 100-120 succeeded. **Run 121 on `ed46380` failed**: that commit added the final D1/D4 result files before the results document was re-rendered, so `test_committed_results_document_is_generated_from_committed_files` (`1 failed, 763 passed, 9 skipped`) correctly reported a stale document. I committed it without running the unit tests first; the next commit `4c021e3` re-rendered the document (run 122: success), and `b236fca` succeeded (run 123). The CI result of the commit that adds this report is checked after pushing; see the final message of the session (STATUS records it if it is not green).
