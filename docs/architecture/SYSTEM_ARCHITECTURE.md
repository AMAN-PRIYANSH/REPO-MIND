# System architecture

This document combines the originally proposed `SYSTEM_ARCHITECTURE.md` and `COMPONENT_DESIGN.md`.

## Design principles

1. **The LLM proposes, code confirms.** The LLM (or agent) may only choose among candidates that code has extracted. Every claim in a verdict is checked by deterministic code.
2. **Use the simplest method that the data justifies.** Mode 1 needs no retrieval (median 2 candidates). Mode 2 has hundreds to thousands of candidates, so retrieval, a vector store and an agent are used there, each measured against a simpler baseline.
3. **Two independent reachability methods.** A VTA call graph and a linker-presence check. Disagreement gives `CANT_DETERMINE`.
4. **False `NOT_REACHABLE` is the worst error.** When in doubt, abstain.
5. **Reachability only.** No component claims exploitability.
6. **Zero cost.** Free open models only, run locally or on free Colab GPUs, behind interfaces with fake implementations for tests.
7. **Reproducible.** Every run records tool and model versions; model outputs are cached and committed so numbers can be recomputed without re-running models.

## Component map

```
                    ┌──────────────── Mode 1 (fix commit) ────────────────┐
advisory ─► C0 Case │ C1 Fix evidence ─► C2 Root-cause selector (LLM,      │
           loader ──┤                       closed set over full diff)     ├─► C3 Lifter ─► target symbols
                    │                                                      │
                    └──────────────── Mode 2 (no fix commit) ─────────────┤
                      C10 Release-range candidates ─► C11 Indexer ─► C12 Vector store
                      C13 Retriever (BM25 + dense + RRF + reranker + HyDE)
                      C14 Investigation agent (LangGraph, tools) ─► closed-set answer
                                                                            │
target symbols ─► C4a VTA reachability ─┐                                   │
                ─► C4b Linker presence ─┴─► C5 Verdict rule ─► C6 Verifier ─► C7 Explainer ─► verdict JSON / demo
```

## Components

| # | Component | Responsibility | Language | Deterministic? |
|---|---|---|---|---|
| C0 | Case loader | Read a vulndb report: module, versions, `vulnerable_at`, fix-commit URLs, curated symbols, `created` date. | Python | Yes |
| C1 | Fix evidence extractor | Fetch fix commits; list changed non-test functions with line ranges and hunks. | Python + Go helper `funcs` | Yes |
| C2 | Root-cause selector | Advisory + full fix diff → choose candidate IDs. | Python + local LLM | No |
| C3 | Lifter | Walk callers from root-cause functions to nearest exported functions in importable packages. | Go helper `lift` | Yes |
| C4a | VTA reachability | Paths from `main` entry points to target symbols. | Go helper `reach` | Yes |
| C4b | Linker presence | Build with inlining off; check symbol survival with `go tool nm`. | Python + Go toolchain | Yes |
| C5 | Verdict rule | Combine C4a and C4b (rule table below). | Python | Yes |
| C6 | Evidence verifier | Check every symbol, file, line and call edge; downgrade-only. | Python + helper `edges` | Yes |
| C7 | Explainer | Plain-English text from the verified path only. | Python + local LLM (optional) | No, cannot change verdict |
| C8 | Evaluation harness | Datasets, metrics, reports. | Python | Yes |
| C10 | Release-range candidates | Functions changed between `vulnerable_at` and the first fixed release; commit messages in that range. | Python + git + helper `funcs` | Yes |
| C11 | Indexer | Function-level chunks (package, signature, doc comment, body, linked commit messages), embeddings, content hashes. | Python | Yes (given a fixed model) |
| C12 | Vector store | Stores chunks, embeddings and metadata; filtered similarity search. PostgreSQL + pgvector for real runs, in-memory for tests. | Python + PostgreSQL | Yes |
| C13 | Retriever | BM25 and dense search, Reciprocal Rank Fusion, optional cross-encoder reranking, optional HyDE query rewriting. | Python | Yes except HyDE |
| C14 | Investigation agent | LangGraph agent with tools over C12/C13, git and the helper; step and time budgets; must answer from the closed candidate set or abstain. | Python + LangGraph + local LLM | No |

C2 and C14 write the same `RootCauseSelection` object, so everything after them is shared.

## Mode 2 in detail

Retrieval pipeline (C13), each stage switchable for ablations:

1. **Query building.** Advisory summary, details, CWE text, identifiers mentioned. Optional **HyDE**: the local LLM writes a short hypothetical vulnerable Go function; its embedding becomes an extra query.
2. **Sparse search.** BM25 over chunk text, with Go-aware tokenisation (split camelCase and snake_case, keep package paths).
3. **Dense search.** Cosine similarity over chunk embeddings in the vector store, filtered by `(module, from_version, to_version)` and `changed_in_range = true`.
4. **Fusion.** Reciprocal Rank Fusion of sparse and dense lists.
5. **Reranking.** Optional cross-encoder rescoring of the top 50.
6. **Selection.** The local LLM selects candidate IDs from the top k (closed set), or the agent investigates further.

Agent (C14), built with LangGraph:

- State: advisory, candidate pool, evidence notes, step count, budget.
- Tools: `search_code`, `read_function`, `search_commits`, `show_commit`, `callers`, `callees`, `submit_answer`.
- Rules: at most N steps and T seconds (set per run); `submit_answer` only accepts IDs from the candidate pool; any other output is rejected; the full trace is saved.
- The agent never decides reachability. It only produces a `RootCauseSelection`.

Multi-agent variant (CP8, stretch): an investigator agent and a sceptic agent that tries to refute the investigator's choice using the same tools. It is kept only if it beats the single agent on the evaluation set.

## Models (all free)

| Role | Default | Where it runs | Interface |
|---|---|---|---|
| LLM (selection, HyDE, agent, explainer) | Qwen2.5-Coder 7B Instruct via Ollama (to be confirmed by measurement) | Colab free GPU; laptop CPU for demos | `LLMClient` (OpenAI-compatible HTTP) |
| Embeddings | A small open text/code embedding model via sentence-transformers (chosen in CP4) | Colab or laptop CPU | `Embedder` |
| Reranker | A small open cross-encoder (chosen in CP4) | Colab or laptop CPU | `Reranker` |

Each interface has a deterministic fake for tests. Model names, versions and settings are recorded in every result.

## Verdict rule (proposal, validated in CP2 and CP7)

Per target symbol:

| C4a (VTA) | C4b (linker) | Verifier | Result | Reason code |
|---|---|---|---|---|
| `PATH_FOUND` | `PRESENT` | passes | `REACHABLE` | - |
| `PATH_FOUND` | `PRESENT` | fails | `CANT_DETERMINE` | `VERIFIER_REJECTED` |
| `NO_PATH` | `ABSENT` | n/a | `NOT_REACHABLE` | - |
| `NO_PATH` | `PRESENT` | n/a | `CANT_DETERMINE` | `METHOD_DISAGREEMENT` |
| `PATH_FOUND` | `ABSENT` | n/a | `CANT_DETERMINE` | `METHOD_DISAGREEMENT` (anomaly) |
| `ERROR` | any | n/a | `CANT_DETERMINE` | `ANALYSIS_FAILED` |
| any | `ERROR` | n/a | `CANT_DETERMINE` | `ANALYSIS_FAILED` |

Case level: `REACHABLE` if any symbol is `REACHABLE`; `NOT_REACHABLE` only if all are; otherwise `CANT_DETERMINE`. No symbols → `CANT_DETERMINE` / `NO_TARGET_SYMBOLS`.

Open question: the linker is conservative, so `NO_PATH` + `PRESENT` may be common on real code. Measured in CP7.

## Confidence and uncertainty

- No numeric confidence. LLM self-reported confidence is never used.
- Uncertainty is expressed by `CANT_DETERMINE` and reason codes, and by showing which methods agreed.

## Known limits of the analysis methods

- VTA: documented as unsound in some respects; reflection and `unsafe` can hide edges; interface and function-pointer calls are resolved conservatively; one build configuration only.
- Linker presence: conservative, binary-level; inlining can remove symbols, so builds use `-gcflags=all=-l`; `main` packages only; Windows symbol format unverified.
- Retrieval and agent: can miss the right function; the closed-set rule prevents invented names, not wrong choices. Wrong choices are measured, not hidden.
- None of the methods assess exploitability.

## Security boundaries

- Target repositories, advisories and commit messages are untrusted. Builds use `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; never run `go generate`, target tests or binaries.
- Prompt injection: advisory and commit text may contain instructions. The LLM and agent outputs are closed-set selections validated by code; agent tools are read-only and limited to the case's repository and candidate data.
- No API keys exist in this project; any local endpoint URL comes from configuration, never hard-coded secrets.
