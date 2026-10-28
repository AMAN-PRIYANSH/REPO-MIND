# Interfaces and contracts

This document replaces the originally proposed `API_DESIGN.md`. Version 1 has no hosted or multi-user API (see [project definition](../PROJECT_DEFINITION.md) non-goals); its only UI is a minimal local demo page. Its interfaces are a command-line interface, a Python-to-Go helper contract, model interfaces, LLM and agent-tool contracts, and a verifier contract.

The examples below are interface specifications. They are not implementation code.

## 1. Command-line interface (proposal)

Entry point: `python -m vulntrace <command>`.

| Command | Checkpoint | Purpose |
|---|---|---|
| `doctor` | CP1 | Report Python, Go, Docker and tool versions; list missing prerequisites. Never installs anything. |
| `fixtures score --method linker` | CP1 | Run a method over the synthetic suite and write a scored report. |
| `fixtures score --method vta` / `naive` / `combined` | CP2 | Call-graph method, negative control, and the verdict rule. |
| `dataset build --mode fix` / `--mode release` | CP3 | Build `VulnCase` plus `FixEvidence` (Mode 1) or `ReleaseRange` (Mode 2). |
| `eval symbols --strategy e0` / `id-search` | CP3 | Baselines. |
| `index build --set d4` | CP4 | Chunk, embed and store candidates. |
| `eval retrieval --config <name>` | CP4-CP5 | Retrieval ablations (BM25, dense, hybrid, rerank, HyDE). |
| `eval symbols --strategy llm` / `llm+lift` / `llm-topk` | CP5 | LLM selection in both modes. |
| `eval lift --set d1` / `--set d4-ceiling` | CP5b | Lifting vs `derived_symbols` and E1+L on the committed CP5 selections; caller/callee ceiling on D4. |
| `eval symbols --strategy agent` | CP6 | LangGraph agent. |
| `triage --advisory <ID> --app <dir> [--mode auto/fix/release]` | CP7 | Full pipeline on one case; prints a verdict JSON. Also `--advisory-file`, `--mode targets --target <pkg>:<symbol>`, `--main`, `--max-mains` (default 10), `--k`, `--retriever` (default the fixed retriever), `--lift NEAREST/ALL` (default off), `--mode2-policy` (default `DOWNGRADE`, decided in CP7; see the architecture document), `--no-verify`, `--data-dir`, `--commit`. Evidence is read from `data/` (`dataset materialize`); triage itself never uses the network. |
| `eval triage --set fixtures/d1/d4` | CP7 | E5-lite: fixtures with truth; D1/D4 distributions and coverage only. |
| `d3 select` / `eval triage --set d3` / `d3 sheet` / `d3 report` | CP7b | Real applications: selection by the written rules (`docs/evaluation/D3_SELECTION_RULES.md`), end-to-end triage with the optional govulncheck reference, adjudication sheets, and scoring of the filled sheet. |
| `demo build --verdict <file> / --dir <dir> [--out <file>]` | CP7b | Writes one self-contained static HTML page from verdict files (no server, no network, no scripts). |

Exit codes: `0` success (including `CANT_DETERMINE` verdicts), `2` invalid input, `3` missing prerequisite, `1` unexpected error.

## 2. Python-to-Go helper contract

The Go helper is one binary, `vt-helper`, built from `helper/` in this repository (CP2). Python invokes it as a subprocess.

### Invocation

```
vt-helper <mode> --request <path-to-request.json>
```

- Modes: `funcs` (list functions and line ranges in Go files), `reach` (VTA reachability), `lift` (caller walk to public functions, CP5b), `callers` / `callees` (read-only call-graph queries, CP5b), `edges` (confirm specific call edges for the verifier), `naive` (negative control).
- The request is a JSON file, not command-line flags, so long symbol lists and Windows paths are safe.
- The helper writes exactly one JSON object to stdout. Logs go to stderr only.
- Python enforces a timeout (default 300 s, configurable) and kills the process on expiry; result `ERROR` with code `TIMEOUT`.

### Request example (`reach`)

```json
{
  "contract_version": "1.0",
  "mode": "reach",
  "module_dir": "C:/work/app",
  "main_packages": ["./cmd/server"],
  "targets": [{"package": "github.com/gohugoio/hugo/markup/goldmark", "symbol": "goldmarkConverter.Convert"}],
  "build": {"tags": [], "goos": null, "goarch": null},
  "limits": {"max_paths_per_target": 3, "max_path_length": 40}
}
```

### Success response example

```json
{
  "contract_version": "1.0",
  "ok": true,
  "mode": "reach",
  "toolchain": {"go_version": "go1.24.7", "goos": "windows", "goarch": "amd64",
                "x_tools_version": "v0.xx.x"},
  "results": [
    {"target": {"package": "...", "symbol": "goldmarkConverter.Convert"},
     "result": "PATH_FOUND",
     "paths": [{"entry": {}, "target": {}, "edges": []}]}
  ],
  "stats": {"packages_loaded": 214, "callgraph_nodes": 18342, "duration_ms": 41200}
}
```

### Error response example

```json
{
  "contract_version": "1.0",
  "ok": false,
  "mode": "reach",
  "error": {"code": "LOAD_FAILED", "message": "package ./cmd/server: build constraints exclude all Go files"}
}
```

Error codes: `BAD_REQUEST`, `CONTRACT_MISMATCH`, `LOAD_FAILED`, `TYPE_ERRORS`, `TARGET_NOT_FOUND`, `INTERNAL`, plus Python-side `TIMEOUT` and `HELPER_MISSING`.

### CP5b modes: `lift`, `callers`, `callees`

`contract_version` stays `1.0`: these modes, their fields and their statuses are added; no existing recording changes.

- Loading: with `main_packages` the program is loaded as for `reach` (roots are `main` and `init`). Without it the module is loaded as a **library**: `packages` (default `["./..."]`) are loaded, every function is a node, and a package with its own errors, or importing one that has, is left out and counted in the response's `load` object (`packages_matched`, `packages_skipped`, `first_errors`). If nothing loads the response is `LOAD_FAILED` with the first error line.
- Graph: the same CHA-seeded VTA call graph as `reach`. A closure is folded into its outermost enclosing function. Every edge is `STATIC` or `DYNAMIC`.
- `lift` request: `targets` (the seeds, vulndb symbol form), `lift_rules` (`NEAREST`, `ALL`; default both), `limits.max_lift_depth` (default 10). An **exported entry point** is an exported function, or an exported method of an exported type, in a package that is neither `internal` nor `main`. `NEAREST` stops at the first entry point on each caller path; `ALL` keeps walking up. The walk stays inside the packages the request matched. Per seed: `status` (`LIFTED`, `ALREADY_EXPORTED` - the seed lifts to itself, `ROOT_ONLY` - no exported caller, nothing is invented, `PACKAGE_NOT_IN_PROGRAM`, `ERROR`), and per rule the entries with `depth`, `dynamic` and one shortest example path (entry first, seed last), plus `depth_limit_reached`. Generic seeds are `ERROR` / `UNSUPPORTED_SYMBOL_FORM`; a symbol missing from a loaded package is `TARGET_NOT_FOUND`; a package that was skipped at load time is `PACKAGE_NOT_LOADED`.
- `callers` / `callees` request: `targets`, `limits.max_hops` (default 1), `limits.max_results` (default 200), `external` (also report functions outside the matched packages; default false). Per target: `result` (`FOUND`, `NONE`, `PACKAGE_NOT_IN_PROGRAM`, `ERROR`) and `edges` with `hop`, the call site (file and line) and `kind`; `truncated` says whether `max_results` cut the list.

### Rules

- Python checks `contract_version`; a different major version is a hard error.
- The helper never accesses the network. Module downloads, if needed, happen in a separate, explicit Python step that the user has allowed.
- `TARGET_NOT_FOUND` is not the same as `NO_PATH`. A symbol that does not exist in the loaded program must not become `NOT_REACHABLE`.
- Exception (added after CP2 review): if the target's **package** is not part of the loaded program at all (no package in the build imports it, directly or indirectly), the helper returns `NO_PATH` with `details.package_not_in_program = true`, because no code from that package can run. This is distinct from `TARGET_NOT_FOUND`, which is reserved for a package that is loaded but lacks the symbol (usually a naming problem) and stays an `ERROR`. A `NOT_REACHABLE` verdict still requires the linker to agree (`ABSENT`). Go plugins are out of scope.

## 3. Linker-presence contract (CP1, Python only)

Steps for one main package:

1. `go build -gcflags=all=-l -o <temp binary> <main package>` with environment `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOFLAGS=-mod=mod` only when explicitly allowed, and `GOPROXY=off` for fixtures.
2. `go tool nm <temp binary>`.
3. For each target symbol, match binary symbol names:
   - Function `pkg.Func` → `<pkgpath>.Func`
   - Method `pkg.T.M` → `<pkgpath>.T.M` or `<pkgpath>.(*T).M`
   - Generic functions and methods → open question; treat as `ERROR` with code `UNSUPPORTED_SYMBOL_FORM` until verified.
4. Result `PRESENT` if any pattern matches a text (`T`/`t`) symbol, `ABSENT` otherwise, `ERROR` if the build or nm fails.

The matching rules for plain functions and value/pointer methods were observed in the feasibility trial on Linux. They must be re-checked on Windows (assumption).

## 4. Model interfaces (CP4 onward)

All models sit behind four small Python interfaces. Each has a deterministic **fake** used by every test, and a **real** implementation used only in evaluation runs (Colab or laptop). Tests never import real model libraries.

| Interface | Methods (informal) | Real implementation | Fake |
|---|---|---|---|
| `LLMClient` | `complete(messages, json_schema=None, tools=None) -> response` | HTTP client for an OpenAI-compatible endpoint (Ollama at `http://localhost:11434/v1` by default; URL from config) | Returns scripted responses keyed by input hash, including invalid ones for tests |
| `Embedder` | `embed(texts) -> vectors`, `model_id` | sentence-transformers model chosen in CP4 | Hash-based deterministic vectors |
| `Reranker` | `score(query, texts) -> scores`, `model_id` | sentence-transformers cross-encoder chosen in CP4 | Token-overlap score |
| `VectorStore` | `upsert(chunks)`, `search(vector, filters, k)`, `delete(filters)` | PostgreSQL + pgvector | In-memory brute-force cosine |

Rules:

- No paid endpoint may be configured. The endpoint configuration must reject known paid API hostnames.
- Every real call records model name, digest or version, and settings in the output object.
- Real implementations live in a separate optional dependency group so the base install and tests stay light.

## 5. LLM contracts (CP5 onward)

### Closed-set selection (Mode 1 `LLM_FULL_DIFF`, Mode 2 `LLM_TOPK`)

Input: advisory summary and details; Mode 1 the full non-test diff in numbered hunks; Mode 2 the top-k retrieved candidates with their code. Candidate list with IDs.

Output: JSON only, matching `RootCauseSelection.selected`. Code validates it (see [data model](DATA_MODEL.md)).

### HyDE query rewriting

Input: advisory text. Output: one short hypothetical Go function (plain text) used only as a retrieval query. It is never shown as evidence.

### Agent tools (CP6)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `search_code` | query text, k (1-20, default 10) | ranked candidate IDs with function name, signature and first commit subject | The fixed CP4 retriever (`hybrid:bge-small`, `code+commits`) over this case's candidates; a query longer than 500 characters is cut (recorded) |
| `read_function` | candidate ID | code (doc comment and body), file and lines, commits of the range that changed its file | Only candidates of this case |
| `search_commits` | query text | the 10 best commits of the release range (BM25 over subject and message) with 12-character SHAs | Read-only; ties in history order |
| `show_commit` | SHA or a prefix of at least 7 characters | message, touched candidates, diff of Go files (non-test first, vendored code left out) | Only commits in the release range; diffs precomputed by `agent prepare --diffs` (read-only `git show`) |
| `callers` / `callees` | candidate ID | one-hop neighbours from the helper's VTA call graph of the vulnerable release, with call site and `STATIC`/`DYNAMIC`; neighbours that are candidates show their ID | Ablation arm A3 only; precomputed tables (`agent prepare --graph`); a case without a table runs without these tools |
| `submit_answer` | 1-3 candidate IDs (most likely first) and 1-10 cited items, or `{"abstain": true}` | accepted / rejected | Ends the run. IDs must be in the case's pool; evidence must be IDs or SHAs that appeared in tool outputs. One retry after a rejection, then `INVALID_ANSWER` |

**JSON action protocol (CP6).** The model emits one JSON object per turn, `{"tool": "<name>", "args": {...}}`
(schema `schemas/agent_action.schema.json`), never provider tool calling. Code parses and validates it and never repairs it;
an invalid reply gets one repair turn (`agent_repair_v1`), a second invalid reply in a row ends the run (`INVALID_ACTION`).
A repeated identical call is answered with a note instead of being run again; the next repeat ends the run
(`LOOP_DETECTED`). Every tool output is capped (default 3000 characters) and wrapped as untrusted data. Budgets per case:
8 steps, 80,000 prompt tokens in total, 24,000 per call (below the server's context), 600 s of model plus tool time.

### Rules for all LLM use

- Closed set only; free-text symbol names are ignored.
- Temperature 0 and a fixed seed by default; repeated runs allowed to measure variance.
- Raw responses and traces are cached and stored so metrics can be recomputed without re-running models.
- Prompt templates are versioned files in the repository.

## 6. Verifier contract (CP7)

For each verdict, the verifier checks:

| Check | How |
|---|---|
| Each target symbol exists at the analysed version | `funcs` mode on the module source |
| Each call-site file and line exists | Read the file at the recorded commit |
| Each call edge exists in the call graph | `edges` mode |
| The path starts at a `main` entry and ends at the target | Structural check |
| Every `REACHABLE` has at least one verified path | Structural check |

Any failed check downgrades the affected symbol to `CANT_DETERMINE` with `VERIFIER_REJECTED`. The verifier never upgrades a result.

CP7 implementation (`src/vulntrace/verifier/`):

- The checks run per `per_symbol` entry (one target symbol analysed from one main package). `REACHABLE` entries get all five checks; `NOT_REACHABLE` entries get the existence check; `CANT_DETERMINE` entries are left alone.
- Existence: `go list` locates the target's package in the app (no code runs) and helper `funcs` must declare the symbol in its files. A `NOT_REACHABLE` whose package is not in the program passes only if the package cannot be in the build at all (no module of the app's build list provides it); a package that should exist but is not found (for example a wrong import path) is rejected.
- Call sites: module files are read with `git show <commit>:<path>` when the app is a clean work tree at the recorded commit, otherwise from the analysed tree (an extracted tree is the content of its commit); `$GOROOT/...` and module-cache files from disk. The line must exist and lie inside the caller's declaration (closures, `init#n`, type arguments and forwarder suffixes map to their declaration; a package-variable initializer of `init` lies outside every function). An edge with no call site is accepted only for Go's synthetic edges: a forwarder (`$bound`, `$thunk`, `$wrapper`, `$instwrapper`) calling the method it wraps, or a package initializer calling an initializer.
- Edges: one helper `edges` request per main package with every edge of every path, matched on caller, callee and exact call site.
- A `REACHABLE` entry keeps the first path that passes every check, unchanged, as `verified_path`; with none it becomes `CANT_DETERMINE` / `VERIFIER_REJECTED` and its failed checks are listed in `verifier_failures`. A verifier error (for example `edges` timing out) also rejects. `assert_downgrade_only` checks every output: same entries, same method results and paths, no result stronger.
