# CP7b report - Real applications (D3) and demo

Branches: the build session used `claude/sleepy-tesla-smt1xr` and stopped at `AWAITING_ADJUDICATION`; this report was
completed by the scoring session on `claude/eloquent-newton-vr2093` (fast-forwarded onto the first, as CLAUDE.md
section 5 requires). State at the end: **`AWAITING_REVIEW`**.

**Addendum for the scoring session (sections marked "scoring session" are new; the rest is the first session's report,
unchanged except where stated).** The adjudication sheet was filled before this session by two independent Claude
reviewer agents, reconciled by the supervising assistant, with an owner spot-check of 11 path steps; it is **not**
expert human ground truth (STATUS.md handoff note). In this session I ran `python -m vulntrace d3 report`, committed
`docs/results/CP7B_REAL_APPS_RESULTS.md`, and fixed one wrong sentence in the renderer's fixed limitations (section 7,
item 11).

**Headline, as rendered by the unchanged template:** on 5 real Go applications (14 cases), VulnTrace answered 11 and
abstained on 3; adjudication judged **0 of 7 REACHABLE paths correct** (precision 0.00, Wilson 0.00 to 0.35) and found 0
false NOT_REACHABLE among 4. All 7 were judged `INFEASIBLE_PATH`; all 3 `CANT_DETERMINE` were judged `WRONG` (the code
gives a clear NOT_REACHABLE). This is a negative result for the REACHABLE verdicts and is reported as such.

## 1. Environment

**Scoring session (`claude/eloquent-newton-vr2093`), as printed:** `Linux vm 6.18.44-fc-v470 #1 SMP PREEMPT_DYNAMIC @0
x86_64`; `Python 3.13.18` (project `.venv`, `pip install -e ".[dev,db,agent]"`); `go version go1.24.7 linux/amd64`;
`git version 2.43.0`; `Docker version 29.9.2, build a82e528` (not used). `proxy.golang.org` answered 200; `git ls-remote
https://github.com/golang/vulndb HEAD` worked. The scoring step reads only committed files; no Go toolchain, network or
`data/` was needed for it, and no analysis was re-run in this session (the D3 triage and its toolchain, go1.26.10, are
the first session's, recorded below).

**Build session:**

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
| `docs/results/CP7B_REAL_APPS_RESULTS.md` | (scoring session) Results document rendered by `d3 report` from the filled sheet |
| `docs/results/cp7b/adjudication/adjudication.json` | (supervisor, before this session) filled `adjudication`, `by`, `note`, `truth` fields |
| `docs/results/cp7b/adjudication_reviews/{reviewA,reviewB,owner_spotcheck}.json` | (supervisor) the two reviewers' outputs and the owner's spot-check |
| `src/vulntrace/d3/report.py` | (scoring session) fixed limitations text corrected; headline template untouched |
| `tests/unit/test_d3_sheet_score.py` | (scoring session) test that the limitations do not claim human expert truth |
| `docs/progress/STATUS.md` | State, branch, task list, handoff notes |
| `docs/progress/reports/CP7b_REPORT.md` | This report |

## 3. Deliverables

| # | Deliverable | Status |
|---|---|---|
| 1 | Application selection (`d3 select`) | **Done.** Rules written and committed (`0ab9f08`) before any candidate was probed; code committed (`e3fd034`) before its first run. 5 applications, 14 cases. Identical output in three runs; the committed one is from a clean tree (`c8bb2af`) |
| 2 | Triage run (`eval triage --set d3`) | **Done.** 14 of 14 cases triaged from a clean tree (`0a2b5ad`), go1.26.10 recorded in every verdict; results in `docs/results/cp7b/`, every file under 512 KiB |
| 3 | govulncheck reference (optional) | **Done**, labelled not truth: ran on all 5 applications; 9 agree, 2 disagree, 3 not comparable (our CANT_DETERMINE) |
| 4 | Adjudication sheet | **Done (prepared, then filled by others).** 5 Markdown files plus `adjudication.json`; all 14 cases are in the sample (7 REACHABLE, all 4 NOT_REACHABLE, all 3 CANT_DETERMINE, since each is at most 5). The builder stopped at `AWAITING_ADJUDICATION`; the sheet was then filled (see addendum) |
| 5 | Scoring and results document | **Done (scoring session).** Rendered by `python -m vulntrace d3 report` from the filled sheet into `docs/results/CP7B_REAL_APPS_RESULTS.md`; the headline template is the one fixed in `97eec05` before any D3 triage result existed (not edited) |
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

Scoring session (all commands run in this session):

| Command | Printed summary |
|---|---|
| `.venv/bin/python -m vulntrace d3 report` | `wrote /home/user/REPO-MIND/docs/results/CP7B_REAL_APPS_RESULTS.md` |
| `.venv/bin/python -m pytest -q tests/unit tests/contract` (after the renderer fix and the new test) | `849 passed, 10 skipped in 14.64s` |
| `.venv/bin/python -m pytest -q tests/integration` (first attempt, helper modules not in the cache) | `62 passed, 74 skipped in 35.78s`: the Go-helper tests skipped with "vt-helper could not be built (GOPROXY=off ...)"; not a pass of those tests |
| `.venv/bin/python -m vulntrace helper fetch`, then `.venv/bin/python -m pytest -q tests/integration` (system go1.24.7) | `helper modules downloaded`; `134 passed, 2 skipped in 195.01s (0:03:15)` (both skips: opt-in network test) |

Not run: `go test ./...` in `helper/` (the helper was not changed in CP7b; CI runs it).

One local failure on the way, disclosed: the first full unit run failed `test_cp6_notebook.py` with
`ModuleNotFoundError: No module named 'langgraph'` because I had installed only `.[dev]`; after installing the CI
extras `.[dev,db,agent]` it passed. Not a code problem.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Five applications chosen by written rules applied by code before results; rejected candidates listed with reasons | **Met** | Rules `0ab9f08` before code `e3fd034` before the run; `d3_selection.json` lists all 37 candidates with rule and detail (12 `TOO_LARGE`, 1 `TOO_MANY_MAINS`, 2 `NO_ELIGIBLE_ADVISORY`, 1 `NO_TAG_BEFORE_CUTOFF`, 5 `KEPT`, 16 `NOT_EVALUATED_QUOTA_FILLED`); diversity note printed |
| 2 | Triage run on all D3 cases; failures counted with reasons; toolchain recorded | **Met** | `d3_triage.json`: 14/14 triaged, `not_triaged: []`; CANT_DETERMINE reasons counted; helper and linker go1.26.10 in every verdict and in the summary |
| 3 | Adjudication sheet complete and prepared; builder stops at `AWAITING_ADJUDICATION` | **Met** | `docs/results/cp7b/adjudication/`; the first session set STATUS to `AWAITING_ADJUDICATION` |
| 4 | After adjudication: scoring, results document, worked examples, limitations | **Met**, with the caveat that the adjudication is not expert human ground truth | `docs/results/CP7B_REAL_APPS_RESULTS.md` (three worked examples, limitations); section 6a |
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

## 6a. Scoring session results (copied from `docs/results/CP7B_REAL_APPS_RESULTS.md`, produced by `d3 report`)

| Quantity | Value |
|---|---|
| REACHABLE adjudicated | 7 of 7: `INFEASIBLE_PATH` 7, `CORRECT` 0, `WRONG` 0 |
| REACHABLE precision (CORRECT among CORRECT, INFEASIBLE_PATH, WRONG) | 0/7 = 0.00 [0.00, 0.35] |
| Path exists in the code (CORRECT or INFEASIBLE_PATH) | 7/7 = 1.00 [0.65, 1.00] (every step is a real call edge in the call graph, but a branch or dynamic dispatch on the path stops it running) |
| NOT_REACHABLE adjudicated | 4 of 4 `CORRECT`; 0 false NOT_REACHABLE |
| CANT_DETERMINE | 3/14 = 0.21 [0.08, 0.48] of triaged cases; all 3 adjudicated `WRONG` (reading the code gives NOT_REACHABLE) |
| govulncheck (not truth), where both answered | 9/11 agree; the 2 disagreements are the same two REACHABLE cases that were judged `INFEASIBLE_PATH` |
| REACHABLE whose every target is context-only | 1 of 7 (`gitleaks__GO-2025-4020`) |

How to read this, without softening it:

- **The REACHABLE verdicts did not survive adjudication.** Not one of 7 shown paths was judged runnable. Causes named
  in the notes: a dynamic call that never takes the target (cli 5506, Xray 4512, Xray 6061), a branch that is never taken
  with the application's configuration (cli 5052: `doPBMAC1` only for a PBMAC1 MAC OID; cli 5004: the Postgres
  driver is never chosen; Xray 5676: `ListenUnix` passes port 0 so the HTTP/3 branch is skipped; gitleaks 4020: `Rar.FS`
  is never set). Plain call-graph reachability over-approximates, and here the over-approximation produced
  zero confirmed paths among 7.
- **The abstentions were not justified either.** For all 3 `CANT_DETERMINE` cases the reviewers say reading the code
  gives a clear NOT_REACHABLE (a tool error, a linker-presence signal that reflects method retention, and a verifier
  rejection). The system's three NOT_REACHABLE answers that were adjudicated were all right, but they are the easy case
  (the advisory's package is not imported or the function has no caller).
- **Precision is for the path shown, not for the target.** The adjudication judges the path the system displays (changed
  targets first). The reviewers' notes record that for several REACHABLE cases the target is plausibly reachable by a
  different path that was not shown (cli 5506 path 3, Xray 4512, Xray 5676 via TCP with h3, Xray 6061). I did not
  re-adjudicate that; the 0/7 is the number the sheet gives, and "the targets are all unreachable" does not follow
  from it. The renderer's fixed limitations now say so (item 11 below).
- 14 cases from 5 applications, three of them sharing one advisory; the Wilson intervals assume independence and are
  therefore too narrow.

**Who adjudicated, exactly.** Two independent Claude reviewer agents read the source at the pinned versions and agreed
on all 14 adjudications and truths (I compared `reviewA.json`, `reviewB.json` and `adjudication.json` in this session:
identical on every case). Perfect agreement between two reviewers of the same model family is weak evidence of
correctness, because their blind spots are correlated. The supervisor re-read two key claims (gitleaks `rar.go`
`FS != nil`; go-pkcs12 encoders never use PBMAC1) and reconciled. The owner spot-checked 11 path steps of 5 REACHABLE
cases, chosen by a fixed rule before the reviews were seen; the spot-check file records that on one step the owner's
answer was "not written (answered 'yes')" and the supervisor read the line instead. I did not read the analysed source
myself in this session and cannot vouch for any individual adjudication.

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
11. **Renderer limitation text corrected (scoring session).** The fixed limitations in `src/vulntrace/d3/report.py`
    said the truth "was done by the owner and the supervising assistant". That is not what happened (two Claude reviewer
    agents did the reading; see section 6a). I replaced it with a statement of the real method and added one sentence
    that `INFEASIBLE_PATH` judges the shown path, not the target; a unit test guards both. Commit `36b30b4`. The headline template, the scoring and the verdicts were not touched, no case was
    recomputed, and no analysis code changed.
10. **Command names** follow the CP7b specification (`eval triage --set d3`, `demo build`); the interfaces document's
    CLI table said `eval reachability --set d3` and a `demo` that starts a page, and was aligned.

## 8. Blockers and limitations

- **The adjudication is LLM-based (two reviewer agents), reconciled by the supervisor, with a partial owner spot-check;
  it is not expert human ground truth.** I did not independently verify any adjudication by reading source.
- Only the path shown was judged; whether the REACHABLE targets are reachable by some other path was not determined.
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

- Treat the 0/7 as the main finding for the final report. The failure pattern (dynamic dispatch, config-dependent
  branches such as port 0, the MAC OID, the default DB type) suggests a verifier or path-feasibility step, but that is
  a verdict-rule change and out of CP7b's scope; it needs its own checkpoint, measured on cases other than these 14.
- The `CANT_DETERMINE` cases where the code gives a clear NOT_REACHABLE (tool error on a missing target, linker
  PRESENT from method retention) are a separate, cheaper thing to examine.
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

**Scoring session** (branch `claude/eloquent-newton-vr2093`, fast-forwarded onto `claude/sleepy-tesla-smt1xr` at `9461ef5`;
`git log --oneline 9461ef5..HEAD` before the commit that contains this report):

```
01dba52 CP7b: results document CP7B_REAL_APPS_RESULTS.md rendered by code from the filled sheet
36b30b4 CP7b: results limitations state how the adjudication was really done (two Claude reviewers, supervisor, owner spot-check; not human ground truth) and that INFEASIBLE_PATH judges the shown path; headline template unchanged; test
18fab0f CP7b: scoring session starts; STATUS records branch claude/eloquent-newton-vr2093 (fast-forwarded from claude/sleepy-tesla-smt1xr)
```

Pushes: every push of this session succeeded (the first, which recorded the branch, created `origin/claude/eloquent-newton-vr2093`;
the second pushed `01dba52`). The report commit and the STATUS change follow in the next commit. CI: see the STATUS
handoff note, which records the result for the last code commit after it was checked; I did not open a pull request, as
instructed.
