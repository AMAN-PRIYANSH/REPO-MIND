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
5. "There is no fix commit linked, only a fixed release. Search what changed and find the likely vulnerable function, with evidence I can check."

## Two modes

**Mode 1 - fix commit available.** The fix commit is known. Its diff is small (median 2 changed functions in the feasibility sample), fits in an LLM prompt, and needs no retrieval. An LLM chooses the root-cause function from a closed list; code does everything else.

**Mode 2 - investigation mode.** No fix commit is given. The system must search the code that changed between the vulnerable release and the fixed release, using the advisory text. In the feasibility sample this candidate set had a median of 13 functions, but 12 of 45 releases changed 100 or more functions and the largest changed 2,558. Here advanced retrieval (hybrid search, fusion, reranking, query rewriting), a vector database and a tool-using agent have a real job, and each is measured against simpler baselines.

Both modes end in the same deterministic reachability analysis and evidence verification.

## Scope (version 1)

In scope:

- Go applications with one or more `package main` entry points.
- Go advisories from the Go vulnerability database (golang/vulndb).
- Fix commits and releases hosted on GitHub.
- Mode 1 and Mode 2.
- Command-line usage, machine-readable JSON output, and a minimal local demo page.
- An evaluation harness with synthetic, labelled and real cases.

## Hard constraint: zero cost

- No paid APIs of any kind. All LLM, embedding and reranker models are free open models run locally (owner's laptop) or on a free Google Colab GPU, through an OpenAI-compatible endpoint (Ollama by default).
- The code is built with Claude Code under the owner's existing Claude Pro plan.
- Tests use fake models and never download or call real ones.

## Non-goals (version 1)

- Exploitability assessment, exploit generation, or proof-of-concept attacks.
- Libraries without a `main` package as targets (entry points are ambiguous; see open questions).
- Languages other than Go.
- Data-flow or taint analysis (whether attacker-controlled data reaches the function).
- Automatic patching or upgrading of dependencies.
- A hosted service or multi-user API. (A minimal local demo page is in scope.)
- Retrieval, agents or multi-agent components in Mode 1, where measurements show they are not needed. They belong to Mode 2; see [architecture decisions](decisions/ARCHITECTURE_DECISIONS.md).
- Paid models or paid infrastructure of any kind.
- Competing with commercial tools (Endor Labs, Semgrep, Snyk). This is an engineering study and demonstration.

## Assumptions

- Assumption: target applications build with the standard Go toolchain with `CGO_ENABLED=0`. Applications that need cgo will produce `CANT_DETERMINE` with an analysis-failure reason.
- Assumption: the vulnerable module version named in the advisory (`vulnerable_at`) can be fetched and built.
- Assumption: a 7B-class open model (for example Qwen2.5-Coder 7B Instruct via Ollama) is good enough for closed-set selection and tool calling. To be measured in CP5-CP6; a smaller or larger free model may replace it.
- Assumption: Google Colab's free GPU is available often enough for evaluation runs. Runs must be resumable because Colab sessions end without warning.
- Code is written and tested in Claude Code cloud sessions (Linux, 4 vCPU, 16 GB RAM, with Go, Python, PostgreSQL 16 and Docker preinstalled). The owner's Windows 11 laptop (16 GB RAM, no dedicated GPU) runs the demo. Windows behaviour must be checked, not assumed.

## Success criteria

The project is successful when all of the following are true and documented with real, reproducible results:

1. On the synthetic suite (truth known by construction), the system produces zero false `NOT_REACHABLE` verdicts. Errors, if any, are `CANT_DETERMINE`.
2. Every `REACHABLE` verdict carries a call path that the verifier has confirmed edge by edge.
3. Mode 1: the LLM + lifting approach is measured against the "every changed function" baseline, separately for advisories created before and after the model's training cutoff.
4. Mode 2: a retrieval ablation table (BM25, dense, hybrid, hybrid + reranker, + query rewriting, agent) reports Recall@k and MRR against labelled symbols, next to the simple ID-search baseline.
5. On adjudicated real applications, the verdict confusion matrix and abstention rate are reported, including failures.
6. The final report states what each advanced component did or did not improve, with numbers, including negative results.
7. A reviewer can re-run the evaluation from a clean checkout using committed result files and cached model outputs.
8. Total money spent: zero.

Success does not require beating any existing tool. It requires honest, measured results.
