# CP7b report - Real applications (D3) and demo

Session branch: `claude/sleepy-tesla-smt1xr`. State at the end of this session: **`AWAITING_ADJUDICATION`**.
Deliverables 1-4, 6 and 7 are done; deliverable 5 (scoring and the results document) has its code, tests and fixed
headline in place, but the results document is rendered only after the owner and the supervising assistant fill
`docs/results/cp7b/adjudication/adjudication.json` (CP7b specification, deliverable 5: "in a second short session").

## 1. Environment

| Item | As printed |
|---|---|
| OS | `Linux vm 6.18.44-fc-v180 #1 SMP PREEMPT_DYNAMIC x86_64`, Ubuntu 24.04.5 LTS; 4 CPUs, 15 GiB RAM |
| Python | `Python 3.13.17` (project venv `.venv`, `pip install -e ".[dev,db,agent]"`, the same extras as CI) |
| Go (system) | `go version go1.24.7 linux/amd64` (`/usr/local/go`); used for the integration tests, as in CI |
| Go (analysis) | `go version go1.26.10 linux/amd64`, fetched as `golang.org/toolchain@v0.0.1-go1.26.10.linux-amd64` from the Go module proxy into the session's scratch directory (sum `h1:5VAGHlY8yl8pTPVSNIez3SNMy6fWabs+QMR25f3oMT0=`, checked by the checksum database), put first on `PATH`; nothing installed system-wide. Same approach and version as CP5b. Helper x/tools stays `v0.42.0` |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.9.2, build a82e528` (not used in CP7b) |
| govulncheck | `golang.org/x/vuln/cmd/govulncheck@v1.9.0` (released 2026-10-11 per the proxy's `.info`), built with go1.26.10 from the module proxy into the cache |

Network checks (through the session's egress proxy):

| Destination | Result |
|---|---|
| `proxy.golang.org` | reachable (200) |
| `sum.golang.org` | reachable (200) |
| GitHub over git (`git ls-remote https://github.com/golang/vulndb HEAD`) | works; plain HTTPS GETs to github.com / codeload.github.com get 403 from the proxy |
| `go.dev`, `vuln.go.dev`, `huggingface.co` | blocked by policy (proxy: `gateway answered 403 to CONNECT`) |

Consequences: the toolchain came from the module proxy, not go.dev; govulncheck used a local database built from the
pinned vulndb snapshot (vuln.go.dev blocked); Mode 2 ranked with BM25 (no dense model; Hugging Face blocked), and the
verdict records this.

## 2. Files changed

| File | Purpose |
|---|---|
| `docs/evaluation/D3_SELECTION_RULES.md` | The written selection rules (A1-A11, V1-V3, case choice), committed before any candidate was probed |
| `docs/evaluation/d3_candidates.json` | The fixed list of 37 candidate applications with domain labels, seed, cutoff and limits |
| `src/vulntrace/d3/__init__.py` | Package |
| `src/vulntrace/d3/select.py` | `d3 select`: the rules as code (pure functions plus a `Probe` for git / Go steps) |
| `src/vulntrace/d3/triage_run.py` | `eval triage --set d3`: evidence per advisory, app trees, the CP7 pipeline unchanged, committed copies with local paths rewritten, provenance on resume |
| `src/vulntrace/d3/govuln.py` | Optional govulncheck reference: build, local OSV database, run (offline), mapping to a per-advisory answer, agreement |
| `src/vulntrace/d3/sheet.py` | `d3 sheet`: adjudication Markdown per application and JSON with blank fields; sample rule; Markdown escaping; source lines and links |
| `src/vulntrace/d3/score.py` | Validation and scoring of a filled sheet; worked-example rule |
| `src/vulntrace/d3/report.py` | Renderer of `docs/results/CP7B_REAL_APPS_RESULTS.md`; headline fixed before any D3 result |
| `src/vulntrace/d3/cli.py` | CLI for `d3 select`, `d3 sheet`, `d3 report` |
| `src/vulntrace/demo/__init__.py`, `page.py`, `cli.py` | `demo build`: one static, script-free, offline HTML page from verdict files |
| `src/vulntrace/__main__.py` | Registers the `d3` and `demo` commands and `--set d3` / `--no-govulncheck` for `eval triage` |
| `src/vulntrace/eval/triage_cli.py` | `cmd_eval_d3`, the `--set d3` branch |
| `src/vulntrace/eval/triage_eval.py` | Bug fix: `replace_root`, local paths replaced only as path prefixes (see section 7) |
| `tests/unit/test_d3_select.py` | Selection rules: ranges, go.mod, tags, toolchain, ordering, case choice, the whole rule pipeline with a fake probe |
| `tests/unit/test_d3_triage.py` | Runner and govulncheck mapping with CP7 fakes; provenance on resume; path rewriting |
| `tests/unit/test_d3_sheet_score.py` | Sample rule, Markdown safety, links, source lines, nothing invented, synthetic edges, context-only flag, validation, scoring, examples, fixed headline, renderer, CLI refusal of an unfilled sheet |
| `tests/unit/test_demo_page.py` | Demo page: escaping of hostile text, no external loads, CSP, anchors, CLI |
| `tests/unit/test_cp7_eval.py` | Regression test for the path-prefix fix |
| `tests/contract/test_d3_committed.py` | The committed D3 files agree with each other, validate against the verdict schema, carry no local or corrupted paths, and the sheet matches the triage file |
| `docs/results/cp7b/d3_selection.json` | Every candidate with the rule that kept or dropped it (produced by `d3 select`) |
| `docs/results/cp7b/d3_cases.json` | The committed D3 case list (application URL, tag, commit, advisory, module versions) |
| `docs/results/cp7b/d3_triage.json` | Compact rows and summary of the D3 triage run, govulncheck reference, provenance |
| `docs/results/cp7b/verdicts/*.json` (14) | Full verdicts, local paths rewritten (`$GOMODCACHE/...`, `$GOROOT/...`, `<local>`) |
| `docs/results/cp7b/adjudication/*.md` (5), `adjudication.json` | The adjudication sheets (blank fields) |
| `docs/DEMO.md` | Exact commands for the demo on one fixture and one D3 case |
| `docs/design/INTERFACES_AND_CONTRACTS.md` | CLI table rows for CP7b aligned with the commands the CP7b specification names |
| `docs/progress/STATUS.md` | State, branch, task list, handoff notes |
| `docs/progress/reports/CP7b_REPORT.md` | This report |

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Application selection (`d3 select`) | **Done.** Rules written and committed (`0ab9f08`) before any candidate was probed; code committed (`e3fd034`) before its first run. 5 applications, 14 cases. Identical output in three runs; the committed one is from a clean tree (`c8bb2af`) |
| 2 | Triage run (`eval triage --set d3`) | **Done.** 14 of 14 cases triaged from a clean tree (`0a2b5ad`), go1.26.10 recorded in every verdict; results in `docs/results/cp7b/`, every file under 512 KiB |
| 3 | govulncheck reference (optional) | **Done**, labelled not truth: ran on all 5 applications; 9 agree, 2 disagree, 3 not comparable (our CANT_DETERMINE) |
| 4 | Adjudication sheet | **Done (prepared).** 5 Markdown files plus `adjudication.json` with blank fields; all 14 cases are in the sample (7 REACHABLE, all 4 NOT_REACHABLE, all 3 CANT_DETERMINE, since each is at most 5). The builder stops at `AWAITING_ADJUDICATION` |
| 5 | Scoring and results document | **Partly done, by design.** Scoring, validation, worked-example rule and renderer exist and are tested; the headline was fixed in code (`97eec05`) before any D3 triage result existed. The document itself is rendered after adjudication (`python -m vulntrace d3 report`, which refuses an unfilled sheet) |
| 6 | Demo (`demo build`, `docs/DEMO.md`) | **Done.** Static page; every command in `docs/DEMO.md` was run in this session (fixture: REACHABLE, verifier PASSED; D3 case `gitleaks__GO-2025-4020`; all 14 D3 verdicts on one page) |
| 7 | Tests | **Done** locally (section 4). CI on the last commit: see section 10 |

## 4. Test evidence

| Command | Printed summary |
|---|---|
| `.venv/bin/python -m pytest -q tests/unit tests/contract` (after the last code change) | `848 passed, 10 skipped in 16.53s` (the 10 skips are the pgvector tests without a database, as in earlier checkpoints) |
| `.venv/bin/python -m pytest -q tests/integration` (system go1.24.7, like CI) | `134 passed, 2 skipped in 282.54s (0:04:42)`; both skips: `opt-in network test (set VULNTRACE_NETWORK_TESTS=1)` |
| `.venv/bin/python -m pytest -q tests/contract/test_d3_committed.py` (after the sheets were committed) | `4 passed in 0.47s` |
| `.venv/bin/python -m pytest -q tests/unit/test_d3_select.py` | `28 passed in 0.11s` |
| `.venv/bin/python -m pytest -q tests/unit/test_demo_page.py` | `5 passed in 0.12s` |
| Demo in a real browser (Playwright, offline context): fixture page, one D3 case, all 14 D3 cases | `{"externalRequests":[],"consoleErrors":[],"mobileHorizontalOverflow":false}` for each |
| `python -m vulntrace triage --advisory-file data/demo/fixture_advisory.json --app fixtures/reachability --mode targets --target vtfixtures/vulnlib:Parse --main ./cmd/direct_call --out data/demo/fixture_direct_call.json` | `REACHABLE PASSED go1.26.10` (14.5 s) |

Not run: `go test ./...` in `helper/` (the helper was not changed in CP7b; CI runs it).

One local failure on the way, disclosed: the first full unit run failed `test_cp6_notebook.py` with
`ModuleNotFoundError: No module named 'langgraph'` because I had installed only `.[dev]`; after installing the CI
extras `.[dev,db,agent]` it passed. Not a code problem.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Five applications chosen by written rules applied by code before results; rejected candidates listed with reasons | **Met** | Rules `0ab9f08` before code `e3fd034` before the run; `d3_selection.json` lists all 37 candidates with rule and detail (12 `TOO_LARGE`, 1 `TOO_MANY_MAINS`, 2 `NO_ELIGIBLE_ADVISORY`, 1 `NO_TAG_BEFORE_CUTOFF`, 5 `KEPT`, 16 `NOT_EVALUATED_QUOTA_FILLED`); diversity note printed |
| 2 | Triage run on all D3 cases; failures counted with reasons; toolchain recorded | **Met** | `d3_triage.json`: 14/14 triaged, `not_triaged: []`; CANT_DETERMINE reasons counted; helper and linker go1.26.10 in every verdict and in the summary |
| 3 | Adjudication sheet complete and prepared; builder stops at `AWAITING_ADJUDICATION` | **Met** | `docs/results/cp7b/adjudication/`; STATUS set to `AWAITING_ADJUDICATION` |
| 4 | After adjudication: scoring, results document, worked examples, limitations | **Not met yet (by design)** | Needs the filled sheet; code and tests are ready (`d3 report`) |
| 5 | No analysed code executed; `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; no checkouts or caches committed | **Met** | Trees come from `git archive` (no hooks); dependencies from `go mod download` with `-mod=readonly`; main packages compiled only to a temp file that is deleted (selection A10) and by the linker method (`go tool nm` only); govulncheck in source mode, `GOPROXY=off`. Every verdict's `toolchain.env` shows `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOPROXY=off`. `git ls-files` lists 498 files; none under `data/`, no `.gz`, binaries, module caches or venv |
| 6 | Demo page builds from verdict files, escapes untrusted text, works offline | **Met** | `tests/unit/test_demo_page.py` (hostile advisory, symbol and path text; no script, link, img or src; CSP `default-src 'none'`); Playwright check above |
| 7 | All tests pass locally and in CI (last commit); report | **Met locally; CI see section 10** | Section 4; this report |

## 6. Results (copied from `docs/results/cp7b/d3_triage.json` and `d3_selection.json`; not adjudicated)

These are system outputs, not correctness. Correctness comes from the adjudication.

Selection: 37 candidates, seeded order; 5 kept, all from different owners and domains: `wagoodman/dive` v0.13.1
(container-tools), `sosedoff/pgweb` v0.17.0 (web-app), `gitleaks/gitleaks` v8.30.0 (security-tools),
`smallstep/cli` v0.29.0 (pki-acme), `XTLS/Xray-core` v25.12.8 (network-tunnel). Load rate: all 6 candidates that
reached the load step (A8) loaded and every main package of the 5 kept built. Run time 14 m 49 s (first run, cold
caches), 5 m 26 s and 5 m 31 s (warm).

| Verdict | Cases |
|---|---|
| REACHABLE | 7 |
| NOT_REACHABLE | 4 |
| CANT_DETERMINE | 3 (ANALYSIS_FAILED 1, METHOD_DISAGREEMENT 1, VERIFIER_REJECTED 1) |
| not triaged | 0 |

Modes: FIX 13, RELEASE 1 (`dive__GO-2026-4610`: fix diff EMPTY; BM25 because no embedder). The Mode 2 policy changed
nothing (pre-policy verdicts are identical). Verification: PASSED 11, FAILED 3 (5 entries downgraded; every one is a
NOT_REACHABLE entry whose target is not declared at the application's dependency version, each checked by hand
against the module cache: all 5 correct, no false rejection). Seconds per case: p50 42.5, p95 80.4, max 116.5,
total 707.0; the whole run 14 m 6 s.

| case | app tag | module@version | mode | verdict | reasons | per-symbol | govulncheck | agreement | s |
|---|---|---|---|---|---|---|---|---|---|
| dive__GO-2026-4610 | v0.13.1 | github.com/docker/cli@v28.0.2+incompatible | RELEASE | CANT_DETERMINE | VERIFIER_REJECTED | {'CANT_DETERMINE': 1, 'NOT_REACHABLE': 4} | NOT_REACHABLE (MODULE) | NOT_COMPARABLE | 53.6 |
| dive__GO-2026-5841 | v0.13.1 | github.com/klauspost/compress@v1.18.0 | FIX | NOT_REACHABLE | - | {'NOT_REACHABLE': 1} | NOT_REACHABLE (MODULE) | AGREE | 26.7 |
| dive__GO-2025-3900 | v0.13.1 | github.com/go-viper/mapstructure/v2@v2.2.1 | FIX | CANT_DETERMINE | ANALYSIS_FAILED | {'CANT_DETERMINE': 3, 'NOT_REACHABLE': 26} | NOT_REACHABLE (PACKAGE) | NOT_COMPARABLE | 12.6 |
| pgweb__GO-2025-4188 | v0.17.0 | github.com/sirupsen/logrus@v1.9.0 | FIX | CANT_DETERMINE | METHOD_DISAGREEMENT | {'CANT_DETERMINE': 5, 'NOT_REACHABLE': 5} | NOT_REACHABLE (PACKAGE) | NOT_COMPARABLE | 29.2 |
| gitleaks__GO-2026-5841 | v8.30.0 | github.com/klauspost/compress@v1.17.11 | FIX | NOT_REACHABLE | - | {'NOT_REACHABLE': 2} | NOT_REACHABLE (PACKAGE) | AGREE | 31.1 |
| gitleaks__GO-2025-4020 | v8.30.0 | github.com/nwaples/rardecode/v2@v2.1.0 | FIX | REACHABLE | - | {'CANT_DETERMINE': 9, 'NOT_REACHABLE': 2, 'REACHABLE': 1} | NOT_REACHABLE (PACKAGE) | DISAGREE | 34.1 |
| cli__GO-2026-5506 | v0.29.0 | go.opentelemetry.io/otel@v1.38.0 | FIX | REACHABLE | - | {'NOT_REACHABLE': 8, 'REACHABLE': 4} | REACHABLE (SYMBOL) | AGREE | 116.5 |
| cli__GO-2026-5052 | v0.29.0 | software.sslmate.com/src/go-pkcs12@v0.6.0 | FIX | REACHABLE | - | {'REACHABLE': 1} | NOT_REACHABLE (PACKAGE) | DISAGREE | 80.4 |
| cli__GO-2026-4503 | v0.29.0 | filippo.io/edwards25519@v1.1.0 | FIX | NOT_REACHABLE | - | {'NOT_REACHABLE': 1} | NOT_REACHABLE (PACKAGE) | AGREE | 42.5 |
| cli__GO-2026-5004 | v0.29.0 | github.com/jackc/pgx/v5@v5.7.5 | FIX | REACHABLE | - | {'REACHABLE': 4} | REACHABLE (SYMBOL) | AGREE | 68.9 |
| Xray-core__GO-2026-5676 | v25.12.8 | github.com/quic-go/quic-go@v0.57.1 | FIX | REACHABLE | - | {'CANT_DETERMINE': 3, 'NOT_REACHABLE': 4, 'REACHABLE': 2} | REACHABLE (SYMBOL) | AGREE | 74.7 |
| Xray-core__GO-2026-4512 | v25.12.8 | github.com/refraction-networking/utls@v1.8.1 | FIX | REACHABLE | - | {'NOT_REACHABLE': 2, 'REACHABLE': 1} | REACHABLE (SYMBOL) | AGREE | 49.7 |
| Xray-core__GO-2026-5841 | v25.12.8 | github.com/klauspost/compress@v1.17.4 | FIX | NOT_REACHABLE | - | {'NOT_REACHABLE': 3} | NOT_REACHABLE (MODULE) | AGREE | 31.5 |
| Xray-core__GO-2026-6061 | v25.12.8 | google.golang.org/grpc@v1.77.0 | FIX | REACHABLE | - | {'CANT_DETERMINE': 7, 'NOT_REACHABLE': 76, 'REACHABLE': 28} | REACHABLE (SYMBOL) | AGREE | 55.5 |

govulncheck reference (not truth): agreement 9 / disagreement 2 / not comparable 3. Both disagreements are ours
REACHABLE vs govulncheck package level (`gitleaks__GO-2025-4020`, `cli__GO-2026-5052`): the fix changed a function
that is reachable, but govulncheck finds none of the advisory's listed symbols called. Which is right is for the
adjudication, not for me to assume.

Observations for the reviewers (facts, not judgements):

- **One REACHABLE rests only on a context-only symbol.** In `gitleaks__GO-2025-4020` the only reachable target,
  `rardecode/v2.FileSystem`, is `context_only: True`: none of its lines changed in the fix; it is a candidate because
  git's diff context touched it (CP7's Mode 1 keeps such candidates, as E0 measured them, and flags them). In the
  other 6 REACHABLE cases at least one reachable target was really changed. The sheet shows the flag; the renderer
  counts such cases.
- `GO-2026-5841` (klauspost/compress) appears in 3 applications (dive, gitleaks, Xray-core); those cases are not
  independent.
- Analysed `main` packages include an example program (`pgweb/config/examples/connect_backend_go`) and two
  developer tools (`xray-core/infra/vformat`, `infra/vprotogen`), as rule A9 says (all main packages). A path from
  such a `main` is a real call-graph path but not the product binary; the sheet names the `main` of every path.
- `Xray-core__GO-2026-6061.json` is 510,242 bytes, under the 524,288-byte limit but close to it (111 per-symbol
  entries over 3 main packages).

## 7. Design deviations

1. **Toolchain go1.26.10, not CI's 1.24.** As CP7's review asked, D3 used a newer Go fetched into a scratch
   directory (CP5b approach), recorded in every verdict. The D3 run is therefore not reproducible inside CI.
2. **V1 requires a GitHub fix commit** (the CP3 D1 rule), stated in the rules document before probing. Reason: both
   Mode 1 and Mode 2 find the repository through it. Effect: most `golang.org/x/...` advisories are excluded.
3. **Version check uses the build list as well (V3)**, stricter than the specification's "go.mod requires a
   version": the go.mod version and the `go list -m` version agreed for every selected case.
4. **go.mod is never changed** (`-mod=readonly`, `go mod download`), unlike D1/D4's `go mod tidy -e`: D3 must
   analyse the dependency versions the application pins.
5. **govulncheck database:** a flat directory of the pinned snapshot's `data/osv/*.json`, which govulncheck v1.9.0
   indexes itself (its client's "hybrid source", a documented-in-code but hidden feature), because `vuln.go.dev` is
   blocked. Advantage: the reference uses exactly the same advisories as the pipeline.
6. **Sheet field `truth`** (optional, NOT_REACHABLE and CANT_DETERMINE only) added to the specification's
   `adjudication` / `by` / `note`, so a reviewer can record what reading the code says.
7. **Sample:** the rule (all REACHABLE; of NR and CD all if at most 5, else 5 seeded) was fixed in code before the
   run; it selected all 14 cases.
8. **Changes after the triage results were seen, before any adjudication** (presentation only; no verdict rule,
   verifier, model, retrieval or prompt changed): (a) context-only targets are flagged in the sheet and paths of
   really-changed targets are listed first, so "judge the first path shown" falls on a changed function where one
   exists; (b) the renderer counts REACHABLE cases that rest only on context-only targets; (c) advisory summaries
   are copied into the sheets from the vulndb snapshot; (d) the diversity note no longer claims "none is a fork",
   which the code does not check (this one was before the triage run).
9. **Bugs found and fixed, each in its own commit:** (a) `b78822c`: the shared CP7 function that rewrites local paths
   in committed files used a plain string replace; with `HOME=/root` it turned `internal/cmd/root.go` into
   `internal/cmd<local>.go` in 3 committed D3 verdicts and the triage file. It now replaces only path prefixes, with a
   regression test; CP7's committed files contain only true prefixes, so they are unaffected. (b) `f9d85de`: Go's
   synthetic edges (`init`->`init`, a `$wrapper`) have an empty call site and were shown as `:0`; they are now
   labelled as synthetic edges. Neither bug touched the analysis, so no case was recomputed: the committed D3 files
   were re-written from the stored raw verdicts (`34ae419`), and `d3_triage.json` now records
   `verdict_provenance` (`repo_commits: ["0a2b5ad"]`, 0 cases run in the re-writing invocation, 14 resumed) next to
   the re-writing invocation's own environment (`f9d85de`, clean).
10. **Command names** follow the CP7b specification (`eval triage --set d3`, `demo build`); the interfaces document's
    CLI table said `eval reachability --set d3` and a `demo` that starts a page, and was aligned.

## 8. Blockers and limitations

- **Adjudication is not done** (the owner's and supervisor's step); criterion 4 waits for it.
- Five applications and 14 cases are case studies; cases of one application are dependent.
- Mode 1 targets come from the fix commit's parent; when the application's dependency version differs, targets can
  be missing (dive GO-2025-3900: 3 of 29 targets missing, so CANT_DETERMINE) or differ from the code the application
  really runs.
- Source links in the sheets are best effort and were **not checked** (plain HTTPS to github.com is blocked here); the
  code lines shown next to each step are read from the analysed files and are authoritative.
- Mode 2 (1 case) ran with BM25, not the intended `hybrid:bge-small` (Hugging Face blocked); recorded in the verdict.
- The linker and govulncheck analyse linux/amd64, `CGO_ENABLED=0`, no build tags.
- Not run locally: helper `go test ./...` (helper unchanged; CI runs it).

## 9. Suggestions for the next checkpoint (not implemented)

- Second short session: fill the sheet, `python -m vulntrace d3 report`, commit the document; check that the
  headline renders unchanged.
- Decide whether context-only candidates should stay deciding in Mode 1 (one D3 REACHABLE rests only on one); this
  needs a measured reason, not D3 tuning.
- If D3 is extended, raise A6 (150 `require` entries excluded 12 of 21 evaluated candidates, caddy at 151) as a new,
  written rule before probing, and consider analysing only the product `main` packages.
- Consider a size cap or compaction for very large committed verdicts (one is at 510 KB of 512 KiB).

## 10. Git

Branch `claude/sleepy-tesla-smt1xr`. Commits (`git log --oneline main..HEAD`, before this report's commit):

```
b7e79a0 CP7b: adjudication sheets prepared (14 of 14 cases; advisory summaries from vulndb; context-only targets flagged and listed after changed ones); docs/DEMO.md with commands verified on a fixture and a D3 case
34ae419 CP7b: committed D3 files re-written from the stored verdicts with the path fix (no case recomputed; verdicts from 0a2b5ad); contract test rejects corrupted placeholders
f9d85de CP7b fix: Go's synthetic edges (empty call site) are labelled as such in sheets, report and demo; a resumed d3 run records where its verdicts came from
b78822c CP7b fix: local paths in committed files are replaced only as path prefixes
1a007d5 CP7b: D3 triage results from a clean tree (0a2b5ad, go1.26.10): 14/14 triaged, 7 REACHABLE, 4 NOT_REACHABLE, 3 CANT_DETERMINE; govulncheck reference 9 agree, 2 disagree; contract test for committed D3 files
0a2b5ad CP7b: D3 selection result from a clean tree (5 apps, 14 cases; identical in three runs); STATUS
c8bb2af CP7b: diversity note states only what the code checks (owner, domain), not fork relations
97eec05 CP7b: adjudication sheet generator (sample rule fixed), scoring of a filled sheet, results renderer with the headline fixed before any D3 triage result; tests
a729b7e CP7b: eval triage --set d3 runner (CP7 pipeline unchanged; evidence per advisory; sanitised committed verdicts) and the govulncheck reference (v1.9.0, offline, pinned vulndb OSV); tests
10a4aeb CP7b: demo build - one offline HTML page from verdict files (no scripts, CSP default-src 'none', every value escaped); tests
e3fd034 CP7b: d3 select - the written selection rules applied by code (A1-A11, V1-V3), unit tests with a fake probe
0ab9f08 CP7b: D3 selection rules and candidate list, fixed before any candidate is probed
09a01fe CP7b: start; STATUS IN_PROGRESS on claude/sleepy-tesla-smt1xr, task list
```

Every push succeeded. CI (GitHub Actions) was green on every completed run of this branch up to `f9d85de` (runs 126-136);
the runs for `34ae419` and `b7e79a0` were still in progress when this report was written, and the result for the
final commit is recorded in STATUS.md's handoff notes after it was checked. No pull request was opened (the session
wrapper says the supervising assistant handles merging).
