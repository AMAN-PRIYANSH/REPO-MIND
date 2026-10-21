# CP2 - Go call-graph helper and verdict rule

- Recommended model: **Opus 5.5**, effort **high**
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `docs/implementation/checkpoints/CP1.md` (including review notes), `docs/progress/reports/CP1_REPORT.md`, `docs/architecture/SYSTEM_ARCHITECTURE.md` (verdict rule, known limits), `docs/design/DATA_MODEL.md` (CallPath, MethodResult, Verdict), `docs/design/INTERFACES_AND_CONTRACTS.md` (section 2), `docs/evaluation/EVALUATION_PLAN.md` (R1-R4), `docs/testing/TESTING_STRATEGY.md`, `docs/decisions/ARCHITECTURE_DECISIONS.md` (ADR-002, 003, 004)

## Goal

Add the second reachability method (a VTA call graph computed by a small Go helper), a deliberately naive control, and the verdict rule that combines VTA with CP1's linker method. Score all of them on the fixture suite, including new cases designed to make the two methods disagree.

No LLM, no embeddings, no advisory data, no retrieval, no database in CP2.

## Task 0 - CP1 carry-over (do this first, as its own commit)

- Change `.gitignore` so it ignores only the top-level `results/` directory (`/results/`), not `docs/results/`.
- Regenerate `docs/results/CP1_LINKER_RESULTS.md` from the output of `fixtures score --method linker --compare-inlining`, and commit it. If any part of that document was written by hand in CP1, make a small, tested generator for it instead, so results documents always come from code.
- Add a short "Correction" section at the end of `docs/progress/reports/CP1_REPORT.md` stating that criterion 9 was not met in the repository at review time, why, and the fix commit. Do not edit the rest of the CP1 report.

## Deliverables

1. **Go helper module** in `helper/`
   - Separate Go module (suggested module path `vulntrace/helper`), binary name `vt-helper`.
   - Depends on `golang.org/x/tools` (pin an exact version in `go.mod`; commit `go.sum`). Fetching it needs the Go module proxy; record in the report whether it worked from the session.
   - Request and response exactly as in [interfaces](../../design/INTERFACES_AND_CONTRACTS.md) section 2: request JSON file in, one JSON object on stdout, logs on stderr, `contract_version` "1.0".
   - Modes in CP2: `funcs`, `reach`, `edges`, `naive`. (`lift` moves to CP5.)
   - `funcs`: list functions and methods in given Go files with start/end lines, using the vulndb symbol format (`Func`, `Type.Method`).
   - `reach`: load the target module's main package(s) with `golang.org/x/tools/go/packages`, build SSA, compute a VTA call graph seeded from a CHA graph, and search from roots to each target symbol. Roots must include the main package's `init` as well as `main`, so package initialisers are covered. Return `PATH_FOUND` with up to `max_paths_per_target` shortest paths (each edge with caller, callee, call-site file and line, and `STATIC` or `DYNAMIC`), or `NO_PATH`. A target symbol not present in the loaded program returns `TARGET_NOT_FOUND`, never `NO_PATH`.
   - `edges`: confirm whether given caller→callee edges exist in the computed call graph (used by the verifier in CP7; tested now).
   - `naive`: the deliberately naive name-only call graph (edges only from calls written by name, from `go/ast`), the R1 negative control, using the same request/response shape as `reach`.
   - Environment for loading and building target code: `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; `GOPROXY=off` for fixtures.
   - Generic targets: attempt support; if not reliable, return `ERROR` with `UNSUPPORTED_SYMBOL_FORM`, as the linker does.

2. **Python wrapper** - suggested `src/vulntrace/methods/callgraph.py` and `src/vulntrace/methods/naive.py`
   - Builds `vt-helper` into a cache directory outside the repository (never committed), or reuses it if the source is unchanged.
   - Writes the request file, runs the helper with a timeout (default 300 s), validates the response against new schemas, and returns `MethodResult` objects with method `CALLGRAPH_VTA` (and a new method value for the naive control, added to the schema).
   - Maps every helper error code and Python-side `TIMEOUT` / `HELPER_MISSING` to `ERROR` results.

3. **Schemas**
   - `schemas/helper_request.schema.json`, `schemas/helper_response.schema.json`, `schemas/verdict.schema.json`.
   - Extend `method_result.schema.json` only by adding values (for example the naive method name); do not break CP1 data.

4. **Verdict rule** - suggested `src/vulntrace/verdict.py`
   - Implements the rule table in [system architecture](../../architecture/SYSTEM_ARCHITECTURE.md) exactly, including case-level aggregation and reason codes.
   - Output validates against `verdict.schema.json`, including the fixed reachability-only `statement`.
   - In CP2 there is no verifier yet: record `verification.status` as `NOT_RUN`, and treat the "verifier passes" column as not yet applicable. Note this in the report.

5. **New fixture cases** (at least 4; truth by construction, with rationale)
   - `present_but_unreachable`: a type whose method calls the vulnerable function is stored in an `any` (so the type is in the binary), while an interface method with the same name and signature is called only on a different type. Truth: NOT_REACHABLE. Designed so the linker may keep the symbol while VTA should not find a path.
   - `closure_never_called`: a closure that calls the vulnerable function is created and stored but never invoked. Truth: NOT_REACHABLE.
   - `method_expression`: the method is used as a method expression (for example `vulnlib.Impl.Run`) and the resulting function is called. Truth: REACHABLE.
   - `interface_two_impls_one_used`: two types implement an interface, only one is ever instantiated, and only the other calls the vulnerable function. Truth: NOT_REACHABLE.
   - Rename or annotate `unsafe_func_pointer` in the manifest rationale so it is not presented as an `unsafe` test (see CP1 review notes). Do not change its truth label.
   - Method outcomes for these cases must be observed, not assumed. The point of these cases is to see disagreements.

6. **Scoring** - extend `fixtures score`
   - `--method vta`, `--method naive`, `--method combined` (combined = verdict rule over VTA + linker).
   - Writes JSON and Markdown under the top-level `results/` directory, as in CP1.
   - Per-case table: truth, each method's result, combined verdict, reason codes.
   - Summary per method: agreements, false NOT_REACHABLE, false REACHABLE, `CANT_DETERMINE` count, errors.

7. **Tests**
   - Unit: verdict rule (every row of the table and the case-level aggregation), schema validation, response parsing, error-code mapping.
   - Contract (`tests/contract/`): recorded helper responses (success and every error code) validated against the schemas and mapped correctly. These must not need Go.
   - Integration (skip with a clear message if Go or the helper build is unavailable): VTA, naive and combined on every fixture case; determinism; `TARGET_NOT_FOUND` is not reported as `NO_PATH`; timeout handling (a test request with a tiny timeout).
   - Go unit tests inside `helper/` for symbol matching and path extraction, run with `go test ./...` in `helper/`.

8. **Results document** - `docs/results/CP2_CALLGRAPH_RESULTS.md`, generated by code from the result files: environment, commands, the per-case table, the four method summaries, and every disagreement or mismatch explained.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Task 0 done: `docs/results/CP1_LINKER_RESULTS.md` is tracked by git and generated by code; `.gitignore` fixed; correction noted in the CP1 report. | `git ls-files` output; commit |
| 2 | Unit and contract tests pass with only Python installed. | Printed summaries |
| 3 | Integration tests and `go test ./...` in `helper/` pass where Go is available. | Printed summaries |
| 4 | Every helper error code and `TIMEOUT` / `HELPER_MISSING` has a test. | Test names |
| 5 | R1-R4 (naive, linker, VTA, combined) scored on all fixtures and reported. | Results document |
| 6 | The combined verdict has **zero false NOT_REACHABLE** on the fixtures, or each exception is explained with a proposed design change. The rule is not weakened to pass. | Results document |
| 7 | The naive control's false NOT_REACHABLE cases are shown (expected on function-value and reflection cases). | Results document |
| 8 | Disagreement cases produce `CANT_DETERMINE` with `METHOD_DISAGREEMENT`, as the rule says. | Per-case table |
| 9 | `TARGET_NOT_FOUND` never becomes `NO_PATH`. | Test name |
| 10 | Helper peak memory and time on the largest fixture are recorded. | Results document |
| 11 | No built binaries, caches or `results/` files are committed; `docs/results/` files are committed. | `git ls-files` |
| 12 | Report at `docs/progress/reports/CP2_REPORT.md` in the wrapper format; STATUS set to `AWAITING_REVIEW`. | Files |

## Out of scope

Lifting (`lift` mode, CP5), the evidence verifier (CP7), advisories, git fetching of other repositories, real applications, any model, retrieval, database or UI.

## Known risks

- VTA may resolve `reflect` calls differently from the linker; that is expected and should show up as `CANT_DETERMINE`, not be "fixed".
- Root selection (`main` plus `init`) matters for `init_imported`; get it wrong and that case becomes a false NOT_REACHABLE.
- If the Go module proxy is unreachable from the session, the helper cannot be built; report it as a blocker instead of vendoring code by hand.

## Review notes

**Supervisor review, 21 Oct 2026 - APPROVED.**

Checked on a clean checkout of `claude/optimistic-shannon-397w1q` at `bd53912`:

- Re-run by the supervisor: `pytest tests/unit tests/contract` → 138 passed.
- **Not** re-run by the supervisor: `go test ./...` in `helper/` and the 22 integration tests. The supervisor's sandbox cannot reach the Go module proxy (`proxy.golang.org` refused), so `golang.org/x/tools` could not be downloaded. These rest on the implementer's evidence plus code reading. CP3 task 0 adds GitHub Actions CI so every later checkpoint is verified in a neutral environment.
- Truth labels of the four new fixtures checked by reading the code: correct. The devirtualisation fix kept truth labels unchanged.
- `verdict.py` matches the rule table row for row.
- Results: combined rule has 0 false NOT_REACHABLE and 0 false REACHABLE on 22 cases, with 6 `CANT_DETERMINE`. VTA alone is unsafe on reflection and `unsafe`; linker alone is unsafe on present-but-unreachable cases. This is the central design claim, now demonstrated on fixtures.

Accepted from the implementer:

- `golang.org/x/tools` pinned at v0.42.0 because later versions need Go 1.25 (environment has 1.24.7). Recorded in risks.
- The CP1 review note on `unsafe_func_pointer` was partly wrong: it is a real `unsafe` test for VTA. Correction accepted.
- Proposal to distinguish "package not in program" from "symbol not found": accepted; contract updated (interfaces section 2) and implemented in CP3 task 0.

Noted, not blocking:

- One commit (`35c50b9`) was pushed with a failing unit test because a pipe hid the exit code; fixed in the next commit and reported honestly.
- A draft pull request (#1) was opened although the wrapper says not to. Harmless; it closes when `main` contains the branch.
