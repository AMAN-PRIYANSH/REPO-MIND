# Risks and open questions

## Open questions

"Decide by" names the latest milestone at which the question must be answered.

| # | Question | Why it matters | Decide by | Current lean |
|---|---|---|---|---|
| Q1 | Where will Claude Code run: the owner's Windows laptop or a cloud environment? Is Go installed there? | M1 integration tests need Go. Windows behaviour is unverified. | Before M1 | Run M1 on the Windows laptop so Windows behaviour is tested early. |
| Q2 | Which LLM provider and model, and what total API budget? | Needed for M4; model cutoff decides the contamination split. | Before M4 | Owner decision. |
| Q3 | Should the repository be renamed from `REPO-MIND` to `vulntrace-ai`? | Clarity for reviewers. GitHub redirects old URLs after renaming. | Before M7 | Owner decision. |
| Q4 | How are entry points defined for libraries without `main`? | Version 1 excludes libraries. | After M5 | Keep excluded. |
| Q5 | How do generic functions and methods appear in `go tool nm` and in vulndb symbol names? | Matching rules for generics are unknown. | M1 (observe) / M2 | Return `UNSUPPORTED_SYMBOL_FORM` until verified. |
| Q6 | Does `go tool nm` print the same symbol format on Windows? | Linker method correctness on the owner's laptop. | M1 | Assumed yes; must be verified. |
| Q7 | How often will VTA and linker disagree on real applications? | High disagreement means high abstention. | M5 | Unknown. Measure. |
| Q8 | Lifting stopping rule: nearest exported caller only, or all exported callers up to a depth? | Affects symbol precision vs recall. | M4 | Measure both. |
| Q9 | What are the licence terms of golang/vulndb data, and can samples be committed here? | Redistribution. | Before M3 | Do not commit vulndb data until checked; reference by commit SHA. |
| Q10 | How will D3 applications fetch their module dependencies? | Needs network and the Go module proxy; affects reproducibility. | Before M5 | Explicit, logged download step, then offline analysis. |
| Q11 | Which `golang.org/x/tools` version is pinned? | Analysis results can change between versions. | M2 | Pin in `helper/go.mod`, record in every result. |
| Q12 | Does the owner have enough time for about 11-16 weeks of work? | Scope control. | Before M1 | M6 can be dropped without harming the core project. |

## Risks

| # | Risk | Type | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| R1 | Owner cannot debug Go helper code | Resource | Medium | High | Keep helper small; every function explained in plain English; contract tests isolate failures. |
| R2 | Ground-truth fixture is wrong | Evaluation | Low | High | Rationale required per case; owner reviews every fixture before M2. |
| R3 | Verdict rule abstains too often on real code | Technical | Medium | Medium | Measure in M5; report honestly; propose rule revisions with evidence. |
| R4 | LLM memorised advisories (contamination) | Evaluation | High for older cases | High | Split by `created` date; headline numbers from post-cutoff only. |
| R5 | Curated labels follow conventions that do not match the LLM's notion of "root cause" | Evaluation | Observed (trial 2) | Medium | Lifting; score against core and core ∪ derived. |
| R6 | Small samples give unstable numbers | Evaluation | High | Medium | Bootstrap intervals; report counts; avoid strong claims. |
| R7 | Large applications exhaust 16 GB RAM during VTA | Resource | Medium | Medium | Choose small-to-medium D3 apps; record peak memory; timeouts. |
| R8 | Building untrusted code causes harm | Security | Low | High | ADR-014 settings; never execute targets; consider a container or VM for D3. |
| R9 | Prompt injection in advisory or commit text | Security | Low | Low | Closed-set selection validated by code; no tools in main LLM step. |
| R10 | API key leaked in logs or commits | Security | Low | High | Keys only from environment; `.env` gitignored; tests check reports contain no key-like strings. |
| R11 | Scope creep (UI, more languages, exploitability) | Delivery | Medium | Medium | Non-goals list; milestone gates. |
| R12 | Fix commits disappear from GitHub | Data | Observed (1 of 60) | Low | Record failures; cache fetched objects. |
| R13 | Over-claiming results in README or interviews | Integrity | Medium | High | Evaluation gates; numbers generated from result files only. |

## Verified facts vs assumptions (summary)

Verified (feasibility findings, 21 Oct 2026):

- Label coverage of Go, Rust and Python advisory databases.
- 59-case comparison of curated symbols with changed functions.
- Linker presence and naive call graph behaviour on five controlled apps (Linux, Go 1.24.7).

Assumed, not yet verified:

- Windows behaviour of `go build` output names and `go tool nm` format.
- That VTA finds paths for the function-value and reflection fixture cases.
- That LLM selection improves on E0.
- That the verdict rule has an acceptable abstention rate on real code.
- That the Go helper fits in memory for chosen D3 apps.
