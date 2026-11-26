# CP10 report - Verdict-level trust against govulncheck, target hygiene and honest evidence

Builder session: branch `claude/wizardly-hamilton-0ft7q0` (26 Nov 2026), started from `main` at `ac72891` (no earlier
CP10 branch existed). State at the end of this session: **`AWAITING_ADJUDICATION`**. Sections 4-6 and acceptance criteria
6 and 9 are completed by the scoring session after the supervisor fills `docs/results/cp10/adjudication/adjudication.json`.

**Summary of what was built and observed (no truth yet).**
Target hygiene, evidence labels and the D3c set are in code, tested, and were committed before any D3c probe or run (commit
order in section 10). `--legacy-targets` reproduces earlier checkpoints exactly: CP7 fixtures 66/66 rows, D3 14/14 and D3b
11/11 verdicts against the committed CP9 verdicts (entry level: verdict, reasons, every entry's result, reason, method
results and verified path). D3c was selected by code: **8 applications (the limit), 23 cases, stratum S 16, stratum N 7**.
**The N quota (8) was not met**: 28 of 57 candidates were evaluated before the 8-application limit was reached. On D3c the
hygiene changed **one** verdict (AdGuardHome GO-2026-6061, stratum S: legacy CANT_DETERMINE (VERIFIER_REJECTED) ->
NOT_REACHABLE); in stratum N it changed nothing. Whether any of this is *right* is not known until adjudication.

## 1. Environment

| Item | As printed |
|---|---|
| OS | `Linux vm 6.18.44-fc-v880 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux`, Ubuntu 24.04.5 LTS, 4 CPUs, 15 GiB RAM |
| Python | `Python 3.13.18`, project `.venv` (`pip install -e ".[dev,agent]"`); nothing installed system-wide |
| Go (system) | `go version go1.24.7 linux/amd64`: Go unit tests, unit/contract/integration tests, CP7 fixture reproduction (CP7's toolchain) |
| Go (D3, D3b, D3c) | `go version go1.26.10 linux/amd64`, `golang.org/toolchain@v0.0.1-go1.26.10.linux-amd64` downloaded with `go mod download` into the session scratchpad, sum `h1:5VAGHlY8yl8pTPVSNIez3SNMy6fWabs+QMR25f3oMT0=` (same as CP7b/CP9, checked by the checksum database), first on `PATH` |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.9.3, build 5457199` (not used) |
| govulncheck | `golang.org/x/vuln/cmd/govulncheck@v1.9.0` (as CP7b), built from the module proxy into the cache; database: pinned vulndb `e0bad56276e98711a598adbab976de7cd914013a`, `data/osv` |
| Network | `proxy.golang.org` 200; `git ls-remote https://github.com/golang/vulndb` OK; `pypi.org` 200; `go.dev`, `dl.google.com`, `huggingface.co` refused by the egress proxy (403) - not needed |

## 2. Files changed

Code
- `src/vulntrace/pipeline/symbols.py` - CP10 hygiene: `curated_symbols`, `stratum_of`, `hygiene_mode1_symbols`, policy/stratum constants.
- `src/vulntrace/pipeline/aggregate.py` - `hygiene_case_result` (stratum N rule: only REACHABLE -> CANT_DETERMINE).
- `src/vulntrace/pipeline/triage.py` - `TriageRequest.target_policy` (HYGIENE default, LEGACY), `target_policy` note, stratum-N re-aggregation after the verifier, `Runners.evidence`, limitations text.
- `src/vulntrace/pipeline/analyse.py` - entries carry `extra_reason`; `default_vta(label_dynamic=)`.
- `src/vulntrace/pipeline/evidence.py` (new) - evidence stage: shown route, `confirmed: false` and kind on DYNAMIC steps, `path_evidence`, `assert_labels_only`, `strip_cp10_evidence`, text output.
- `src/vulntrace/pipeline/feasibility.py` - `helper_settings(rank_evidence=)`.
- `src/vulntrace/pipeline/cli.py` - `triage --legacy-targets`, `--format json|text`; runners with `evidence`.
- `src/vulntrace/methods/callgraph.py` - `label_dynamic` request option.
- `src/vulntrace/verifier/verify.py` - checks the filter's ranked path, counted apart (`display_checks_by_kind`), `path_checks`; never changes a result.
- `src/vulntrace/verdict.py` - reason `ONLY_CONTEXT_TARGETS_REACHABLE`.
- `src/vulntrace/demo/page.py` - route caveat, "Route shown (an example from the call graph)", unconfirmed labels, extra-target column, target rules.
- `src/vulntrace/d3/select.py` - D3c: `advisory_index_strata`, `eligible_for_stratum_n`, `pick_cases_strata`, `select_d3c`; `evaluate_candidate(pick=)`; strata carried in cases (D3 path unchanged, tested).
- `src/vulntrace/d3/triage_run.py` - `target_policy` (default LEGACY), `set_name`.
- `src/vulntrace/eval/triage_eval.py` - CP7 runners pinned to LEGACY; `eval_fixtures(target_policy=)`; memo runners keep `evidence`.
- `src/vulntrace/cp10/{__init__,cli,run,sheet,score,report}.py` (new) - `cp10 select|run|sheet|report`.
- `src/vulntrace/__main__.py` - registers `cp10`.
- `helper/contract.go`, `graph.go`, `reach.go`, `feasible.go` - opt-in `label_dynamic` (edge `dynamic_kind`) and `feasibility.rank_evidence` (`dynamic_steps`, `rank_rule`, `ranked_path`, `ranked_index`); absent options give the CP9 output byte for byte.
- `helper/evidence_test.go` (new) - ranking, dynamic kinds, no-option output unchanged.
- `schemas/verdict.schema.json`, `helper_request.schema.json`, `helper_response.schema.json` - additive optional fields and enum values only.

Tests
- `tests/unit/test_cp10_hygiene.py`, `test_cp10_evidence.py`, `test_cp10_select.py`, `test_cp10_score.py` (new).
- `tests/contract/record_cp10.py`, `tests/contract/cp10/**` (new) - real recordings (helper, linker, verifier) for hygiene and evidence.
- `tests/contract/test_cp10_contract.py`, `test_cp10_committed.py` (new); `test_cp7_verdict_contract.py` - reason-code coverage includes the CP10 recordings.

Documents and results
- `docs/evaluation/D3C_SELECTION_RULES.md`, `docs/evaluation/d3c_candidates.json` (new) - written before any D3c probe.
- `docs/results/cp10/fixtures.json`, `d3/`, `d3b/`, `d3c/` (selection, cases, verdicts of both runs), `adjudication/` (sheets).
- `docs/results/CP10_VERDICT_RESULTS.md` - rendered by code; preview with the headline pending.
- `docs/progress/STATUS.md`, this report.

## 3. Deliverables

| # | Deliverable | State |
|---|---|---|
| 1 | Target hygiene in code before any D3c run; `--legacy-targets` reproduces CP7/CP9; hygiene-induced NOT_REACHABLE only possible in stratum S, listed | **Done** (adjudication of the listed cases pending) |
| 2 | Evidence honesty: ranking among the N examined paths, `confirmed: false` + kind, path evidence level, statement in JSON, text output and demo page | **Done** |
| 3 | D3c by code with strata, quotas, new seed, D3/D3b excluded; VulnTrace (hygiene and legacy) and govulncheck on every case | **Partly done**: run complete, but stratum N has 7 cases, below the quota of 8 (section 8) |
| 4 | Verdict-level sheets: every D3c case; truth-only items for the 7 D3 REACHABLE and the 4 D3b non-REACHABLE cases | **Done** (34 items); waiting for the supervisor |
| 5 | Scoring, `CP10_VERDICT_RESULTS.md` rendered by code, headline fixed before D3c results | **Partly done**: renderer and headline committed (`57e21e3`) before the D3c selection; scores need the filled sheet |
| 6 | Tests; CI green | **Done** for this session (section 4); CI to be re-checked on the last commit by the scoring session |

## 4. Test evidence (this session)

| Command | Printed summary |
|---|---|
| `python -m pytest tests/unit tests/contract -q` (start of session, baseline) | `929 passed, 10 skipped in 16.52s` |
| `python -m pytest tests/unit tests/contract -q` (last code commit) | `995 passed, 10 skipped in 32.17s` |
| `(cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 GOPROXY=off go test ./...)` | `ok  	vulntrace/helper	15.732s` |
| `python -m pytest tests/integration -q` (after task 1a) | `172 passed, 2 skipped in 295.59s (0:04:55)` |
| `python -m pytest tests/integration -q` (final code) | `172 passed, 2 skipped in 299.67s (0:04:59)` (run on `0c7e04a`, the last code commit) |
| `python tests/contract/record_cp10.py` (real helper) | every scenario's assertion held (verdict, reasons, stratum, evidence level) |
| `python -m vulntrace cp10 run --set fixtures` (go1.24.7) | `cp7_reproduction.identical: True`, 66 rows, 0 differences; hygiene changed 0 fixture rows |
| `python -m vulntrace cp10 run --set d3` / `--set d3b` (go1.26.10) | `cp9_reproduction`: 14/14 and 11/11 identical, `all_identical: True` |
| `python -m vulntrace triage --advisory-file ... --app fixtures/reachability --mode targets --target vtfixtures/vulnlib:Parse --main ./cmd/interface_dispatch --format text` | `FIXTURE-DEMO: REACHABLE`, `evidence level: HAS_DYNAMIC_STEPS (1 dynamic step(s): {'INTERFACE_METHOD': 1})`, step 1 `[DYNAMIC INTERFACE_METHOD, unconfirmed]`, the route statement |
| CI (GitHub Actions, this branch) | runs 175, 176, 177 `success` (first three commits); later runs checked in section 10 |

## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Hygiene rules in code before any D3c run; `--legacy-targets` reproduces CP7/CP9 exactly | **Met** | Hygiene `02317a1` precedes the D3c selection (`9a0adbb`) and run (`7fed16c`); fixtures 66/66 (`fixtures.json`), D3 14/14 and D3b 11/11 entry-level identical (`cp9_reproduction` in `d3_verdicts.json`, `d3b_verdicts.json`); contract test `test_cp10_committed.py` |
| 2 | Hygiene never creates NOT_REACHABLE in stratum N; every hygiene NOT_REACHABLE in S listed and adjudicated | **Met for N; S listed, adjudication pending** | Exhaustive unit test over entry combinations (`test_stratum_n_hygiene_only_turns_reachable_into_cant_determine`); N induced: 0 in D3c (no N cases in D3/D3b). S induced: D3c `AdGuardHome__GO-2026-6061`; in-sample D3 `cli__GO-2026-5052`, D3b `frp__GO-2025-4233` - all three are sheet items |
| 3 | Evidence labels in verdict JSON, text output and demo page | **Met** | `tests/contract/cp10/verdicts_evidence/*`, `test_cp10_evidence.py` (text, page), the CLI run in section 4 |
| 4 | D3c chosen by code with quotas and a seed fixed before runs; earlier apps excluded | **Met, quota N not reached** | Rules/candidates/seed `4696a7c` before the first probe; `d3c_selection.json` (`quotas_met: false`, S 16, N 7); exclusion enforced in code and tested |
| 5 | Sheets for every D3c case and the truth-only items; stop at `AWAITING_ADJUDICATION` | **Met** | `docs/results/cp10/adjudication/` (34 items); STATUS |
| 6 | Per-stratum verdict table vs govulncheck with intervals; false NOT_REACHABLE reported even when 0 | **Pending adjudication** | Renderer `cp10/report.py` does this; preview committed |
| 7 | In-sample sets labelled; headline fixed before results | **Met** | `HEADLINE` in `cp10/report.py` committed in `57e21e3`, before `9a0adbb`; D3/D3b sections say IN-SAMPLE. After the D3c run only a preview-table fallback in `changes_section` changed (`0c7e04a`), not the headline or any score |
| 8 | No analysed code executed; toolchain flags; no checkouts or caches committed | **Met** | `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY=off` for analysis (recorded in every verdict's `toolchain.env`); builds only to temp files deleted unread; `data/` is gitignored; `git ls-files data` is empty |
| 9 | Tests pass locally and in CI on the last commit; report; STATUS `AWAITING_REVIEW` after scoring | **Partly** | Tests pass locally (section 4); scoring and the final state belong to the next session |

## 6. Results (from committed files; no truth yet)

D3c verdicts (`docs/results/cp10/d3c/d3c_verdicts.json`, also in the preview results document):

| stratum | cases | VulnTrace hygiene | VulnTrace legacy | govulncheck claim | govulncheck level |
|---|---|---|---|---|---|
| S | 16 | REACHABLE 6, NOT_REACHABLE 8, CANT_DETERMINE 2 | REACHABLE 6, NOT_REACHABLE 7, CANT_DETERMINE 3 | REACHABLE 6, NOT_REACHABLE 10 | SYMBOL 6, PACKAGE 6, MODULE 1, NONE 3 |
| N | 7 | REACHABLE 1, NOT_REACHABLE 2, CANT_DETERMINE 4 | the same | REACHABLE 5, NOT_REACHABLE 2 | SYMBOL 5, NONE 2 |

Route evidence of the 7 hygiene REACHABLE verdicts: `STATIC_PATH` 2, `HAS_DYNAMIC_STEPS` 5.

Observations, not scores:
- govulncheck reported **no finding at all** (`NOT_AFFECTED`, level NONE) for 5 D3c cases although selection rule V3 found
  the build-list version inside the advisory's range (AdGuardHome GO-2026-6061 and GO-2026-5506, shiori GO-2026-5841,
  GO-2026-4887 and GO-2026-4883). They are scored as govulncheck NOT_REACHABLE claims and listed; the cause is not
  investigated here.
- In stratum N govulncheck answered at **symbol** level for 5 cases (an advisory without curated symbols lists whole
  packages, so any call into the package is a symbol-level finding). VulnTrace abstained (CANT_DETERMINE) on 4 of the 7 N
  cases, 3 of them `VERIFIER_REJECTED`.
- govulncheck ran twice per application (once per pass). Verdict, level, scored claim and symbol list were identical in
  every case; the example `trace` it prints differed in 7 D3c, 2 D3 and 4 D3b cases (it shows one of several call stacks).

## 7. Design deviations

1. **`evidence_level` name.** The verdict schema already uses `evidence_level` for the mode level (`TARGET_LEVEL`,
   `CHANGED_FUNCTION_LEVEL`, `CANDIDATE_LEVEL`). Redefining it would break every earlier verdict and the legacy
   reproduction, so the route's level is `path_evidence.evidence_level` (`STATIC_PATH` / `HAS_DYNAMIC_STEPS`, plus
   `NO_ROUTE_SHOWN`) at entry and verdict level.
2. **Stratum N rule, stricter than the literal text.** "Decision targets are the changed functions excluding context-only
   ones" taken literally could turn a legacy CANT_DETERMINE into NOT_REACHABLE (a context-only target that errors would
   simply be ignored), violating acceptance criterion 2. Implemented: in stratum N the verdict is the legacy verdict,
   except that a REACHABLE resting only on context-only targets becomes CANT_DETERMINE (`ONLY_CONTEXT_TARGETS_REACHABLE`).
3. **Curated symbols = the report's `symbols`**, not vulndb's machine-derived `derived_symbols`.
4. **The route shown does not replace `verified_path`.** Ranking adds `shown_path`; `verified_path` and every verifier
   decision keep their CP9 meaning, and the ranked path is checked by the verifier apart (display only). This keeps
   ranking from ever changing a verdict and keeps the legacy reproduction exact. The reproduction therefore compares after
   removing CP10's additive keys (`strip_cp10_evidence`).
5. **Helper contract version stays `1.0`**: the new request options are opt-in and absent options give the CP9 output
   byte for byte (Go test `TestNoRankNoLabelIsTheCP9Output`, recorded responses), as CP9 did for `feasibility`.
6. **D3c candidate list extended.** The 29 remaining D3 candidates were too few for two strata (15 drop again for
   reasons the strata do not change); 28 applications were added from memory, without probing, in the same commit as
   the rules and seed (`D3C_SELECTION_RULES.md`, "Why candidates were added"). Of the 8 kept applications, 3 come from the
   original list (AdGuardHome, croc, act) and 5 from the added list (shiori, gobuster, node_exporter, restic, glow); see
   `source_list` in `d3c_selection.json`.
7. **Per-application cases: up to 3 per stratum**, and applications added until both quotas are met, capped at 8
   applications, so that the process terminates; written in the rules before probing.
8. **Stratum N allows UNREVIEWED advisories** (V1N). Of the 7 N cases, 5 are UNREVIEWED.
9. **Truth target set.** The truth question is about the hygiene decision targets (curated symbols in S, non-context
   changed functions in N) and scores all three tools. The earlier CP7b/CP9 truths were judged on the legacy targets;
   the in-sample sections say which truth source each case uses.
10. **govulncheck ran on D3b and in both passes** (CP9 had not run it on D3b).

## 8. Blockers and limitations

- **Stratum N quota not met**: 7 of 8. The selection stopped at the 8-application limit after evaluating 28 of 57
  candidates (status counts: KEPT 8, DIVERSITY_DOMAIN 9, TOO_LARGE 4, NO_ELIGIBLE_ADVISORY 3, BUILD_FAILED 2,
  DIVERSITY_OWNER 1, NO_TAG_BEFORE_CUTOFF 1, not evaluated 29). No rule was relaxed; the spec allows adding
  applications, but the written cap (8) was reached. Whether to accept 7 or release a rule change is the supervisor's call.
- **A defect found and fixed during the session**: the first D3 run's reproduction field compared unsanitised local paths
  with the sanitised committed CP9 files and reported 6 entry-level differences; fixed in `9a0adbb` (sanitise first, as
  CP9 did), regression test added, D3 re-run (resumed from the same verdicts) gives 14/14.
- n is small (23 cases, 8 applications; S cases are clustered: act and restic and shiori and AdGuardHome give 3 each).
- Truth will come from reviewer agents of the same model family and the supervisor, not experts.
- In-sample D3 verdicts were computed at commits `4696a7c` (hygiene pass) and `57e21e3` (legacy pass), D3c at `792b9df` and
  `462166e`; the commits in between changed no pipeline code (scoring, sheets, results only).

## 9. Suggestions for the next checkpoint (not implemented)

- Look at the 5 `NOT_AFFECTED` govulncheck answers (version in range by go.mod and build list, yet no finding).
- The 3 stratum N `VERIFIER_REJECTED` abstentions: check which verifier check fails on these applications.
- If stratum N matters, a candidate source that targets modules whose advisories lack curated symbols.

## 10. Git

Branch `claude/wizardly-hamilton-0ft7q0`. Every push in this session succeeded.

```
0c7e04a CP10 task 4: verdict-level adjudication sheets (34 items: 23 D3c cases with truth and route judgement where REACHABLE; truth-only: 7 D3 REACHABLE, 4 D3b non-REACHABLE); results document rendered as a preview (headline pending); contract test for committed CP10 files; preview fix for the hygiene-change table
7fed16c CP10 task 3d: D3c triage (23 cases, 8 apps; hygiene and --legacy-targets, filter on, go1.26.10) and govulncheck v1.9.0 (source, symbol scan, pinned vulndb). Hygiene changes 1 case (AdGuardHome GO-2026-6061: CANT_DETERMINE -> NOT_REACHABLE, stratum S, to be adjudicated)
462166e CP10: D3b in-sample run: --legacy-targets reproduces the committed CP9 verdicts 11/11; hygiene changes 1 case (frp GO-2025-4233 CANT_DETERMINE -> NOT_REACHABLE, stratum S); govulncheck recorded
792b9df CP10 task 1b: --legacy-targets reproduces CP7 and CP9: CP7 fixtures 66/66 rows identical (go1.24.7, filter off); D3 14/14 verdicts identical to the committed CP9 verdicts (filter on, CP10 evidence keys removed, go1.26.10). D3 in-sample hygiene run: 2 cases change (gitleaks GO-2025-4020, cli GO-2026-5052 -> NOT_REACHABLE in stratum S); regression test for the reproduction check
9a0adbb CP10 task 3c: D3c selection by code (seed 20261126): 8 applications kept (the limit), 23 cases, S=16, N=7 (quota N=8 not met; candidates evaluated 28 of 57); fix: CP9 reproduction compares sanitised legacy verdicts (as CP9 did)
57e21e3 CP10 task 3b: scoring (cp10/score.py) and the results renderer (cp10/report.py) with the headline sentence fixed before any D3c result; verdict-level sheets (cp10/sheet.py: every D3c case, truth-only items for D3 REACHABLE and D3b non-REACHABLE cases); tests
4696a7c CP10 task 3a: D3c rules (docs/evaluation/D3C_SELECTION_RULES.md), candidate list d3c_candidates.json (29 remaining D3 candidates + 28 added, written without probing) and seed 20261126, committed before any D3c probe; select_d3c with strata S/N, quotas 8/8, 4-8 apps, D3/D3b apps excluded; cp10 CLI (select, run for fixtures/d3/d3b/d3c with hygiene + legacy + govulncheck, CP9 reproduction check); tests
7fd7bff CP10 tasks 2a-2c: evidence honesty. Helper (opt-in, contract unchanged without the options): rank_evidence ranks the N examined paths (filter pass, fewer DYNAMIC, shorter) and reports ranked_path; label_dynamic reports each DYNAMIC edge's kind. Verifier checks the ranked path apart (display only). Pipeline evidence stage adds shown_path, confirmed:false labels and path_evidence (STATIC_PATH / HAS_DYNAMIC_STEPS); triage --format text, --legacy-targets; demo page states the route caveat. Go, unit and contract tests, real recordings
02317a1 CP10 task 1a: target hygiene rules in code (stratum S: curated vulndb symbols decide, changed functions extra; stratum N: context-only targets never decide, ONLY_CONTEXT_TARGETS_REACHABLE); TriageRequest.target_policy (HYGIENE default, LEGACY = CP7/CP9); CP7/CP7b eval runners pinned to LEGACY; unit tests and real recordings
a44929d CP10: session starts; STATUS IN_PROGRESS on claude/wizardly-hamilton-0ft7q0; task list
```

(The report and STATUS commits that follow these are listed by the scoring session.)
