# CP5b - Lifting and caller/callee queries (Go helper)

- Recommended model: **Opus 5.5**, effort **high** (Go call-graph code is subtle; keep the session short and focused)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 2-3 days
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `docs/implementation/checkpoints/CP2.md` (helper design, review notes), `CP3.md`, `CP4.md` and `CP5.md` (**review notes at the end of each bind this checkpoint**), `docs/design/INTERFACES_AND_CONTRACTS.md` (section 2, the helper contract), `docs/design/DATA_MODEL.md` (symbol origins, `LIFTED`), `docs/evaluation/EVALUATION_PLAN.md` (E1+L, metrics), `docs/decisions/RISKS_AND_OPEN_QUESTIONS.md` (Q4, R5, R16)

## Goal

Add the Go helper modes the rest of the project needs: **`lift`** (from a function, walk callers up to exported entry points) and **`callers` / `callees`** (read-only call-graph queries for the CP6 agent). Measure lifting against the vulnerability database's own `derived_symbols`, which are exactly the lifted symbols a human curator added.

Why now: CP3 found the labelled function is not among the changed functions in about a quarter of cases (R5), and CP5 showed that an LLM choosing one changed function loses recall. Lifting is the planned answer to label conventions, and the CP6 agent tools need the same call-graph queries.

No LLM, no embeddings, no retrieval changes. No new Colab model run is needed.

## Task 0 - carry-overs from the CP5 review (each its own commit, do first)

0a. **D1 first-pass mismatch.** `dataset materialize --set d1` leaves about 9 of 150 cases in the wrong state on the first pass (the same 9 in two different environments); a second pass fixes them in seconds. Find the cause: run `dataset diagnose` on one of the 9 (for example `GO-2026-5681`) with a fresh cache and report the git error. Fix it so **one** pass converges, add a test that would have caught it, and remove the double-run workaround from `notebooks/cp5_llm_colab.ipynb`. If the cause cannot be found, say so and keep the workaround.

0b. **Ollama install check.** In the CP5 notebook, the install cell only checks `which ollama`, so a partial install (no `llama-server`) is never repaired and every call fails with HTTP 500. Make it check that the server really works (for example one tiny generate call) and re-run the installer if not.

0c. **Correct one case record.** `GO-2020-0006` is `PSEUDO_VERSION_UNRESOLVED` in `docs/results/datasets/D4_cases.json` but rebuilds as `AVAILABLE` in every environment. Update that one record and the counts, as its own commit with the reason, and make sure the evidence gate expectations still hold.

0d. **HyDE table note.** In the CP5 renderer, state how many comparisons each model's HyDE table contains, so a single borderline interval cannot read as a finding. Regenerate `docs/results/CP5_LLM_RESULTS.md` from the committed result files (no model run).

## Deliverables

1. **Helper `lift` mode** - `helper/` (Go)
   - Request: module/package loading information as for `reach`, plus a list of seed symbols (vulndb symbol format). Response: for each seed, the lifted exported entry points with one example call path each, and a status.
   - Exported entry point = an exported function, or an exported method of an exported type, in a package that is not `internal` and not `main`.
   - **Stopping rule (open question Q4): implement both and measure both.** `NEAREST`: stop at the first exported function on each caller path. `ALL`: collect every exported entry point reachable upward, up to a depth limit (stated and recorded). Interface calls and function values use the same VTA-seeded call graph as `reach`; record how each edge was resolved (`STATIC` or `DYNAMIC`).
   - A seed that is already exported lifts to itself (`origin` unchanged). A seed with no exported caller returns `ROOT_ONLY` (lifting failed), never an invented symbol. Generic targets: `UNSUPPORTED_SYMBOL_FORM`, as elsewhere.
   - Loading real modules needs their dependencies. Builds use `GOTOOLCHAIN=local` and `CGO_ENABLED=0`; never run `go generate`, tests or built binaries of the analysed code (CLAUDE.md section 8). A module that cannot be loaded returns a clear status (`LOAD_FAILED` with the first error line), which is counted and reported, never dropped.

2. **Helper `callers` and `callees` modes**
   - One-hop (optionally N-hop, N stated) read-only queries from a symbol, with call-site file and line. Response shape as in the helper contract (`contract_version` stays "1.0"; add fields and statuses only, do not break existing recordings).
   - Python wrappers in `src/vulntrace/methods/` with timeouts and error mapping like the other modes; new schema entries added, not breaking.

3. **Fixtures** (extend `fixtures/reachability/` or add a lifting fixture set, truth by construction, rationale per case): private helper called by an exported function; call through an interface; call through a function value; call through a method value; unexported type with exported wrapper; package under `internal/`; no exported caller (expect `ROOT_ONLY`); seed already exported; a diamond (two exported callers, to separate `NEAREST` from `ALL`). Outcomes must be observed, not assumed.

4. **Lifting evaluation on D1** - `python -m vulntrace eval lift`
   - Cases: D1 cases whose vulndb record has non-empty `derived_symbols`. First report how many there are and how many modules load successfully (`LOAD_FAILED` counted, with reasons).
   - Seeds: the core symbols (known root cause). Gold: the `derived_symbols`. Metrics: recall and precision of the lifted set against `derived_symbols`, per case macro-average, with cluster bootstrap 95% intervals (D1 `cluster_key`), for `NEAREST` and `ALL`; coverage (cases where lifting succeeded) reported next to every rate.
   - **E1+L:** apply lifting to the E1 selections already committed in `docs/results/cp5/` (no model re-run) and score against core ∪ derived. Report E1+L next to E1 and E0, paired.
   - **Ceiling measurement on D4 (measurement only, no pipeline change):** for D4 cases whose core symbol is not among the candidates, report how often it lies within 1 or 2 caller or callee hops of some candidate. This tells CP6 whether graph expansion could help.
   - Results to `results/cp5b/` as JSON, rendered by code to `docs/results/CP5B_LIFTING_RESULTS.md`. Evidence that needs source checkouts and dependencies stays in the gitignored `data/` directory and cache. Say how long the real run took and on which machine; if the Go proxy or GitHub is not reachable from the session, say so plainly and mark criterion 6 accordingly (a small Colab notebook is then allowed, same rules as before: evidence on local disk, gate, `sys.path` line).

5. **Tests**
   - Go: unit tests in `helper/` for exported-entry-point detection, both stopping rules, depth limit, `ROOT_ONLY`, generics.
   - Python unit and contract tests with recorded helper responses (success and every new error status) that do not need Go.
   - Integration (skip with a clear message if Go is missing): every lifting fixture, determinism, the diamond case.
   - Nothing needs the network by default. CI stays green.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Task 0 done (cause of the D1 mismatch reported or honestly "not found"; install check; D4 record corrected; HyDE note). | Report, commits |
| 2 | `lift`, `callers`, `callees` implemented, schemas extended without breaking old recordings. | Tests |
| 3 | Both stopping rules implemented and compared on the fixtures and on D1. | Results doc |
| 4 | Fixture truths verified by running, including `ROOT_ONLY` and the diamond case. | Integration summary |
| 5 | `eval lift` on D1: counts of cases with `derived_symbols`, load failures with reasons, recall and precision with intervals, coverage next to every rate. | Results doc |
| 6 | E1+L vs E1 vs E0 reported (paired), and the D4 ceiling measurement. If the real run could not be done, say so plainly. | Results doc |
| 7 | No analysed code was executed; builds used `GOTOOLCHAIN=local`, `CGO_ENABLED=0`. | Report |
| 8 | All tests pass locally and in CI; no `data/`, caches or third-party source committed. | Printed summaries, `git ls-files` |
| 9 | Report `docs/progress/reports/CP5b_REPORT.md` in the wrapper format; STATUS `AWAITING_REVIEW`. | Files |

## Out of scope

LLM calls, retrieval changes, the agent (CP6), the verifier, real target applications, any use of lifting inside the verdict path.

## Known risks

- Many real modules will fail to load (dependencies, Go version, build tags). That is a measured result; report the load rate and do not hide failures.
- Lifting through dynamic dispatch may add many callers (`ALL`); the depth limit and the `NEAREST` rule exist to keep precision measurable.
- Vulndb `derived_symbols` follow a curator's convention, so a low score may reflect convention, not a bug; show worked examples of both cases.

## Review notes

(The supervising assistant adds notes here if the state becomes `CHANGES_REQUESTED`.)
