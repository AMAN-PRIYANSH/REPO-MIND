# CP9 - Path-feasibility filter for REACHABLE (downgrade-only)

- Recommended model: **Opus 5.5**, effort **high** (Go SSA analysis; mistakes here create false confidence)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days of builder work, then an adjudication round on a **new** set of applications, then a short scoring session
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `CP2.md`, `CP7.md`, `CP7b.md`, `CP8.md` (**review notes at the end of each bind this checkpoint**), `docs/results/CP7B_REAL_APPS_RESULTS.md`, `docs/results/cp7b/adjudication_reviews/` (the reviewers' notes name the infeasibility patterns), `docs/design/INTERFACES_AND_CONTRACTS.md` (helper contract, verifier)

## Goal

CP7b found that **0 of 7** REACHABLE paths on real applications could run as a whole, although every step exists. Build a **path-feasibility filter** that recognises the specific, common reasons a call-graph path cannot run, and measure, on applications it was **not** designed on, whether it removes false alarms without hiding real ones.

The filter is **downgrade-only**: it may turn `REACHABLE` into `CANT_DETERMINE` (reason `PATHS_INFEASIBLE`), never into `NOT_REACHABLE`, because its checks are incomplete. It never upgrades anything.

## The patterns (from the CP7b reviewers' notes)

| ID | Pattern | Example in D3 |
|---|---|---|
| F1 | **Context mismatch at a dynamic call through a parameter.** Function F is reached from call site s, then F makes an interface or function-value call on a value that came in through a parameter; the value passed at s cannot have the callee's type (VTA is context-insensitive and joins callers). | `fmt.Fprintf(os.Stderr, ...)` joined to `utls.UConn.Write`; a `goAway` item joined to `cleanupStream`; `sync.Once.Do` closure from one caller joined to another's |
| F2 | **Guard on a constant argument.** The next step's call site is only executed under a branch whose condition depends on a parameter, and the caller on the path passes a constant that makes the branch false. | `ListenUnix` passes port 0; a hard-coded `"badgerv2"`; `Exec` called with no variadic arguments under `len(arguments) > 0` |
| F3 | **Guard on a field that is never set.** The call site is only executed under `x.f != nil` (or `x.f != zero`) and no store to field `f` exists anywhere in the analysed program. | `archives.Rar.FS` |

Anything else (for example the go-pkcs12 MAC algorithm chosen through struct constants and an `Equal` method) is **out of scope** and must stay REACHABLE: being incomplete is acceptable, being wrong is not.

## Deliverables

1. **Feasibility check in the Go helper** (a new mode or an option of `reach`; the builder decides and records why)
   - Implements F1 to F3 on SSA with one level of call-site context along the path. Each check is conservative: when the analysis cannot decide (unknown values, reflection, `unsafe`, phi of non-constants, stores through pointers it cannot resolve), the step counts as **feasible**.
   - Path search: examine up to **N** shortest distinct paths per target (N fixed in the specification of the run, default 20, recorded in every result). The first path with no infeasible step is reported as the evidence. If all examined paths contain an infeasible step, the target is `PATHS_INFEASIBLE`, and the output records each path's first infeasible step with pattern ID, file, line and the reason (for example "argument at execute.go:72 is `*os.File`; callee receiver is `*utls.UConn`").
   - The VTA graph and the two-method verdict rule are unchanged; the filter runs after them and before the verifier.

2. **Pipeline and verifier integration**
   - New reason code `PATHS_INFEASIBLE`, schema extended without breaking old files.
   - The verifier checks that every reported infeasible step exists (file, line, call edge) and that a REACHABLE result's reported path has passed the filter. Downgrade-only property tests extended to the new code path.
   - A `--no-feasibility` switch gives the old behaviour, so before/after can be compared on the same inputs.

3. **Fixtures (truth by construction)** for every pattern: at least two infeasible cases per pattern (must be downgraded) and at least two **feasible look-alikes** per pattern (must stay REACHABLE), for example: the same `Fprintf` reached once with `os.Stderr` and once with the target type; a guard where one caller passes the constant and another passes a variable; a field that is set in one rarely-used function. All CP2/CP7 fixtures must keep their verdicts (any change is a failure to report, not to fix by editing the fixture).

4. **Evaluation**
   - **Fixtures:** downgrades of infeasible cases, **false downgrades** of feasible look-alikes and of existing true-REACHABLE fixtures (target: 0; report the number whatever it is).
   - **D3 (development set, in-sample):** before/after on the 14 CP7b cases. The patterns were designed from these cases, so this is **not** evidence of generalisation; label it so.
   - **D3b (held-out, the real test):** 3 new real applications chosen by the existing D3 selection code with its written rules, **excluding the five D3 applications**, with a new fixed seed recorded before any run. Run triage with and without the filter. The builder prepares adjudication sheets (same format as CP7b) for every case whose verdict is REACHABLE in either run, and stops at `AWAITING_ADJUDICATION`. The supervisor runs the same adjudication method as CP7b (two independent reviewer agents on the real source, supervisor reconciliation, owner spot-check).
   - **D1/D4 distributions:** how many REACHABLE verdicts the filter downgrades, by pattern (cost of the filter; no truth).
   - Headline sentence for the results document fixed in the renderer **before** any D3b result exists; results rendered by code to `docs/results/CP9_FEASIBILITY_RESULTS.md`; files under `docs/results/cp9/`, each under 512 KiB.

5. **Tests:** unit tests per pattern on SSA snippets, contract tests for the new output fields, integration tests on the fixtures; CI green.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | F1-F3 implemented, conservative when undecidable, downgrade-only (property tests). | Tests |
| 2 | Fixtures: every infeasible case downgraded; false downgrades of feasible look-alikes and old fixtures reported (target 0). | Results doc |
| 3 | D3 before/after reported and labelled in-sample. | Results doc |
| 4 | D3b chosen by code with the D3 rules and a seed fixed before runs; D3 apps excluded; sheets prepared; stop at `AWAITING_ADJUDICATION`. | Case list, sheets |
| 5 | After adjudication: REACHABLE path precision before vs after on D3b, number of REACHABLE downgraded, how many downgraded cases the adjudication judged reachable by some path (the filter's misses), with intervals. | Results doc |
| 6 | D1/D4 downgrade counts by pattern. | Results doc |
| 7 | `--no-feasibility` reproduces CP7/CP7b results exactly. | Test |
| 8 | No analysed code executed; toolchain flags used; no checkouts or caches committed. | Report, `git ls-files` |
| 9 | All tests pass locally and in CI (check CI on the **last** commit); report `docs/progress/reports/CP9_REPORT.md`; STATUS `AWAITING_REVIEW` after scoring. | Files |

## Out of scope

Changing VTA or the verdict rule, making any `NOT_REACHABLE` from the filter, general symbolic execution, patterns beyond F1-F3, LLMs anywhere in the verdict path, re-adjudicating D3, new models.

## Known risks

- A filter tuned on 7 paths can easily overfit; only D3b counts as evidence, and with 3 applications its n is small. Say so.
- Interface calls with many implementations make F1 expensive; cap the work and record when a cap is hit (the step then counts as feasible).
- Downgrading true REACHABLE results is the new danger: a real call path hidden as `CANT_DETERMINE`. Report every case where the adjudication says the target is reachable but the filter downgraded it.

## Review notes

(The supervising assistant adds notes here.)

**Supervisor review, 20 Nov 2026 - APPROVED as a negative result** (branches `claude/intelligent-planck-krrtgg` at `4ebcfa2` and the scoring session `claude/elegant-mccarthy-wq32ck` at `a5ff207`).

Checked by the supervisor: `pytest tests/unit tests/contract` -> 929 passed, 10 skipped; CI green on both scoring commits; the scoring session left the rendered results document unchanged (it only completed the report and STATUS).

How the D3b adjudication was done (the supervisor ran it): two independent Claude reviewer agents read the real source at the pinned versions; they agreed on all 14 path judgements (7 cases x path A and path B) and on `truth` for 5 cases; they split on the two go-task cases (A REACHABLE with low confidence through an unescaped `ref` in the go-getter URL; B NOT_REACHABLE with high confidence). The supervisor confirmed the first premise of A's route (`taskfile/node_git.go:113`) but not the rest, so those two are UNKNOWN. The owner spot-checked 8 lines of 3 cases chosen by a fixed rule before any review was seen; all matched, and check 8 (`tx.conn.Exec(ctx, "commit")`) supports the reviewers' reason for path B of the gogs cases.

What the results say:

1. **Fixtures:** 7/7 infeasible cases downgraded, 0/8 look-alikes and 0/36 true-REACHABLE CP7 runs downgraded; `--no-feasibility` reproduces CP7 exactly.
2. **In-sample D3:** 1 of 7 REACHABLE downgraded (gitleaks GO-2025-4020).
3. **Held-out D3b (the evidence):** 0 of 7 REACHABLE downgraded; REACHABLE path precision 0/7 without and 0/7 with the filter. The filter did not hide any real path (0 downgrades), and the targets were reachable by some other path in 5 of 7 (2 UNKNOWN). The infeasibility reasons in D3b were mostly outside F1-F3 as implemented (closures passed through helpers such as `withLock` and `BackoffUntil`, run-time state such as "inside a transaction", client-side versus server-side branches).
4. **Lesson:** three hand-written patterns do not generalise; real infeasibility is long-tailed. Keep the held-out discipline.

Important distinction for everything after CP9: **path precision** (is the shown route runnable) is not **verdict precision** (is the target reachable by some route). On D3b, verdict-level REACHABLE was right in 5/7, wrong in 0/7, unknown in 2/7. Verdict-level accuracy has never been measured on all D3 cases. CP10 measures it.
