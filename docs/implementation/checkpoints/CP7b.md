# CP7b - Real applications (D3) and demo

- Recommended model: **Sonnet 5.5**, effort **high** (selection scripts, adjudication sheets, report generator; the analysis code already exists)
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 2-3 days of builder work, then the owner's adjudication
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `CP5b.md`, `CP7.md` (**review notes at the end of each bind this checkpoint**), `docs/design/INTERFACES_AND_CONTRACTS.md` (triage CLI, verifier), `docs/design/DATA_MODEL.md`, `docs/evaluation/EVALUATION_PLAN.md` (D3, E5)

## Goal

Run `triage` on real Go applications and let a **human adjudicate the answers**. D1/D4 only measured distributions; D3 is where correctness on real software is judged. Also build the demo: a self-contained page that shows verdict, call path and evidence.

## Findings that shape this checkpoint

- CP7: most D1/D4 modules ended in `CANT_DETERMINE` because they need Go 1.25 or newer or are libraries without a `main` package. D3 must use real `main` applications, and the toolchain must be a newer Go fetched into a scratch directory (as in CP5b), recorded in every result.
- Mode 2 `NOT_REACHABLE` is always downgraded. D3 cases are mostly Mode 1 (fix commit known); Mode 2 runs only where there is no fix commit, and with BM25 unless a dense retriever is available (state which).
- `REACHABLE` means reachable in the call graph, not exploitable. Adjudication judges the path, not the risk.

## Deliverables

1. **Application selection** - `python -m vulntrace d3 select`
   - Five real Go applications (public repositories, pinned to a commit): each has a `main` package, a `go.mod` that requires a module version **inside the affected range** of at least one vulndb advisory with known symbols, builds without cgo, and loads with the toolchain. Aim for about 3-4 advisories per application, 12-20 cases in all.
   - **Selection rules are written down and applied by code before any triage result is seen**; the script prints every candidate application, which rule kept or dropped it, and a diversity note (not five forks of one project). The owner may veto an application; nothing is swapped after results are seen.
   - Committed: a small case list (application repo URL and commit, advisory ID, module version). Not committed: source checkouts, caches.

2. **Triage run** - `python -m vulntrace eval triage --set d3`: verdicts, paths with file and line, verifier outcome, `CANT_DETERMINE` reasons, seconds per case, toolchain and versions. Results to `docs/results/cp7b/`, each file under 512 KiB.

3. **Reference comparison (optional, clearly labelled not truth):** where `govulncheck` (golang.org/x/vuln, fetched from the Go module proxy, source mode, nothing of the application is executed) can run, record its verdict and compare agreement per case. Disagreements are listed, not resolved by assumption.

4. **Adjudication sheet** - `docs/results/cp7b/adjudication/` (a Markdown file per application plus one JSON with blank fields): for every case, the verdict, the call path with file and line links, the code lines at each step, and fields `adjudication` (`CORRECT` / `INFEASIBLE_PATH` / `WRONG` / `CANNOT_JUDGE`), `by`, `note`. All `REACHABLE` cases are adjudicated; for `NOT_REACHABLE` and `CANT_DETERMINE` a stated sample (at least 5 or all, if fewer) is adjudicated by reading the code. The **owner and the supervising assistant fill the sheet**; the builder prepares it and stops at `AWAITING_ADJUDICATION`.

5. **Scoring and results document** (after adjudication, in a second short session): per-verdict counts, `REACHABLE` precision from adjudication, `CANT_DETERMINE` share with reasons, agreement with `govulncheck` where present, worked examples (one `REACHABLE`, one `CANT_DETERMINE`, one disagreement), limitations. Headline sentence fixed in the renderer before results. Rendered by code to `docs/results/CP7B_REAL_APPS_RESULTS.md`.

6. **Demo** - `python -m vulntrace demo build`: one self-contained static HTML page (no server, no network, no external assets) generated from verdict JSON files: verdict, mode, symbols with origin and rank, call path with file and line, verifier checks, limitations. Plain design. A Streamlit page is **not** required (dropped by the roadmap's drop order); do not add it.
   - A short `docs/DEMO.md`: the exact commands to reproduce the demo on one fixture and one D3 case.

7. **Tests**: unit and contract tests for selection rules, sheet generation (no verdict text is invented), scoring from a filled sheet, and the page generator (HTML escapes untrusted text from advisories and code); CI green.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Five applications chosen by written rules applied by code before results; rejected candidates listed with reasons. | Case list, script output |
| 2 | Triage run on all D3 cases; failures counted with reasons; toolchain recorded. | Results JSON |
| 3 | Adjudication sheet complete and prepared; builder stops at `AWAITING_ADJUDICATION`. | Files |
| 4 | After adjudication: scoring, results document, worked examples, limitations. | Results doc |
| 5 | No analysed code executed; `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; no checkouts or caches committed. | Report, `git ls-files` |
| 6 | Demo page builds from verdict files, escapes untrusted text, works offline. | Test, page |
| 7 | All tests pass locally and in CI (check CI on the **last** commit); report `docs/progress/reports/CP7b_REPORT.md`. | Files |

## Out of scope

New models, retrieval or prompt changes, the agent, Streamlit, changing verdict rules or the verifier after seeing D3 results (a bug found is fixed in its own commit, disclosed, and the full D3 run repeated), hosted deployment.

## Known risks

- Many applications will not load; the case list must be chosen so that enough do, and the load rate is reported.
- Adjudication takes human time: keep sheets short and readable, one case per section.
- Selecting applications after seeing results would bias the outcome; the rules and their order are fixed first.

## Review notes

(The supervising assistant adds notes here.)
