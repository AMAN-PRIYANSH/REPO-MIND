# Risks and open questions

## Decisions already made (21 Oct 2026)

| Question | Decision |
|---|---|
| Where does Claude Code run? | Claude Code cloud sessions (Linux, 4 vCPU, 16 GB RAM, Go, Python, PostgreSQL 16, Docker preinstalled). |
| Which LLM provider, what budget? | Free open models only, via Ollama or sentence-transformers. Budget: zero. |
| Where do real model runs happen? | Google Colab free GPU; laptop CPU for the demo. |
| Time budget? | About 4 weeks, 8 checkpoints; multi-agent is a stretch goal. |
| Rename the repository? | Not now. Revisit at the end (GitHub redirects old URLs after a rename). |

## Open questions

| # | Question | Why it matters | Decide by | Current lean |
|---|---|---|---|---|
| Q1 | Does `go tool nm` print the same symbol format on Windows? | Demo on the owner's laptop. | CP7 | Check on the laptop during CP7. |
| Q2 | How do generic functions appear in `go tool nm` and vulndb symbols? | Matching rules. | CP1-CP2 | `UNSUPPORTED_SYMBOL_FORM` until verified. |
| Q3 | How often will VTA and linker disagree on real applications? | Abstention rate. | CP7 | Measure. |
| Q4 | Lifting stopping rule: nearest exported caller or all exported callers? | Symbol precision vs recall. | CP5 | Measure both. |
| Q5 | Licence terms of golang/vulndb data. | Whether samples can be committed. | CP3 | Reference by commit SHA only until checked. |
| Q6 | Which embedding and reranker models? | Retrieval quality and Colab/CPU speed. | CP4 | Small open models first; compare at most two of each. |
| Q7 | Is a 7B open model reliable enough at tool calling for the agent? | CP6 feasibility. | CP6 | Measure invalid-call rate; fall back to a simpler constrained loop if needed. |
| Q8 | Why are 10/42 core-symbol sets not fully inside the release diff (trial 5)? | Ceiling of Mode 2. | CP3 | Investigate before using as a ceiling. |
| Q9 | How should pseudo-versions be resolved? | 5/50 trial cases failed. | CP3 | Use the commit hash embedded in the pseudo-version. |
| Q10 | Can the cloud environment pull the pgvector Docker image? | Integration tests for the real store. | CP4 | Docker Hub is on the default allowlist; verify. |

## Risks

| # | Risk | Type | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| R1 | Owner cannot debug Go helper code | Resource | Medium | High | Small helper; plain-English explanations; contract tests isolate failures. |
| R2 | Ground-truth fixture is wrong | Evaluation | Low | High | Rationale per case; owner and supervisor review fixtures in CP1. |
| R3 | Verdict rule abstains too often on real code | Technical | Medium | Medium | Measure; report honestly; revise with evidence. |
| R4 | LLM memorised advisories | Evaluation | High for older cases | High | Split by `created` date; headline numbers post-cutoff. |
| R5 | Labels follow conventions unlike the model's notion of root cause | Evaluation | Observed | Medium | Lifting; score against core and core ∪ derived. |
| R6 | Small samples give unstable numbers | Evaluation | High | Medium | Bootstrap intervals; raw counts; no strong claims. |
| R7 | Colab GPU unavailable or session cut off | Resource | Medium | Medium | Resumable runs, caching, smaller model fallback, laptop CPU for small runs. |
| R8 | 7B model too weak for agent tool calling | Technical | Medium | Medium | Strict tool schemas, budgets, retries; report failure rate; constrained loop fallback. |
| R9 | Retrieval does not beat the B-ID baseline | Evaluation | Medium | Medium | Report it honestly; it is still a valid, interview-worthy finding. |
| R10 | Four-week deadline slips | Delivery | Medium | Medium | Drop order defined in the roadmap; checkpoints keep work mergeable. |
| R11 | Claude Pro usage limits interrupt sessions | Delivery | High | Low | Commit per task; handoff notes in STATUS.md; same wrapper resumes. |
| R12 | Building untrusted code causes harm | Security | Low | High | ADR-014 settings; never execute targets. |
| R13 | Prompt injection in advisory or commit text | Security | Medium | Low | Closed-set answers validated by code; read-only tools; budgets. |
| R14 | Accidental paid usage (paid API, Fable or 1M-context model in Claude Code) | Cost | Low | High | CLAUDE.md rule; endpoint check test; model guidance per checkpoint. |
| R15 | Over-claiming results | Integrity | Medium | High | Evaluation gates; numbers generated from result files only. |

## Verified facts vs assumptions (summary)

Verified (feasibility findings, 21 Oct 2026): label coverage across Go, Rust and Python databases; 59-case fix-commit comparison; 45-case release-range sizes; five-app controlled reachability test (Linux, Go 1.24.7); Claude Code cloud environment specification (from official documentation).

Assumed, not yet verified: Windows `nm` behaviour; VTA results on fixtures; local 7B model quality; retrieval beating baselines; agent reliability; abstention rate on real code; Colab availability.
