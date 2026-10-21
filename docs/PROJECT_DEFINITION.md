# Project definition

## Problem statement

Dependency scanners report every known vulnerability in every dependency version a project uses. Most of those reports do not matter, because the application never calls the vulnerable code.

Published studies show how large the gap is (verified, cited in [feasibility findings](research/FEASIBILITY_FINDINGS.md)):

- In npm, only 32.49% of flagged packages actually reached the vulnerable function.
- In Maven, under 1% of packages had a reachable call path to vulnerable code in their dependencies.

Go already has a reachability tool, govulncheck. But it can only check reachability when the advisory names the vulnerable functions ("symbols"). In the Go vulnerability database, about 80% of live advisories list no symbols (verified, see findings). Without symbols, any program that imports the module is treated as affected.

VulnTrace AI targets that gap:

1. Recover the vulnerable function from the advisory and fix commit.
2. Decide reachability with deterministic program analysis.
3. Show evidence a human can check.
4. Abstain honestly when it cannot decide.

## Three things that must never be confused

| Term | Meaning | Who decides |
|---|---|---|
| Presence | The vulnerable module version is in the dependency graph. | Dependency scanners (version matching). |
| Reachability | A call path exists from the application's entry point to a vulnerable function. | VulnTrace AI. |
| Exploitability | An attacker can actually trigger the vulnerability through that path with harmful input. | A human security reviewer. Out of scope. |

VulnTrace AI never outputs a claim about exploitability. Output text must say "reachable", never "exploitable" or "vulnerable to attack".

## Intended users

- Application developers who receive a dependency alert and need to know whether to act now.
- Security engineers triaging many alerts who want evidence, not just a label.
- Interviewers and reviewers evaluating this project as a portfolio piece (secondary audience: the evaluation reports must be readable on their own).

## Use cases

1. "Advisory GO-XXXX-YYYY affects a module my app uses. Is my app's code able to reach the vulnerable function?"
2. "The advisory does not list vulnerable functions. Which function in the fix commit is the root cause, and is it reachable from my app?"
3. "Show me the exact call path, with file and line, so I can check it myself."
4. "Tell me clearly when the tool cannot decide, and why."

## Scope (version 1)

In scope:

- Go applications with one or more `package main` entry points.
- Go advisories from the Go vulnerability database (golang/vulndb).
- Fix commits hosted on GitHub.
- Command-line usage and machine-readable JSON output.
- An evaluation harness with synthetic and real cases.

## Non-goals (version 1)

- Exploitability assessment, exploit generation, or proof-of-concept attacks.
- Libraries without a `main` package as targets (entry points are ambiguous; see open questions).
- Languages other than Go.
- Data-flow or taint analysis (whether attacker-controlled data reaches the function).
- Automatic patching or upgrading of dependencies.
- A web UI, hosted service, or multi-user API.
- Vector databases, RAG, rerankers, agents or multi-agent orchestration in the main pipeline. Some of these appear only as measured experiments; see [architecture decisions](decisions/ARCHITECTURE_DECISIONS.md).
- Competing with commercial tools (Endor Labs, Semgrep, Snyk). This is an engineering study and demonstration.

## Assumptions

- Assumption: target applications build with the standard Go toolchain with `CGO_ENABLED=0`. Applications that need cgo will produce `CANT_DETERMINE` with an analysis-failure reason.
- Assumption: the vulnerable module version named in the advisory (`vulnerable_at`) can be fetched and built.
- Assumption: an LLM API will be available for milestone 4 onward. The provider and model are an open decision.
- Assumption: development happens on a Windows 11 laptop with 16 GB RAM. Every tool chosen must work there or have a documented alternative.

## Success criteria

The project is successful when all of the following are true and documented with real, reproducible results:

1. On the synthetic suite (truth known by construction), the system produces zero false `NOT_REACHABLE` verdicts. Errors, if any, are `CANT_DETERMINE`.
2. Every `REACHABLE` verdict carries a call path that the verifier has confirmed edge by edge.
3. On the symbol-identification set, the LLM + lifting approach is measured against the "every changed function" baseline, separately for advisories created before and after the model's training cutoff.
4. On adjudicated real applications, the verdict confusion matrix and abstention rate are reported, including failures.
5. The final report states what each optional experiment (retrieval, agent) did or did not improve, with numbers.
6. A reviewer can re-run the evaluation from a clean checkout by following documented commands.

Success does not require beating any existing tool. It requires honest, measured results.
