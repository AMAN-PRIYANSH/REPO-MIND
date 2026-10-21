# Architecture decisions

Each record states the decision, why, what else was considered, and how it will be validated. Status is `Accepted`, `Proposed` (adopted provisionally; must be validated), or `Rejected`.

Evidence references point to [feasibility findings](../research/FEASIBILITY_FINDINGS.md).

---

## ADR-001 Go as the first ecosystem

- Status: Accepted
- Decision: Go applications and Go advisories only.
- Why: 77.1% of REVIEWED Go advisories list curated symbols, with separate `derived_symbols` and a `vulnerable_at` version (trial 1). Mature analysis libraries.
- Alternatives: Rust (21.6% labelled), Python (no function-level labels found).

## ADR-002 Python orchestration with a Go analysis helper

- Status: Accepted
- Decision: Python for orchestration, retrieval, models, agent and evaluation; one small Go binary for program analysis, called as a subprocess with JSON in and out.
- Why: VTA, SSA and the Go package loader exist only in Go. Python is the owner's strongest language and has the retrieval and agent ecosystem.
- Alternatives: tree-sitter call graph in Python (name-based; trial 3 showed false `NOT_REACHABLE`).

## ADR-003 Own VTA helper; govulncheck as reference only

- Status: Proposed
- Decision: Reachability on `golang.org/x/tools` VTA in our helper; govulncheck run separately for comparison where curated symbols exist.
- Why: Full paths are needed for the verifier, and recovered symbols must be checkable. Using govulncheck as truth would be circular.
- Validation: CP2.

## ADR-004 Two independent reachability methods with abstention

- Status: Proposed
- Decision: VTA path search plus linker presence; disagreement gives `CANT_DETERMINE`.
- Why: Trial 3 showed a common method silently missing real paths.
- Risk: conservative linker may raise abstention. Measured in CP2 and CP7.

## ADR-005 Mode 1 uses closed-set selection over the full diff, no retrieval

- Status: Proposed
- Decision: With a fix commit, the LLM receives the advisory and the complete non-test diff and selects candidate IDs.
- Why: All 59 sampled fix diffs fit in context (max about 24k estimated tokens); median 2 changed functions (trial 2).
- Validation: E1 vs E0 (CP5).

## ADR-006 JSON files for cases and results

- Status: Accepted
- Decision: Cases, verdicts, runs and traces as JSON / JSON Lines.
- Why: Hundreds of records; easy to diff, review and reproduce.

## ADR-007 Mode 2 uses advanced retrieval with PostgreSQL + pgvector

- Status: Proposed
- Decision: Function-level chunks with metadata; BM25 + dense search fused with RRF; optional cross-encoder reranking and HyDE; chunks and embeddings stored in PostgreSQL + pgvector with metadata filters; in-memory backend with the same interface for tests.
- Why: Without the fix commit, candidate sets reach hundreds to thousands of functions (trial 5: 12/45 releases with 100+, max 2,558). Ranking is a real problem. pgvector keeps vectors next to relational metadata (module, version, package, hash, model) that every query filters on; PostgreSQL 16 is preinstalled in Claude Code cloud sessions and familiar to the owner.
- Alternatives: dedicated vector databases (Qdrant, Milvus, Chroma) add a second datastore without a capability we need; pure in-memory search is fine for one case but does not show versioned indexing.
- Validation: Q1-Q5 ablations vs B-ID baseline (CP4-CP5). Every component must earn its place; any that does not is reported as such.

## ADR-008 Single LangGraph agent for Mode 2; multi-agent only as a measured stretch

- Status: Proposed (single agent), Stretch (multi-agent)
- Decision: One tool-using agent built with LangGraph for Mode 2 investigation, with step and time budgets and closed-set answers. A two-agent investigator + sceptic variant is tested in CP8 only if time allows.
- Why: Release ranges include commit messages, callers and diffs that a fixed pipeline cannot follow adaptively; an agent can. Published analysis of multi-agent systems reports minimal gains and many coordination failures, so multi-agent is tested, not assumed.
- Alternatives: no agent (kept as the baseline S1); multi-agent by default (rejected).

## ADR-009 No knowledge graph

- Status: Rejected
- Decision: Relationships between advisories, modules, versions, symbols and commits are plain records.
- Why: Fixed-shape relationships; a knowledge graph would add technology without capability. The call graph is separate and required.

## ADR-010 Deterministic, downgrade-only evidence verifier

- Status: Accepted
- Decision: Every cited symbol, file, line and call edge is checked by code; failures downgrade to `CANT_DETERMINE`.

## ADR-011 Deterministic lifting to public entry points

- Status: Proposed
- Decision: After root-cause selection, a call-graph walk finds the nearest exported functions in importable packages.
- Why: Curated labels sometimes name the public caller (trial 2: Caddy, Helm).
- Validation: E1+L vs E1 (CP5). Stopping rule is an open question.

## ADR-012 JSON Schema as the source of truth for data shapes

- Status: Accepted

## ADR-013 Inlining disabled for linker checks

- Status: Proposed
- Decision: Build with `-gcflags=all=-l`.
- Validation: CP1 inlining fixture, run with and without the flag.

## ADR-014 Analysis safety for untrusted code

- Status: Accepted
- Decision: `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; never run `go generate`, target tests or binaries; fixture builds use `GOPROXY=off`; agent tools are read-only.

## ADR-015 Zero cost: free open models behind interfaces

- Status: Accepted
- Decision: All models are free and open, served through an OpenAI-compatible endpoint (Ollama by default) or loaded locally (sentence-transformers). Every model sits behind an interface with a deterministic fake for tests. Paid API hosts are rejected by configuration.
- Why: Owner constraint: no spending. Interfaces also make the system model-agnostic, which is good design regardless.
- Default LLM: a 7B-class open coding model (Qwen2.5-Coder 7B Instruct proposed); confirmed or replaced by measurement in CP5.

## ADR-016 Real model runs on Google Colab, code built in Claude Code cloud sessions

- Status: Accepted
- Decision: Claude Code writes and tests code in cloud sessions with fakes. Real model evaluations run in Colab notebooks (free GPU) that install this repository and write result files, which are then committed.
- Why: Cloud sessions cannot download models by default (Hugging Face is not on the default network allowlist) and have no GPU; Colab has a free GPU. The owner's laptop has no dedicated GPU.
- Risk: Colab GPU availability and session limits. Mitigation: resumable runs with caching; small model fallback.
