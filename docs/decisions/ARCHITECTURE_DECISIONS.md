# Architecture decisions

Each record states the decision, why, what else was considered, and how it will be validated. Status is `Accepted` (adopted for implementation), `Proposed` (adopted provisionally, must be validated), or `Rejected for v1`.

Evidence references point to [feasibility findings](../research/FEASIBILITY_FINDINGS.md).

---

## ADR-001 Go as the first ecosystem

- Status: Accepted
- Decision: Support Go applications and Go advisories only in version 1.
- Why: 77.1% of REVIEWED Go advisories list curated symbols, with a separate `derived_symbols` field and a `vulnerable_at` version (trial 1). Go has mature analysis libraries.
- Alternatives: Rust (21.6% of advisories list affected functions; less mature reachability tooling). Python (no function-level labels found in 7,862 advisories; dynamic language makes call graphs unreliable).
- Consequences: The owner must run Go tooling. Python remains the main language for project code.

## ADR-002 Python orchestration with a Go analysis helper

- Status: Accepted
- Decision: Python for orchestration, LLM calls and evaluation. One small Go binary for program analysis, called as a subprocess with JSON in and out.
- Why: VTA, SSA and the Go package loader exist only in Go. Python is the owner's strongest language.
- Alternatives: All-Go (harder for the owner to maintain). Tree-sitter call graph in Python (name-based; trial 3 showed name-only graphs give false `NOT_REACHABLE`).
- Consequences: A versioned contract between the two languages is required (see interfaces document).

## ADR-003 Own VTA helper as the analysis engine; govulncheck as a reference only

- Status: Proposed
- Decision: Build reachability on `golang.org/x/tools` VTA in our helper. Run govulncheck separately where curated symbols exist, for comparison only.
- Why: We need full call paths for the verifier and results for symbols we recovered ourselves. Using govulncheck as ground truth would be circular because it uses the same analysis family.
- Alternatives: Wrap govulncheck's scanning API. Simpler, but intermediate data may not be exposed in the form we need.
- Validation: In M2, confirm the helper can produce paths for fixture cases. If wrapping govulncheck turns out to provide everything needed, revisit this ADR.

## ADR-004 Two independent reachability methods with abstention on disagreement

- Status: Proposed
- Decision: Combine VTA path search and linker symbol presence. Disagreement gives `CANT_DETERMINE`.
- Why: Trial 3 showed one common method (name-only graph) can silently miss real paths. Two methods with different failure modes make silent misses less likely.
- Risk: The linker is conservative, so disagreement may be frequent on real code, raising abstention.
- Validation: Measure abstention and false `NOT_REACHABLE` on D2 (M2) and D3 (M5).

## ADR-005 One LLM step: closed-set root-cause selection over the full diff

- Status: Proposed
- Decision: The LLM receives the advisory text and the complete non-test diff, and selects among candidate functions extracted by code. No retrieval in the main path.
- Why: All 59 sampled fix diffs fit in context (max about 24k estimated tokens), with a median of 2 changed functions (trial 2). There is nothing meaningful to retrieve or rank.
- Alternatives: RAG over diff chunks (no benefit at this size). Free-text symbol generation (hallucination risk).
- Validation: E1 vs E0 on the post-cutoff split (M4).

## ADR-006 JSON files instead of a database in version 1

- Status: Accepted
- Decision: Store cases, results and reports as JSON / JSON Lines files.
- Why: Hundreds of cases. Files are easy to diff, review and reproduce.
- Alternatives: PostgreSQL (owner has experience). Kept as a later option if cross-run querying becomes painful.

## ADR-007 No vector database, embeddings or reranker in the main pipeline

- Status: Accepted for the main pipeline; embeddings tested in M6 only
- Decision: Main pipeline has no vector store, embeddings or reranker. M6 may test keyword search and hybrid (keyword + embeddings) retrieval on cases without a fix commit, using in-memory search.
- Why: Candidate sets are tiny when a fix commit exists. Retrieval is only plausibly useful when there is no fix commit.
- Alternatives: pgvector index (no scale need). Dedicated vector database (adds infrastructure without benefit).
- Validation: X1 on D4. Enable only if it beats abstention with clear margins.

## ADR-008 No multi-agent architecture

- Status: Rejected for v1
- Decision: No separate cooperating agents.
- Why: The stages are sequential and deterministic except one. Published analysis of multi-agent systems reports minimal gains over single agents and many coordination failure modes. A single tool-using agent is tested in M6 for hard cases only.

## ADR-009 No knowledge graph

- Status: Rejected for v1
- Decision: Relationships between advisories, modules, versions, symbols and commits are stored as plain records.
- Why: The relationships have a fixed shape. A knowledge graph would add technology without new capability. The call graph is a separate thing and is required.

## ADR-010 Deterministic, downgrade-only evidence verifier

- Status: Accepted
- Decision: Every cited symbol, file, line and call edge is checked by code. Failures downgrade to `CANT_DETERMINE`. The verifier never upgrades.
- Why: An LLM cannot be trusted to check its own claims, and path claims must be auditable.

## ADR-011 Deterministic lifting to public entry points

- Status: Proposed
- Decision: After the LLM selects root-cause functions, a call-graph walk inside the vulnerable module finds the nearest exported functions in importable (non-`internal`) packages.
- Why: Trial 2 showed curated labels sometimes name the public caller instead of the changed private helper (Caddy, Helm).
- Validation: E1+L vs E1 in M4. The exact stopping rule (nearest exported caller vs all exported callers) is an open question.

## ADR-012 JSON Schema as the source of truth for data shapes

- Status: Accepted
- Decision: Data shapes are defined by JSON Schema files under `schemas/`, validated in tests with the `jsonschema` package. Both Python and Go code conform to them.
- Alternatives: Python dataclasses or Pydantic only (does not cover the Go side).

## ADR-013 Inlining disabled for linker checks

- Status: Proposed
- Decision: Build with `-gcflags=all=-l` for linker presence.
- Why: An inlined function may vanish from the symbol table even when called, which would cause a false `ABSENT`. Trial 3 used this flag.
- Validation: M1 includes a case where the vulnerable function is small enough to be inlined; compare results with and without the flag and record them.

## ADR-014 Analysis safety for untrusted code

- Status: Accepted
- Decision: Builds use `GOTOOLCHAIN=local` and `CGO_ENABLED=0`. Never run `go generate`, target tests or built binaries. Fixture builds use `GOPROXY=off`.
- Why: Target repositories and fix commits are untrusted input.
