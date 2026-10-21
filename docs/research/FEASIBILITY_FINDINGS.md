# Feasibility findings

This document records what was measured before the design was written, and what was not. Later documents cite it.

All trials ran on 21 October 2026 in a Linux sandbox with Go 1.24.7 and Python 3.13. The trial scripts were delivered separately to the project owner (`vulntrace_trial.zip`) and are not part of this repository yet. Re-running them is part of CP3.

## What was run, and what was not

| Run | Not run |
|---|---|
| Label-coverage statistics over the whole Go vulnerability database | govulncheck itself (building third-party code was blocked in the sandbox) |
| Comparison of curated symbols vs functions changed by the fix commit, 59 advisories | Any VTA / CHA / RTA call graph from golang.org/x/tools |
| Count of functions changed between vulnerable and fixed releases, 45 advisories | Any model of any kind (LLM, embedding, reranker) |
| Controlled 5-app reachability test with known truth | Any LLM call |
| Label-coverage counts for Rust and Python advisory databases | Any embedding, vector search or retrieval experiment |

Nothing in this repository should claim a result for an item in the right-hand column until it is actually run.

## Trial 1 - Label coverage in the Go vulnerability database (verified)

Source: `golang/vulndb`, `data/osv/*.json`, shallow clone on 21 Oct 2026.

| Group | Advisories | List symbols | Have a FIX reference | FIX is a GitHub commit |
|---|---|---|---|---|
| All live (4,710 minus 18 withdrawn) | 4,692 | 19.9% | 52.9% | 41.0% |
| REVIEWED | 1,175 | 77.1% | 81.6% | 49.4% |
| UNREVIEWED | 3,517 | 0.8% | 43.3% | 38.2% |

Usable evaluation cases (REVIEWED, core symbols present, GitHub fix commit, not standard library): **507** (counted from `data/reports/*.yaml`).

Data-format facts (verified by reading the files):

- Each report YAML separates `symbols` (written by the Go security team) from `derived_symbols` (callers computed by tooling). Example: GO-2026-5504 (Hugo) has 3 core symbols and 4 derived symbols.
- Each report has a `vulnerable_at` version, usable as the version to analyse.
- Each report has `source.created`. The `published` and `modified` fields in the repository's `data/osv` JSON are placeholders (`0001-01-01`), so they cannot be used for time splits.

Implication: about 80% of live Go advisories give govulncheck no symbols. Recovering symbols is the real gap this project addresses.

## Trial 2 - Are curated symbols just "the functions the fix changed"? (verified)

Method:

- Random sample (seed 7) of 60 REVIEWED advisories with core symbols and a GitHub fix commit: 30 with GO-2026 IDs, 30 with GO-2023 to GO-2025 IDs.
- 59 succeeded. One failed because the commit was no longer fetchable from GitHub.
- Each fix commit was fetched with git. Non-test Go functions overlapping the changed lines (old and new side) were listed with Go's standard-library parser.
- Predicted symbols = every changed function ("E0 baseline"). Compared by function name against the core `symbols`.

Results (n = 59):

| Measure | Result |
|---|---|
| Mean recall of core symbols | 0.91 |
| Cases where all core symbols appear among changed functions | 52/59 (88%) |
| Mean precision of "every changed function" | 0.70 |
| Exact set match | 27/59 (46%) |
| Changed non-test functions per case | median 2, 90th percentile 10, max 71 |
| Diff size, estimated tokens (characters / 4) | median ~970, 90th percentile ~6,400, max ~24,000 |
| Diffs under 30,000 estimated tokens | 59/59 |
| Advisories in the GO-2026 sample created after 30 June 2026 | 19/30 |

Observed labelling convention (verified by reading the diffs):

- Caddy (GO-2026-4538): the fix changed private helper `matchPatternWithEscapeSequence`; the core symbol is the public caller `MatchPath.Match`.
- Helm (GO-2026-5566): the fix changed `InstallWithOptions` in an `internal` package; the core symbol is `NewRootCmd` in an importable package.

Implications (proposals, not measured):

- The full fix diff fits in an LLM context window for every sampled case, so retrieval over the diff is not needed for cases that have a fix commit.
- The LLM's job is precision (drop refactoring noise from about 2 to 10 candidates), not retrieval.
- "Lifting" a private root-cause function to its nearest public callers should be a deterministic call-graph step, not an LLM step.

Limitations of this trial:

- 59 cases only.
- Sample excludes advisories without a GitHub fix commit, which are the hardest cases.
- Name-level matching may count a coincidental name match. An earlier strict package-path matcher undercounted because of `/v2`, `/v3` module suffixes; the reported numbers use name-level matching.
- Token counts are estimates.

## Trial 3 - Controlled reachability example (verified)

A fake vulnerable library `vulnlib` (vulnerable function `Parse`, safe function `Safe`, method `Impl.Run` that calls `Parse`) and five apps whose truth is known by construction.

Methods compared:

- Import-level: the app imports `vulnlib`.
- Text search: the string `vulnlib.Parse` appears in the app.
- Naive name-only call graph: edges only from call expressions written by name (what many tutorial "code graph" projects build).
- Linker symbol presence: `go build -gcflags=all=-l` (inlining disabled), then `go tool nm`, then check whether `ctrl/vulnlib.Parse` survives dead-code elimination.

| App | Truth | Import-level | Text search | Naive call graph | Linker presence |
|---|---|---|---|---|---|
| Direct call | REACHABLE | correct | correct | correct | correct |
| Only `Safe` used | NOT_REACHABLE | false positive | correct | correct | correct |
| `Parse` stored in a map of function values and called through it | REACHABLE | correct | correct | **false NOT_REACHABLE** | correct |
| `Impl.Run` called via `reflect` `MethodByName` with a runtime name | REACHABLE | correct | false negative | **false NOT_REACHABLE** | correct |
| Call to `Parse` only inside a function nothing calls | NOT_REACHABLE | false positive | false positive | correct | correct |

Observed: in the reflection app the linker kept `vulnlib.Parse`, `vulnlib.Impl.Run` and `vulnlib.(*Impl).Run`.

Implications:

- A name-only call graph produces false `NOT_REACHABLE`, the most dangerous error. It must not be used.
- Linker presence was correct on all five, but it is a conservative, binary-level check. govulncheck's documentation warns binary analysis can report code that is in the binary but unreachable. Five cases do not establish its accuracy.
- Two independent methods (a VTA call graph and linker presence) with abstention on disagreement is the proposed design. It has not yet been tested.

## Trial 5 - Candidate-set size without the fix commit (verified)

Question: if the fix commit is not used, how many functions changed between the vulnerable release and the fixed release?

Method:

- Same 59-advisory sample as trial 2. For each, the `vulnerable_at` version and the smallest `fixed` version above it were mapped to git tags (sub-module prefixes and `+incompatible` suffixes handled).
- Both tags were fetched; non-test, non-vendor Go functions overlapping changed lines were counted.
- 50 advisories attempted, 45 succeeded. The 5 failures were Go pseudo-versions (`v0.0.0-2024...`), which have no git tag. Handling them (resolving the commit hash inside the pseudo-version) is required work for CP3.

Results (n = 45):

| Measure | Result |
|---|---|
| Changed functions between releases | 25th percentile 3, median 13, 75th percentile 102, 90th percentile 364, max 2,558 |
| Releases with 100 or more changed functions | 12/45 |
| Releases with 5 or fewer changed functions | 16/45 |
| Cases where all core symbols are among the changed functions | 32/42 (any core symbol: 40/42) |
| Same 45 cases, functions changed by the fix commit alone | median 2 |

Implications (proposals):

- Without the fix commit, about a quarter of cases become a real ranking problem over 100+ candidates. This is where hybrid retrieval, reranking and an agent can be measured meaningfully (Mode 2).
- Some core symbols are outside the release diff (10/42 not all found). Possible reasons: labels naming public callers (trial 2), or matching limits. CP3 must investigate before the numbers are used as a ceiling.
- A strong, cheap baseline must be included: searching commit messages in the release range for the advisory's CVE or GHSA identifier.

## Trial 4 - Other ecosystems (verified)

| Ecosystem | Advisories | With function-level labels |
|---|---|---|
| Go (REVIEWED) | 1,175 | 77.1% list symbols |
| Rust (RustSec advisory-db) | 1,328 | 287 (21.6%) list affected functions |
| Python (pypa/advisory-database) | 7,862 | none have a `symbols` or `functions` field; 2 have an `imports` field |

Decision: start with Go. Rust is a possible later extension. Python lacks labels for evaluation.

## Facts from published sources (verified, cited)

- govulncheck analyses function-pointer and interface calls conservatively, which may cause false positives; use of `unsafe` may cause false negatives; edges can be missed with `unsafe` and `reflect`. Sources: [govulncheck docs](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck), [vulncheck limitations](https://go.googlesource.com/vuln/+/1a1baf8b415df55cabca81b42f5ceeedc4fb103c/vulncheck/doc.go).
- In binary mode govulncheck may report code that is in the binary but unreachable. Source: [govulncheck docs](https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck).
- In the Go vulnerability database schema, if `symbols` is omitted, any program importing the package is marked vulnerable. Source: [Go vulnerability database schema](https://go.googlesource.com/website/+show/HEAD/_content/doc/security/vuln/database.md).
- golang.org/x/tools provides CHA, RTA, static and VTA call-graph algorithms; its benchmark notes say all are unsound in some respect. Sources: [callgraph package](https://pkg.go.dev/golang.org/x/tools/go/callgraph), [callgraph_test.go](https://go.googlesource.com/tools/+/HEAD/go/callgraph/callgraph_test.go).
- Only 8.5% of CVE descriptions mention the vulnerable function or file; over 26% of vulnerable functions are not among the modified functions of the fix. Source: [VFArchē](https://arxiv.org/pdf/2506.18050).
- An audit of 100 functions from each of BigVul, Devign and DiverseVul found only 39, 47 and 65 truly vulnerable. Source: [VulValidate](https://arxiv.org/pdf/2610.05103).
- npm: 32.49% of flagged packages reached the vulnerable function. Source: [NDSS slides](https://www.ndss-symposium.org/wp-content/uploads/F1902-zhang-slides.pdf). Maven: under 1% had a reachable path. Source: [TU Delft study](https://research.tudelft.nl/en/publications/on-the-effect-of-transitivity-and-granularity-on-vulnerability-pr).
- Multi-agent systems often show minimal gains over single-agent systems; 14 failure modes identified. Source: [Why Do Multi-Agent LLM Systems Fail?](https://nips.cc/virtual/2025/poster/121528).
- Recommended practice: use the simplest solution and add complexity only when needed. Source: [Anthropic, Building effective agents](https://www.anthropic.com/research/building-effective-agents).

## Overlapping work (for honest positioning)

- govulncheck and OSV-Scanner: Go reachability when symbols are known.
- Endor Labs AURI: commercial agents plus deterministic reachability evidence.
- Semgrep Supply Chain: reachability plus data-flow checks on how the function is called.
- Vulnhuntr: LLM-driven iterative call-chain retrieval.
- VFArchē, CleanVul, Bishop Fox patch-diffing study: vulnerable-function identification.

VulnTrace AI does not claim novelty. Its value is a measured, reproducible engineering study.
