# Interfaces and contracts

This document replaces the originally proposed `API_DESIGN.md`. Version 1 has no network API or UI (see [project definition](../PROJECT_DEFINITION.md) non-goals). Its interfaces are a command-line interface, a Python-to-Go helper contract, and an LLM contract.

The examples below are interface specifications. They are not implementation code.

## 1. Command-line interface (proposal)

Entry point: `python -m vulntrace <command>`.

| Command | Milestone | Purpose |
|---|---|---|
| `doctor` | 1 | Report Python, Go and tool versions; list missing prerequisites. Never installs anything. |
| `fixtures score --method linker` | 1 | Run a method over the synthetic suite and write a scored report. |
| `fixtures score --method vta` | 2 | Same, call-graph method. |
| `fixtures score --method combined` | 2 | Both methods plus the verdict rule. |
| `dataset build` | 3 | Build `VulnCase` and `FixEvidence` files from a local vulndb checkout. |
| `eval symbols --strategy e0` / `--strategy llm` / `--strategy llm+lift` | 3-4 | Score symbol identification. |
| `triage --advisory <ID> --app <dir>` | 5 | Full pipeline on one case; prints a verdict JSON. |
| `eval reachability --set d3` | 5 | End-to-end evaluation. |

Exit codes: `0` success (including `CANT_DETERMINE` verdicts), `2` invalid input, `3` missing prerequisite, `1` unexpected error.

## 2. Python-to-Go helper contract

The Go helper is one binary, `vt-helper`, built from `helper/` in this repository (milestone 2). Python invokes it as a subprocess.

### Invocation

```
vt-helper <mode> --request <path-to-request.json>
```

- Modes: `funcs` (list functions and line ranges in Go files), `reach` (VTA reachability), `lift` (caller walk to public functions), `edges` (confirm specific call edges for the verifier).
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

### Rules

- Python checks `contract_version`; a different major version is a hard error.
- The helper never accesses the network. Module downloads, if needed, happen in a separate, explicit Python step that the user has allowed.
- `TARGET_NOT_FOUND` is not the same as `NO_PATH`. A symbol that does not exist in the loaded program must not become `NOT_REACHABLE`.

## 3. Linker-presence contract (milestone 1, Python only)

Steps for one main package:

1. `go build -gcflags=all=-l -o <temp binary> <main package>` with environment `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, `GOFLAGS=-mod=mod` only when explicitly allowed, and `GOPROXY=off` for fixtures.
2. `go tool nm <temp binary>`.
3. For each target symbol, match binary symbol names:
   - Function `pkg.Func` → `<pkgpath>.Func`
   - Method `pkg.T.M` → `<pkgpath>.T.M` or `<pkgpath>.(*T).M`
   - Generic functions and methods → open question; treat as `ERROR` with code `UNSUPPORTED_SYMBOL_FORM` until verified.
4. Result `PRESENT` if any pattern matches a text (`T`/`t`) symbol, `ABSENT` otherwise, `ERROR` if the build or nm fails.

The matching rules for plain functions and value/pointer methods were observed in the feasibility trial on Linux. They must be re-checked on Windows (assumption).

## 4. LLM contract (milestone 4)

### Input to the model

- Advisory summary and description text.
- The complete non-test Go diff, split into numbered hunks.
- The candidate list from `FixEvidence`, with IDs.
- Instructions: select zero or more candidate IDs that contain the root cause; cite hunk IDs; or answer `none_selected`.

### Output from the model

JSON only, matching the `RootCauseSelection.selected` shape. Code validates it as described in [data model](DATA_MODEL.md).

### Rules

- The model chooses from a closed set. Free-text symbol names are ignored.
- Temperature and sampling settings are recorded. Repeated runs are allowed for measuring variance.
- Raw responses are stored so metrics can be recomputed without new API calls.
- API keys come from environment variables. They are never logged or written to results.
- The provider and model are an open decision (see [risks and open questions](../decisions/RISKS_AND_OPEN_QUESTIONS.md)).

## 5. Verifier contract (milestone 5)

For each verdict, the verifier checks:

| Check | How |
|---|---|
| Each target symbol exists at the analysed version | `funcs` mode on the module source |
| Each call-site file and line exists | Read the file at the recorded commit |
| Each call edge exists in the call graph | `edges` mode |
| The path starts at a `main` entry and ends at the target | Structural check |
| Every `REACHABLE` has at least one verified path | Structural check |

Any failed check downgrades the affected symbol to `CANT_DETERMINE` with `VERIFIER_REJECTED`. The verifier never upgrades a result.
