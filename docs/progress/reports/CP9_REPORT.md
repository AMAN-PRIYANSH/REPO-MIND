# CP9 report - Path-feasibility filter for REACHABLE (downgrade-only)

Branch `claude/intelligent-planck-krrtgg` (one session, 17-18 Nov 2026). State at the end of this session:
**`AWAITING_ADJUDICATION`**. The D3b adjudication sheets are prepared; the D3b precision and miss numbers
(acceptance criterion 5) do not exist yet and are not claimed anywhere. A second, short session scores the filled
sheet and completes this report (sections marked *pending*).

**Summary of what was measured.** On fixtures built for the purpose, the filter downgrades every infeasible case
(7/7) and no feasible look-alike (0/8) or truly REACHABLE CP2/CP7 fixture run (0/36). On the 14 D3 cases it was designed
from (in-sample), it downgrades 1 of 7 REACHABLE verdicts. On the held-out D3b (3 new applications, 11 cases) it
downgrades **0 of 7** REACHABLE verdicts, and on the CP7-REACHABLE cases of D1 (38) and D4 (32) it downgrades 0 cases.
With the filter off, the pipeline reproduces CP7 (66/66 fixture rows), CP7b (14/14 D3 verdicts), D1 (38/38) and D4
(32/32) exactly. The filter is safe but, outside the cases it was designed from, it almost never fires: every REACHABLE
target in D3b, D1 and D4 has at least one call-graph path with no F1-F3 step. What it does change on D3b is the
**reported path** (all 7 cases now report a different path, "path B"); whether path B is better than path A is exactly
what the pending adjudication measures.

## 1. Environment

| Item | As printed |
|---|---|
| OS | `Linux vm 6.18.44-fc-v553 #1 SMP PREEMPT_DYNAMIC @0 x86_64` (Ubuntu 24.04.5 LTS), 4 CPUs, 15 GiB RAM; after a worker restart late in the session `uname` showed `6.18.44-fc-v595`, the working tree and `data/` survived |
| Python | `Python 3.13.18` (project `.venv`, `pip install -e ".[dev,db,agent]"`, the CI extras) |
| Go (system) | `go version go1.24.7 linux/amd64`: Go unit tests, integration tests, CP9 fixtures, D1, D4 (CP7's toolchain) |
| Go (D3, D3b) | `go version go1.26.10 linux/amd64`, fetched as `golang.org/toolchain@v0.0.1-go1.26.10.linux-amd64` from the Go module proxy into the scratchpad (sum `h1:5VAGHlY8yl8pTPVSNIez3SNMy6fWabs+QMR25f3oMT0=`, the same as CP7b), first on `PATH`; nothing installed system-wide |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.10.0, build fdd4b8e` (not used) |
| x/tools | `v0.42.0` (unchanged) |

Network checks: `proxy.golang.org` 200; `pypi.org` 200; `api.github.com` 200; `git ls-remote https://github.com/wagoodman/dive HEAD` works; plain HTTPS to github.com 400 through the proxy (git works); `go.dev` and `vuln.go.dev` blocked by the proxy (403 to CONNECT), as in CP7b. Consequences: the toolchain came from the module proxy; govulncheck was not re-run (it is a reference only and not part of CP9).

## 2. Files changed

| File | Purpose |
|---|---|
| `helper/feasible.go` | The filter: F1-F3 on SSA, facts through parameter pass-through, state search, N shortest paths, reasons with file and line |
| `helper/feasible_test.go` | Go unit tests per pattern (SSA snippets), look-alikes, conservative cases, caps, compatibility, validation |
| `helper/contract.go`, `helper/main.go`, `helper/reach.go` | `feasibility` request/response fields (omitted when not asked); validation; `reduce` keeps the node -> SSA function map (no output change) |
| `fixtures/feasibility/` (`go.mod`, `vulnlib/`, 16 `cmd/*/main.go`, `manifest.json`) | CP9 fixtures, truth by construction, in a separate module so the CP2/CP7 suite is untouched |
| `schemas/helper_request.schema.json`, `helper_response.schema.json`, `verdict.schema.json`, `fixture_manifest.schema.json` | Additive: `feasibility` objects, `PATHS_INFEASIBLE`, `FILTERED_PATH` / `INFEASIBLE_STEP` checks, manifest `pattern` / `kind` / `expected_filter` |
| `src/vulntrace/pipeline/feasibility.py` | Filter stage (REACHABLE + INFEASIBLE -> CANT_DETERMINE / PATHS_INFEASIBLE) and its own downgrade guard |
| `src/vulntrace/pipeline/triage.py`, `analyse.py`, `aggregate.py`, `cli.py` | Stage wiring (after the rule table, before the verifier), `Runners.feasibility`, `--no-feasibility`, `--max-examined-paths`; guard accepts the filter's evidence as verified path |
| `src/vulntrace/methods/callgraph.py` | Request `feasibility` only when asked; answer copied into MethodResult details |
| `src/vulntrace/verifier/verify.py`, `checks.py` | FILTERED_PATH (evidence path must pass too, as well as a method path) and INFEASIBLE_STEP (reported steps and context edges must exist) |
| `src/vulntrace/verdict.py`, `paths.py`, `__main__.py`, `eval/triage_cli.py`, `eval/triage_eval.py` | Reason constant, fixture path, CLI (`eval feasibility`, `cp9 sheet`, `cp9 report`, flags on `eval triage`), memo runners carry the setting |
| `src/vulntrace/eval/feasibility_eval.py`, `feasibility_real.py`, `feasibility_dist.py`, `feasibility_sheet.py`, `feasibility_report.py`, `feasibility_cli.py` | Fixture evaluation and CP7 reproduction; D3/D3b off/on runs with CP7b's runner; D1/D4; sheets; renderer (headline fixed before D3b results) |
| `docs/evaluation/D3B_SELECTION_RULES.md`, `docs/evaluation/d3b_candidates.json` | D3b rules and candidate list, seed 20261117, committed before any probe |
| `docs/results/cp9/**`, `docs/results/CP9_FEASIBILITY_RESULTS.md` | Results (each file under 512 KiB; three large verdict copies as `.json.gz`, listed in `d3b_feasibility.json`) |
| `tests/unit/test_cp9_feasibility.py`, `test_cp9_report.py`, `test_cp9_sheet.py` | Filter stage, verifier checks, filter-on never stronger than filter-off (exhaustive single symbols + 300 random pairs), renderer, sheets |
| `tests/contract/record_cp9.py`, `tests/contract/cp9/**`, `test_cp9_contract.py`, `test_cp9_committed.py` | Real recordings (helper responses, 8 verdict scenarios), committed-results checks, regeneration test |
| `tests/contract/test_cp7_verdict_contract.py` | "Every reason code is recorded" also counts the CP9 recordings (PATHS_INFEASIBLE lives there); nothing weakened |
| `tests/integration/test_cp9_feasibility.py` | CP9 fixtures as constructed; CP7 fixtures unchanged and reproduced (real Go) |
| `docs/progress/STATUS.md`, this report | State, task list, handoff |

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Feasibility check in the Go helper | **Done.** Option `feasibility` of `reach` (one load and one VTA graph; the filter needs the SSA program the graph came from; a request without it is byte-identical to before). F1-F3, conservative when undecidable, N = 20 recorded in every result, first infeasible step with pattern, file, line, reason and context edges |
| 2 | Pipeline and verifier integration | **Done.** `PATHS_INFEASIBLE`, additive schemas, verifier FILTERED_PATH / INFEASIBLE_STEP, property tests, `--no-feasibility` |
| 3 | Fixtures | **Done.** 16 cases: F1 2 infeasible + 3 look-alikes, F2 3 + 2, F3 2 + 3, 1 out-of-scope (pkcs12 pattern) |
| 4 | Evaluation | **Partly done (by design).** Fixtures, D3 (in-sample), D3b runs and sheets, D1/D4 done; D3b scoring waits for the adjudication |
| 5 | Tests | **Done**; CI green on every completed run of the branch (see section 4) |

## 4. Test evidence

| Command | Printed summary |
|---|---|
| `python -m pytest tests/unit tests/contract -q` (baseline, before any change) | `887 passed, 10 skipped in 17.22s` |
| `python -m pytest tests/unit tests/contract -q` (last) | `929 passed, 10 skipped in 19.79s` |
| `(cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 go test -count=1 ./...)` | `ok  	vulntrace/helper	18.449s` |
| `python -m pytest tests/integration/test_cp9_feasibility.py -q` | `38 passed in 263.18s (0:04:23)` |
| `python -m pytest tests/integration -q` | `172 passed, 2 skipped in 366.09s (0:06:06)` (the 2 skips: opt-in network tests, `VULNTRACE_NETWORK_TESTS` not set) |
| `python tests/contract/record_cp9.py` | 8 verdict scenarios and 4 responses recorded; every built-in assertion held |
| GitHub Actions CI on this branch | `success` on every completed run, 156-168 (commits `3e6574b` ... `6af94c4`, the last code and results commit); see the addendum for the documentation commits after it |

## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | F1-F3, conservative when undecidable, downgrade-only (property tests) | **Met** | `helper/feasible_test.go` (per pattern, look-alikes, phi of constants, address-taken parameter, package variable, constant condition, struct-constant, reflection, unsafe, pointer escape, struct conversion, caps); `test_filter_on_is_never_stronger_than_filter_off`; filter guard on every verdict |
| 2 | Fixtures: every infeasible case downgraded; false downgrades reported | **Met** | `fixtures.json`: 7/7 infeasible downgraded; false downgrades 0 of 8 look-alikes, 0 of 36 truly REACHABLE CP2/CP7 runs |
| 3 | D3 before/after reported and labelled in-sample | **Met** | `d3/d3_feasibility.json` (`label` IN-SAMPLE), results document section |
| 4 | D3b chosen by code with the D3 rules, seed fixed before runs, D3 apps excluded, sheets prepared, stop at AWAITING_ADJUDICATION | **Met** | seed and list committed in `82868ed` before probing; selection `3a81afd` before triage; sheets `d627428`; STATUS |
| 5 | After adjudication: precision before vs after, downgrades, misses, intervals | **Pending** | needs the filled sheet |
| 6 | D1/D4 downgrade counts by pattern | **Met** | `d1_feasibility.json`, `d4_feasibility.json` |
| 7 | `--no-feasibility` reproduces CP7/CP7b exactly | **Met** | fixtures 66/66 rows identical (and corruption probe, summaries); D3 14/14 verdicts identical (verdict, reasons, every entry's result, reason, methods, verified path); D1 38/38 and D4 32/32 case verdicts; integration test |
| 8 | No analysed code executed; toolchain flags; nothing cached committed | **Met** | only the helper, `go list`, `go build -o <temp>` (deleted, never run), `go tool nm`; `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; `git ls-files` shows no `data/`, binaries or venv |
| 9 | Tests pass locally and in CI (last commit); report; STATUS AWAITING_REVIEW after scoring | **Partly** | tests and CI as in section 4; report written; STATUS is AWAITING_ADJUDICATION (AWAITING_REVIEW after scoring) |

## 6. Results (copied from `docs/results/CP9_FEASIBILITY_RESULTS.md`, generated by code)

Headline: *pending* (the template was fixed in `bd92d72` before any D3b result).

| Set | Cases | REACHABLE without filter | Downgraded by filter | Filter answers per REACHABLE entry | Filter off reproduces earlier results |
|---|---|---|---|---|---|
| CP9 fixtures | 16 | 16 | 7 (all 7 infeasible; 0 of 8 look-alikes; out-of-scope kept) | - | - |
| CP2/CP7 fixtures (3 modes) | 66 runs | 36 truly REACHABLE runs | 0 | - | 66/66 rows identical |
| D3, in-sample | 14 | 7 | 1 (gitleaks GO-2025-4020, F1; F3 also on its examined paths) | FEASIBLE 40, INFEASIBLE 1 | 14/14 verdicts identical |
| D3b, held-out | 11 | 7 | **0** | FEASIBLE 150 | (new set) |
| D1 (CP7-REACHABLE cases only) | 38 | 38 | 0 | FEASIBLE 275 | 38/38 |
| D4 (CP7-REACHABLE cases only) | 32 | 32 | 0 | FEASIBLE 274, INFEASIBLE 2 (F2, GO-2026-6665; the case stays REACHABLE) | 32/32 |

D3 in-sample detail (from `d3/d3_feasibility.json`, the first examined path of each REACHABLE entry): of the 7
cases the CP7b reviewers judged INFEASIBLE_PATH, the filter reported the reviewers' kind of infeasible step in 5:
F1 at `fmt/print.go:225` (the `Fprintf(os.Stderr)` splice, Xray GO-2026-4512), F1 at `sync/once.go:78` (a Once splice,
cli GO-2026-5506; the closure named is `crypto/elliptic.initAll`, not the godebug closure the reviewers cited), F1 at
`controlbuf.go:387` (the goAway splice, on the `isTransportResponseFrame` entries of Xray GO-2026-6061), F2 at
`hub.go:410` (`ListenUnix` passes port 0, Xray GO-2026-5676) and F1 at `detect/detect.go:209` for gitleaks
GO-2025-4020 (the `sources.Files` / `File` splice reviewer A also noted; F3 on `Rar.FS` appears on other examined
paths). In 4 of those 5 the state search found another path with no F1-F3 step, so they stay REACHABLE with a new
evidence path; only gitleaks is downgraded. Not recognised: pkcs12 (out of scope by design) and pgx
`len(arguments) > 0` (cli GO-2026-5004): in pgx v5.7.5 `Conn.exec` reassigns `arguments` in its option loop
(`conn.go:484`, `:487`) and through `RewriteQuery` (`:494`), so at the `execSimpleProtocol` call (`:547`) the value is no
longer the parameter and counts as unknown (checked by reading the downloaded module source, not run).

## 7. Design deviations

1. **The INFEASIBLE decision uses an exhaustive state search; the N = 20 shortest paths are examined for the
   explanation only.** The specification says a target is PATHS_INFEASIBLE when all N examined paths contain an
   infeasible step. That rule would hide real paths behind hubs: the 20 shortest paths often all pass one joined call
   (D3: `Fprintf(os.Stderr)`), while a longer path is fine. The filter instead downgrades only if a breadth-first search
   over states (function, known parameter facts) from the roots finds no path that avoids every infeasible step. This
   can only give fewer downgrades than the specified rule, never more. N is still fixed (20), examined, reported and
   recorded in every result; the first examined path with no infeasible step is the evidence when there is one.
2. **Context follows direct parameter pass-through along the path**, not only one call-site level. Two of the three F1
   examples need it (`Once.Do(f) -> doSlow(f) -> f()`, `put(it) -> executeAndPut(nil, it)`). Only values passed
   unchanged as a parameter are followed; anything else is unknown.
3. **CP9 fixtures are a separate Go module** (`fixtures/feasibility`), so the 22 CP2/CP7 fixtures and their committed
   results stay byte-identical (CP9 criterion 7).
4. **Verifier with the filter on:** a REACHABLE entry needs a method path that passes (as before) *and* the filter's
   evidence path, which becomes the verified path. So the filter can never make the verifier accept a case it rejects
   without the filter (proved by the property test).
5. **F3 and reflection:** F3 does not apply when a pointer to the struct (or to anything holding it) is converted to an
   interface anywhere in the program, when an `unsafe.Pointer` is converted to such a pointer, when the field's address
   escapes, or when another struct type is converted to it. Construction through `reflect.New(TypeOf(T{}))` is not
   detected; this is a known hole, documented in `feasible.go`.
6. **D3b:** the D3 candidate list minus the five D3 applications, quota 3, seed 20261117 (rules file
   `D3B_SELECTION_RULES.md`). The diversity rule A1 applies among D3b applications only.
7. **Committed verdict copies:** each entry keeps its first 3 examined paths (and their count); filter-on copies leave
   out method paths identical to the filter-off copy beside them; a copy still over 512 KiB is committed in full as
   `.json.gz` (3 files). Full verdicts stay in `data/cp9/`.
8. **D1/D4:** only the 70 cases whose CP7 verdict was REACHABLE are re-run (the filter cannot change anything else, by
   construction and by test), with CP7's toolchain.
9. **Sheet format:** the CP7b format, extended for two paths per case (`adjudication_off`, `adjudication_on`,
   `steps_correct`, `truth`); targets chosen with CP7b's rule (changed functions before context-only ones).

## 8. Blockers and limitations

- **The filter rarely fires outside its design set.** D3b: 0 downgrades; D1/D4: 0 case downgrades. With 3 applications
  and 11 cases, "0 of 7" says little either way (95% Wilson upper bound 0.35 for the downgrade rate).
- **D3b is less independent than "held-out" suggests:** 4 of its 11 cases use advisories that are also in D3
  (GO-2026-5841, GO-2026-6061, GO-2026-5676, GO-2026-5004), so some vulnerable library code, including the pgx code the
  F2-variadic idea came from, is shared; the applications are new.
- D3b cases of one application share code and are not independent.
- The filter changes the reported path in all 7 D3b REACHABLE cases; whether path B is more often runnable than path A
  is unknown until adjudication.
- Per-case seconds are not a clean cost measure (the second run benefits from warm build and module caches); the
  helper records the filter's own time in `stats.feasibility.duration_ms`.
- The D1/D4 background job was stopped at the 2-hour limit with 5 D4 filter-on cases left; they were finished by a
  resumed run (the runner resumes per case; no case was re-run). The D3 and D3b result files were first written by
  harness code that was not yet committed; the analysis code (helper, pipeline) was committed (`3e6574b`) before every
  run, and all committed result files were rewritten from a clean tree by resuming (`repo_dirty: false` in each file).
- `dataset materialize --cases <subset>` rewrites `docs/results/datasets/D1|D4_materialize.json`; both were reverted
  and are unchanged in git.
- Cosmetic: the selection log's quota line says "five applications were already kept" for D3b (quota 3). Not changed
  after the selection ran.
- govulncheck was not re-run (reference only; not required by CP9).

## 9. Suggestions for the next checkpoint

- Score D3b (second session), and if path B turns out no better than path A, keep the filter off by default for the
  reported path and use it only as a downgrade guard.
- Handle loop phis of a parameter and its own slices (`arguments = arguments[1:]`) for F2; that is the pgx case.
- Look again at the clear-answer CANT_DETERMINE cases of CP7b (all three had a clear NOT_REACHABLE), which matter more
  than REACHABLE paths for users.

## 10. Git

Branch `claude/intelligent-planck-krrtgg`; every commit was pushed (no push failed). `git log --oneline f066158..HEAD`
before the commit that adds this list:

```
16110e9 CP9: report (scoring pending) and STATUS AWAITING_ADJUDICATION; D3b sheets ready for the supervisor
6af94c4 CP9 task 4e: results document rendered by code (headline pending D3b adjudication); regeneration test; clearer D1/D4 entry wording
4840d6d CP9 task 4d: D4 distribution: filter off reproduces CP7 on all 32 CP7-REACHABLE cases; filter on downgrades 0 cases (2 of 276 REACHABLE entries INFEASIBLE by F2, in GO-2026-6665)
20bdd5b CP9 task 4d: D1 distribution: filter off reproduces CP7 on all 38 CP7-REACHABLE cases; filter on downgrades 0 (275 REACHABLE entries, all FEASIBLE)
d627428 CP9 task 4c: D3b adjudication sheets (7 cases, path A without and path B with the filter for the same changed target); contract test for committed CP9 results
24d833e CP9 task 4c: D3b triage with and without the filter (held-out): 7 REACHABLE without the filter, 0 downgraded; every REACHABLE entry has a path that passes the filter
fa6aa37 CP9: a committed verdict copy over 512 KiB is written in full as .json.gz (under 512 KiB) instead of being cut; the sheet reads both
a682c01 CP9 task 4b: D3 before/after (IN-SAMPLE): filter off reproduces all 14 CP7b verdicts; filter on downgrades 1 of 7 REACHABLE (gitleaks GO-2025-4020), 6 stay REACHABLE with paths that pass the filter
c546837 CP9: committed D3/D3b verdict copies keep 3 examined paths per entry and leave out method paths identical to the filter-off copy (512 KiB limit); full verdicts stay in data/
4b4c374 CP9: STATUS: fixture results done, D3b selected, handoff notes
3a81afd CP9 task 4c: D3b selection by the D3 rules (seed 20261117, D3 apps excluded): go-task/task, fatedier/frp, gogs/gogs; 11 cases. Committed before any D3b triage.
ebba1d3 CP9 task 4a: fixture results (7/7 infeasible downgraded, 0/8 look-alikes and 0/36 true-REACHABLE CP7 runs downgraded; --no-feasibility reproduces all 66 CP7 fixture rows)
3d40a11 CP9: D3b adjudication sheet generator (cp9 sheet) and cp9 report command
bd92d72 CP9: results renderer with the D3b headline fixed before any D3b result; D3/D3b (off/on) and D1/D4 harnesses
82868ed CP9: D3b selection rules and candidate list (seed 20261117, D3 apps excluded, quota 3), fixed before any D3b probe or run
722dfd1 CP9: STATUS ticks tasks 1-3 and records handoff notes
3e6574b CP9 task 2: pipeline and verifier integration of the feasibility filter
634d4e0 CP9 task 1: feasibility filter in the Go helper (reach option), F1-F3 on SSA with parameter pass-through context; CP9 fixture module (16 cases); Go unit tests per pattern, conservativeness, caps, compatibility
e06d06f CP9: session starts; STATUS IN_PROGRESS, branch claude/intelligent-planck-krrtgg, task list
```

## Addendum (end of this session)

- Local: unit + contract `929 passed, 10 skipped`; Go `ok vulntrace/helper`; integration `172 passed, 2 skipped`.
- CI: `success` on runs 156-168. Run 169 (`16110e9`, report and STATUS only) and the run for the commit that adds this
  addendum (documentation only) were still running when this was written; their result is stated in the session's
  final message and must be checked by the scoring session before `AWAITING_REVIEW`.
- Stopped at `AWAITING_ADJUDICATION`; nothing of the next checkpoint was started.
