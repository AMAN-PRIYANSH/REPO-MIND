# Dataset strategy

Four datasets, each answering a different question. Sizes are initial targets for a 4-week build.

## D2 - Synthetic reachability suite (CP1-CP2)

Purpose: reachability methods tested against truth known by construction.

- A Go module under `fixtures/reachability/` with a fake vulnerable package and one `package main` per case. No external dependencies; builds offline.
- At least 12 cases in CP1, about 20 by CP2.

Categories (CP1 must include the first five, which reproduce feasibility trial 3):

| Category | Truth |
|---|---|
| Direct call | REACHABLE |
| Package imported, only a safe function used | NOT_REACHABLE |
| Vulnerable function stored as a function value in a map and called through it | REACHABLE |
| Method calling the vulnerable function, invoked via `reflect` `MethodByName` with a runtime name | REACHABLE |
| Call only inside a function nothing calls (dead code) | NOT_REACHABLE |
| Interface dispatch to an implementation that calls it | REACHABLE |
| Type implements the interface but is never instantiated | NOT_REACHABLE |
| Method value (`f := obj.Method; f()`) | REACHABLE |
| Call inside a goroutine started from `main` | REACHABLE |
| Call inside `init()` of an imported package | REACHABLE |
| Call only in a file excluded by a non-default build tag | NOT_REACHABLE |
| Call only in a `_test.go` file | NOT_REACHABLE |
| Generic function instantiation that calls it | REACHABLE |
| Small vulnerable function that the compiler would inline | REACHABLE |
| Call through an `unsafe` function-pointer trick | REACHABLE (expected hard case) |

Rules: truth follows from the code and is justified in `rationale`; debatable cases are excluded or explained; method outcomes are observed, never pre-written as "expected".

## D1 - Mode 1 symbol identification (CP3, CP5)

- Source: golang/vulndb `data/reports/*.yaml` at a pinned commit.
- Inclusion: `review_status: REVIEWED`, at least one core symbol, at least one GitHub fix commit, not standard library or toolchain. 507 eligible on 21 Oct 2026.
- Sample: 150 advisories, stratified by `created` year, including all advisories created after the evaluated model's cutoff.
- Gold: core `symbols`; secondary: core ∪ `derived_symbols`.
- Owner manually reviews 20 random cases and records agreement with the labels.

## D4 - Mode 2 investigation (CP3-CP6)

- Same eligibility as D1, but the fix commit is hidden. Candidates are the functions changed between the `vulnerable_at` version and the smallest fixed version above it (feasibility trial 5).
- Pseudo-versions must be resolved through the commit hash they contain (5 of 50 failed in the trial without this).
- Sample: 120 advisories, deliberately including every eligible case with more than 100 candidates, because that is where retrieval matters.
- Commit messages in the release range are part of the evidence, so the B-ID baseline and the `search_commits` agent tool are realistic.
- Gold: core symbols present in the candidate set. Cases where no gold symbol is in the set are kept and reported separately as a ceiling limit.

## D3 - Real applications, adjudicated (CP7)

- 5 pairs of (advisory, real Go application at a commit depending on the vulnerable version). Small-to-medium apps that build with `CGO_ENABLED=0` and fit in 16 GB RAM, with a `package main`.
- Mix of expected reachable and expected not reachable.
- Truth: owner adjudication with written reasoning. Two-method agreement or govulncheck agreement is not accepted as truth on its own.
- 5 cases are case studies, not statistics. More can be added after the 4-week build.

## Contamination and splits

- Split D1 and D4 by `source.created` against each model's training cutoff.
- Record the vulndb commit SHA so case lists are reproducible.
- Feasibility check: 19 of 30 sampled GO-2026 advisories were created after 30 June 2026.

## Later additions (after the 4-week build)

- "Patch-absent" mode: search the whole module at `vulnerable_at` (thousands of functions), not just the release diff.
- Rust (RustSec lists affected functions for about 22% of advisories).
- More D3 applications.
