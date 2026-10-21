# Dataset strategy

Four datasets, each answering a different question. Sizes are initial targets; they can grow later.

## D2 - Synthetic reachability suite (milestones 1-2)

Purpose: reachability methods tested against truth known by construction.

- A Go module under `fixtures/reachability/` with a fake vulnerable package and one `package main` per case.
- No external dependencies, so it builds offline.
- Initial target: at least 12 cases in milestone 1, growing to about 25 by milestone 2.

Required categories (milestone 1 must include the first five, which reproduce feasibility trial 3):

| Category | Truth |
|---|---|
| Direct call | REACHABLE |
| Package imported, only a safe function used | NOT_REACHABLE |
| Vulnerable function stored as a function value in a map and called through it | REACHABLE |
| Method that calls the vulnerable function, invoked via `reflect` `MethodByName` with a runtime name | REACHABLE |
| Call exists only in a function nothing calls (dead code) | NOT_REACHABLE |
| Interface method dispatch to an implementation that calls the vulnerable function | REACHABLE |
| Type implements the interface but is never instantiated | NOT_REACHABLE |
| Method value (`f := obj.Method; f()`) | REACHABLE |
| Call inside a goroutine started from `main` | REACHABLE |
| Call inside `init()` of an imported package | REACHABLE |
| Call only in a file excluded by a build tag not set by default | NOT_REACHABLE |
| Call only in a `_test.go` file | NOT_REACHABLE |
| Generic function instantiation that calls the vulnerable function | REACHABLE |
| Call through `unsafe`-based function pointer trick | REACHABLE (expected hard case) |

Rules:

- Truth must follow from the code itself, written in the case's `rationale`.
- If a case's truth is debatable (for example, reachability depends on a runtime input), it is excluded or labelled and explained, not forced.
- Method outcomes are observed and reported. They are never written into the manifest as "expected" in advance.

Limitation: synthetic cases are small and may not represent real code. They test correctness on known patterns, not real-world accuracy.

## D1 - Symbol identification (milestones 3-4)

Purpose: score recovery of vulnerable functions from advisory plus fix commit.

- Source: golang/vulndb `data/reports/*.yaml` at a pinned commit.
- Inclusion: `review_status: REVIEWED`, at least one core `symbols` entry, at least one GitHub fix commit, not the standard library or toolchain.
- Feasibility count: 507 eligible advisories (verified on 21 Oct 2026).
- Initial sample: 150 advisories, stratified by `created` year, with all advisories created after the evaluated model's cutoff included.
- Ground truth: core `symbols`; secondary: core ∪ `derived_symbols`.

Known label issues:

- The Go team labels the nearest public function in some cases rather than the changed private helper (Caddy and Helm examples in the findings). This is a convention, not an error, and motivates lifting.
- Curated labels can still be wrong. The owner manually reviews 20 randomly chosen D1 cases and records agreement.
- Published dataset audits show commit-derived "vulnerable function" labels are often wrong in other datasets (VulValidate: 39/47/65 of 100). Go's curated labels are expected to be better but are not assumed perfect.

## D3 - Real applications, adjudicated (milestone 5)

Purpose: end-to-end verdict quality on real code.

- About 10 pairs of (advisory, real Go application at a commit that depends on the vulnerable module version).
- Selection criteria: small-to-medium applications that build with `CGO_ENABLED=0`, load within the 16 GB memory limit, and have at least one `package main`.
- Aim for a mix: some where reachability is expected, some where only an unrelated part of the dependency is used.
- Truth: the owner adjudicates each case by reading the code and the call path, recording reasoning in a case note. Two-method agreement or govulncheck agreement is not accepted as truth on its own.

Limitation: 10 cases cannot support strong statistical claims. Results are reported as case studies with counts.

## D4 - Hard cases without fix evidence (milestone 6, experimental)

Purpose: test whether retrieval or an agent helps when no fix commit is available.

- REVIEWED advisories with core symbols but no fetchable GitHub fix commit, about 20 cases.
- Only advisory text and the module source at `vulnerable_at` are given to the strategy.
- Scored with the same symbol metrics as D1.

## Contamination and splits

- Split D1 and D4 by `source.created` against each model's cutoff.
- Record the vulndb commit SHA used, so the case list is reproducible.
- Feasibility check: 19 of 30 sampled GO-2026 advisories were created after 30 June 2026, so a post-cutoff split is feasible for models with cutoffs around mid-2026.

## Later additions (not version 1)

- Rust (RustSec lists affected functions for about 22% of advisories).
- UNREVIEWED Go advisories, evaluated qualitatively only, because they have no labels.
- More D3 applications.
