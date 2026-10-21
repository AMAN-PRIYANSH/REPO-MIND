# Implementation roadmap and milestone gates

This document combines the originally proposed `IMPLEMENTATION_ROADMAP.md` and `MILESTONE_ACCEPTANCE_CRITERIA.md`, so each milestone's criteria sit next to its scope. Milestone 1 has its own detailed specification: [MILESTONE_1.md](MILESTONE_1.md).

## Gate rule (applies to every milestone)

A milestone is complete only when:

1. Every acceptance criterion below is met, with evidence (commands run and their printed output).
2. The implementer's report lists files changed, deviations from the design, skipped tests with reasons, and open issues.
3. The project owner has reviewed the report and explicitly approved moving on.

Claude Code must stop at the end of each milestone. Approval for one milestone is not approval for the next.

Time estimates assume about 12 hours of work per week by the project owner, with AI assistance. They are rough.

## M0 - Design (this phase)

- Deliverables: the documents in `docs/` and the Round 1 prompt.
- Acceptance: owner has read the documents and resolved or accepted the open questions marked "before M1".

## M1 - Ground truth and linker presence (Round 1)

- Prerequisites: M0 approved. Python 3.11+ available. Go available for integration tests (if not, unit tests still run, and the missing tool is reported as a blocker).
- Deliverables: Python package skeleton, `doctor` command, two JSON Schemas, synthetic fixture suite (at least 12 cases), linker-presence method, `fixtures score --method linker`, tests, results document.
- Dependencies: none.
- Acceptance criteria and test gate: see [MILESTONE_1.md](MILESTONE_1.md).
- Estimate: 1-2 weeks.

## M2 - Go call-graph helper and verdict rule

- Prerequisites: M1 approved; Go available; decision on how `golang.org/x/tools` will be fetched (network access for the Go module proxy).
- Deliverables: `helper/` Go module with `funcs`, `reach` and `edges` modes; Python wrapper; naive name-only call graph as negative control (R1); verdict rule (R4); fixture suite extended to about 25 cases; contract tests with recorded responses.
- Acceptance:
  - Every helper error code has a test.
  - R1, R2, R3, R4 scored on D2 and reported with confusion matrices.
  - R4 produces zero false `NOT_REACHABLE` on D2, or each exception is documented with its cause and a proposed design change (the rule may not be weakened silently to pass).
  - Helper run on the largest fixture stays within documented memory and time.
- Estimate: 2-3 weeks.

## M3 - Advisory dataset and fix evidence

- Prerequisites: M2 approved; network access to GitHub for git fetches; vulndb commit pinned.
- Deliverables: vulndb report reader; `VulnCase` and `FixEvidence` builders; D1 sample of 150 cases; E0 baseline report; re-run of feasibility trial 2 at full size.
- Acceptance:
  - Parser tests cover `/vN` module paths, multi-package reports, missing fields.
  - E0 results reported with counts and intervals, split by `created` date.
  - Any differences from the feasibility numbers are explained.
- Estimate: 2 weeks.

## M4 - LLM root-cause selection and lifting

- Prerequisites: M3 approved; LLM provider, model and budget decided by the owner; API key available as an environment variable.
- Deliverables: LLM client with caching; prompt template v1; output validation; `lift` helper mode; E1 and E1+L reports with contamination split.
- Acceptance:
  - Invalid LLM outputs are rejected in tests using recorded responses.
  - No test calls a live API.
  - Total API spend recorded and within the agreed budget.
  - E1 and E1+L compared with E0 on the post-cutoff split, with intervals.
- Estimate: 2 weeks.

## M5 - End-to-end pipeline, verifier, real applications

- Prerequisites: M4 approved; D3 applications chosen and adjudication notes written by the owner.
- Deliverables: verifier; `triage` command; D3 evaluation; failure gallery.
- Acceptance:
  - Every `REACHABLE` verdict has a verified path.
  - Verifier tests show each check can fail and only downgrades.
  - D3 confusion matrix, abstention rate, and per-case notes reported, including failures.
  - Abstention rate of the verdict rule on real code is reported; if it is so high that the tool is not useful, that is documented and a design revision is proposed.
- Estimate: 2-3 weeks.

## M6 - Experiments on hard cases (optional)

- Prerequisites: M5 approved; owner decides it is worth the time and budget.
- Deliverables: D4 set; X1 (keyword search, then hybrid keyword + embeddings) and X2 (single tool-using agent) strategies writing `RootCauseSelection`; comparison report.
- Acceptance: results reported whether positive or negative; any strategy enabled by default only if it beats the abstaining baseline on D4 with non-overlapping intervals.
- Estimate: 2 weeks.

## M7 - Report and demo

- Deliverables: final results summary, README update with real numbers, short demo script, limitations section.
- Acceptance: a reviewer can reproduce the headline tables from a clean checkout using documented commands and cached LLM responses.
- Estimate: 1-2 weeks.

## Dependency chain

```
M0 → M1 → M2 → M3 → M4 → M5 → (M6 optional) → M7
```

M3 could start in parallel with M2 because it does not depend on the helper, but sequential order is kept to make each review small.
