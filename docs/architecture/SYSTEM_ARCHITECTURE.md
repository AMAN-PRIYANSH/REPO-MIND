# System architecture

This document combines the originally proposed `SYSTEM_ARCHITECTURE.md` and `COMPONENT_DESIGN.md`. They describe the same boundaries, so one document is clearer.

## Design principles

1. **The LLM proposes, code confirms.** The LLM may only choose among candidates that code has already extracted. Every claim in a verdict is checked by deterministic code.
2. **Two independent reachability methods.** A source-level call graph and a linker-presence check. Disagreement leads to `CANT_DETERMINE`, never to a guess.
3. **False `NOT_REACHABLE` is the worst error.** When in doubt, abstain.
4. **Reachability only.** No component outputs an exploitability claim.
5. **Reproducible by default.** Every run records tool versions, inputs, and (for LLM steps) the model ID, prompt hash and raw response.
6. **Nothing optional in the main path.** Retrieval, embeddings and agents exist only as experiments behind flags (milestone 6), and only if measurement justifies them.

## Components

| # | Component | Responsibility | Language | Deterministic? |
|---|---|---|---|---|
| C0 | Case loader | Read a vulndb report: module, packages, `vulnerable_at`, fix-commit URLs, core and derived symbols, `created` date. | Python | Yes |
| C1 | Fix evidence extractor | Fetch fix commits with git. List changed non-test Go functions with old/new line ranges and diff hunks. | Python + Go helper (`funcs` mode) | Yes |
| C2 | Root-cause selector | Read advisory text + the complete non-test diff. Choose which candidate functions contain the root cause. | Python + LLM | **No** (the only LLM decision) |
| C3 | Symbol lifter | Walk callers inside the vulnerable module from root-cause functions to the nearest exported functions in importable packages. | Go helper (`lift` mode) | Yes |
| C4a | Call-graph reachability | Build a VTA call graph of the target application. Search for paths from `main` entry points to target symbols. | Go helper (`reach` mode) | Yes |
| C4b | Linker-presence check | Build the application with inlining disabled, list binary symbols, check if target symbols survive dead-code elimination. | Python calling `go build` and `go tool nm` | Yes |
| C5 | Verdict engine | Combine C4a and C4b results with the agreement rule below. | Python | Yes |
| C6 | Evidence verifier | Check every cited symbol, file, line, and call edge against source and the call graph. Reject unsupported evidence. | Python + Go helper | Yes |
| C7 | Explainer | Turn the verified path into plain-English text. May not add facts. | Python + LLM (optional) | No, but cannot change the verdict |
| C8 | Evaluation harness | Run datasets, compute metrics, write reports. | Python | Yes |

C2 runs only when the case has no curated symbols, or in evaluation when we deliberately hide them.

## Why Python plus a Go helper

- VTA, SSA and the package loader exist only in Go (`golang.org/x/tools`). Python cannot compute an accurate Go call graph.
- Python is the owner's main language and suits orchestration, LLM calls and evaluation.
- The boundary is a command-line contract with JSON on stdout. See [interfaces and contracts](../design/INTERFACES_AND_CONTRACTS.md).

Alternative considered: calling govulncheck as a library. It already does reachability with symbols. It is a useful reference, but it hides intermediate results we need (full call paths for our verifier, results for symbols we recovered ourselves). Decision recorded in [ADR-003](../decisions/ARCHITECTURE_DECISIONS.md).

## Deterministic vs LLM operations

| Operation | Method | Reason |
|---|---|---|
| Parse advisory fields, versions, URLs | Code | Exact data. |
| Fetch fix commit, list changed functions | Code | Exact data. |
| Choose root-cause functions among candidates | **LLM** | Needs reading natural language plus code intent. Closed choice set limits hallucination. |
| Lift to public entry points | Code | Graph walk; trial 2 showed this is a labelling convention, not judgement. |
| Reachability | Code (two methods) | Graph question; must be exact and repeatable. |
| Verdict | Code (rule table) | Must be auditable. |
| Verify evidence | Code | An LLM cannot check itself. |
| Explanation text | LLM (optional) | Presentation only, constrained to verified facts. |

## Verdict rule (proposal, to be validated in milestones 2 and 5)

Per target symbol, the two methods produce:

- C4a (call graph): `PATH_FOUND`, `NO_PATH`, or `ERROR`.
- C4b (linker): `PRESENT`, `ABSENT`, or `ERROR`.

| C4a | C4b | Verifier | Per-symbol result | Reason code |
|---|---|---|---|---|
| `PATH_FOUND` | `PRESENT` | passes | `REACHABLE` | - |
| `PATH_FOUND` | `PRESENT` | fails | `CANT_DETERMINE` | `VERIFIER_REJECTED` |
| `NO_PATH` | `ABSENT` | n/a | `NOT_REACHABLE` | - |
| `NO_PATH` | `PRESENT` | n/a | `CANT_DETERMINE` | `METHOD_DISAGREEMENT` |
| `PATH_FOUND` | `ABSENT` | n/a | `CANT_DETERMINE` | `METHOD_DISAGREEMENT` (flag as anomaly) |
| `ERROR` | any | n/a | `CANT_DETERMINE` | `ANALYSIS_FAILED` |
| any | `ERROR` | n/a | `CANT_DETERMINE` | `ANALYSIS_FAILED` |

Case-level verdict across all target symbols:

- `REACHABLE` if at least one symbol is `REACHABLE`.
- `NOT_REACHABLE` only if every symbol is `NOT_REACHABLE`.
- Otherwise `CANT_DETERMINE`, with all reason codes listed.
- `CANT_DETERMINE` with `NO_TARGET_SYMBOLS` if C0 and C2 produce no symbols.

Open question: the linker is conservative, so `NO_PATH` + `PRESENT` may be common on real applications and push the abstention rate up. This must be measured on real cases (milestone 5) before the rule is considered final. See [risks and open questions](../decisions/RISKS_AND_OPEN_QUESTIONS.md).

## Confidence and uncertainty

- No numeric confidence scores. LLM self-reported confidence is not used in verdicts.
- Uncertainty is expressed only through `CANT_DETERMINE` and its reason codes.
- Each verdict lists which methods agreed, so a reader can see why it was reached.

## Known limits of the analysis methods

Call graph (VTA via golang.org/x/tools):

- All algorithms in the package are documented as unsound in some respect.
- Reflection and `unsafe` can hide edges.
- Function pointers and interfaces are resolved conservatively, which can add infeasible paths.
- Results depend on build configuration (GOOS, GOARCH, build tags). Version 1 analyses the default configuration of the analysis machine only and records it.

Linker presence:

- Binary-level and conservative: code kept for reflection or interface tables may be present but never called.
- Inlining can remove a function's symbol even when it is called. Builds therefore use `-gcflags=all=-l` to disable inlining. This changes the binary compared with production; that is acceptable because we measure reachability, not the shipped artifact.
- Only works for `main` packages.
- Assumption to verify on Windows: `go tool nm` symbol names have the same format on Windows PE binaries as on Linux ELF binaries.

Both methods:

- Analyse one build configuration.
- Say nothing about whether harmful input can reach the function (exploitability).

## Security boundaries

- Target repositories and fix commits are untrusted input. Analysis builds run with `GOTOOLCHAIN=local` and `CGO_ENABLED=0`, and never run `go generate` or the target's tests or binaries.
- LLM inputs (advisory text, commit messages, code comments) may contain prompt-injection text. The LLM output is a closed-set selection that is validated by code, and the LLM has no tools in the main pipeline, so injected instructions cannot trigger actions.
- API keys are read from environment variables and never written to files, logs or reports.
