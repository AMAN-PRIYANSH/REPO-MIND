# Interview notes

For the owner. These are answers in plain words that you can say in your own words; change anything that does not sound like you. Every number comes from [docs/results/summary.json](results/summary.json) (a test checks this), and every answer links to its evidence. The honest answer is always the one the evidence allows: where the result was negative or weak, say so first.

**Say this about the build, plainly.** The project was built with Claude Code, one checkpoint at a time under written rules ([CLAUDE.md](../CLAUDE.md)), and each checkpoint was reviewed by a separate supervising assistant before the next was released. Documented owner work includes running the Colab model runs and spot-checking path steps of the real-application cases. [Add, in your own words, what you decided, reviewed and understood yourself.] Be ready to explain any part you list.

## The pitch (about a minute)

Dependency scanners flag a vulnerable library even when your code never calls the vulnerable function. Go's official tool, govulncheck, can answer "is it called?", but only when the advisory names the vulnerable functions, and most Go advisories do not. VulnTrace AI takes the fix commit, or the functions changed between releases, and asks with two independent methods, a call graph and a linker check, whether your application's `main` can reach them. It shows the call path with file and line, a deterministic verifier re-checks every step, and it says "can't determine" instead of guessing. I also tried retrieval, a local LLM, HyDE and an agent, and measured each against a simple baseline: retrieval stayed in, the rest did not earn their place, and I kept those as negative results. On real applications the lesson was that a call-graph path is not proof the code can run, so "reachable" means "needs a human look". It is about reachability, never exploitability.

Evidence: [final report](FINAL_REPORT.md), [README](../README.md).

## Likely questions

### 1. Why not just use govulncheck?

Because it needs the advisory to name symbols, and most Go advisories do not (a pre-design measurement, not re-measured here: [feasibility findings](research/FEASIBILITY_FINDINGS.md)). This project tries to recover the symbols and then decide reachability. But be honest about the comparison: on the 14 real-application cases, govulncheck agreed on 9/11 = 0.818 [0.523, 0.949] of the cases where both answered, and on the 2 disagreements it said NOT_REACHABLE while the reviewers found our REACHABLE paths infeasible (2 of 2). On those cases the official tool was not worse than this pipeline. I did not show that this tool beats it; the case for it is the advisories govulncheck cannot answer.

Evidence: [CP7b results](results/CP7B_REAL_APPS_RESULTS.md), [summary](results/SUMMARY.md#cp7b-real-applications-d3-adjudicated).

### 2. Why did you drop the agent?

I built a LangGraph agent with search, diff and caller/callee tools and measured it against plain retrieval. It did not win: for one model it equalled retrieval at top-1 (difference 0.000 [-0.082, 0.082]), for the other it was worse (-0.208 [-0.304, -0.112]), and it cost about 5.2 times the prompt tokens of the one-shot LLM. The only win was over a weak baseline that answered a small share of cases. So the product uses retrieval and the agent stays as a measured negative result; the multi-agent extension was dropped for the same reason.

Evidence: [CP6 results](results/CP6_AGENT_RESULTS.md), [CP6 review](implementation/checkpoints/CP6.md#review-notes).

### 3. How do you know the numbers are real?

Every number in the README, the final report and these notes comes from `summary.json`, which code computes from committed result files with the same statistics code that renders the per-checkpoint results documents; a test regenerates it and fails if the committed copy differs, another test checks each source file's sha256, and another fails if a number in these documents is not in the summary. Limits: the test catches numbers that are not in the summary, not a correct number attached to the wrong claim, and the model runs happened on Colab, so they can be recomputed from the committed files but not re-run in CI. One real catch: the summary generator once rounded twice and printed a different third decimal from the results document it was meant to match; the cross-check test against that document caught it.

Evidence: [SUMMARY.md](results/SUMMARY.md), `tests/unit/test_cp8_summary.py`, `tests/unit/test_cp8_docs.py`.

### 4. What is the biggest weakness?

REACHABLE is over-approximate. On real applications the reviewers judged 0/7 = 0.000 [0.000, 0.354] of the shown REACHABLE paths able to run as a whole, although every step exists in the code (7/7 = 1.000 [0.646, 1.000]): a dynamic call that never takes the target, a branch never taken, a field never set. n is small and this judges the shown path, not the target, which may be reachable by another path. That is why REACHABLE is presented as "a call-graph path exists; needs a human look", never as confirmed. The next step would be a path-feasibility check.

Evidence: [CP7b results](results/CP7B_REAL_APPS_RESULTS.md), [CP7b review](implementation/checkpoints/CP7b.md#review-notes).

### 5. What is the worst error, and how did you guard against it?

A false NOT_REACHABLE, because it tells someone to ignore a real problem. Guards: two independent methods must both say absent; the verifier can only downgrade; a Mode 2 NOT_REACHABLE is downgraded to CANT_DETERMINE (only 5 of 20 required raw verdicts existed); and Mode 1 analyses every changed function instead of an LLM's single pick. Results: 0 of 22 false NOT_REACHABLE on the fixtures and 0 of 4 on the real applications. Running on real modules also found two linker-method defects that could have caused one; they were fixed and re-run. The fixtures have known truth by construction and the real-application sample is small, so this is evidence, not a guarantee.

Evidence: [CP7 results](results/CP7_TRIAGE_RESULTS.md), [CP7 review](implementation/checkpoints/CP7.md#review-notes).

### 6. Why does it abstain so much on real code?

On real modules 102 of 143 Mode 1 runs and 88 of 120 Mode 2 runs ended in CANT_DETERMINE. The main causes are mechanical: modules that need a newer Go than the 1.24 toolchain used (58 of 143 and 52 of 120) and libraries with no `main` package (26 of 143 and 22 of 120). These are distributions, not accuracy. On real applications the 3 abstentions all had a clear NOT_REACHABLE answer in the code (3 of 3), so the abstentions were too cautious; using those cases is the obvious improvement.

Evidence: [CP7 results](results/CP7_TRIAGE_RESULTS.md), [CP7b results](results/CP7B_REAL_APPS_RESULTS.md).

### 7. What did the LLM add?

In the product, nothing, and that is a result. When a local LLM chose the root-cause function from a fix diff, recall fell from 0.840 [0.774, 0.901] to 0.569 [0.490, 0.643] (paired -0.271 [-0.337, -0.207]) while precision rose slightly. A wrongly narrowed pick is exactly the error that could cause a false NOT_REACHABLE, so Mode 1 keeps every changed function. When an LLM chose among the retriever's top-10, one model improved on top-1 and the other abstained on 76 of 118 cases; I did not tune the prompt on those cases.

Evidence: [CP5 results](results/CP5_LLM_RESULTS.md), [CP5 review](implementation/checkpoints/CP5.md#review-notes).

### 8. Is the advanced RAG worth it?

Be careful here. Retrieval clearly beats the commit-message baseline (MRR 0.599 [0.519, 0.683] against 0.397 [0.317, 0.478]), but BM25 alone reaches 0.571 [0.495, 0.651], and BM25, dense and hybrid retrieval are statistically indistinguishable on this data (hybrid against BM25 0.028 [-0.011, 0.065]). Rerankers did not help, and HyDE is weak at best. The main gain came from putting commit subjects into the chunk text. The honest summary: ranking is useful but not solved, and the fancy parts did not clearly pay off. Also, the end-to-end Mode 2 runs used BM25 as the documented fallback, not the intended hybrid retriever, because no embedder was available in that environment.

Evidence: [CP4 results](results/CP4_RETRIEVAL_RESULTS.md), [CP4 review](implementation/checkpoints/CP4.md#review-notes).

### 9. How was the truth for the real applications made, and can you trust it?

Two kinds. The fixtures have truth by construction. For the 14 real-application cases, two Claude reviewer agents, working independently, read the real source at the pinned versions; they agreed on every case, the supervising assistant reconciled them, and the owner spot-checked path steps. That is not expert human ground truth, two reviewers of the same model family agreeing is weak evidence, and nothing was built or run. I treat the numbers as case-study evidence, and a human expert adjudicator is the first thing I would add.

Evidence: [CP7b results](results/CP7B_REAL_APPS_RESULTS.md), [adjudication files](results/cp7b/adjudication/adjudication.json), [CP7b review](implementation/checkpoints/CP7b.md#review-notes).

### 10. Could the models have seen the test data?

Possibly, which is why results are split by creation date against each model's training cut-off and headline numbers use only later cases. Limits: one model's cut-off is taken from third-party copies of its model card, the other's is undocumented so every dated case counts as possibly seen, and 87 of 120 D4 cases are post-cut-off while 14 have no date. Cross-model comparisons are indicative only.

Evidence: [final report, threats to validity](FINAL_REPORT.md#7-threats-to-validity), [CP5 review](implementation/checkpoints/CP5.md#review-notes).

### 11. How do you handle untrusted code and prompt injection?

Analysed code, advisories and commit text are untrusted data. Builds use `GOTOOLCHAIN=local` and `CGO_ENABLED=0`; `go generate`, the target's tests and its binaries are never run. LLM and agent outputs are closed-set selections validated by code, agent tools are read-only, and the LLM never decides reachability; deterministic analysis does.

Evidence: [system architecture, security boundaries](architecture/SYSTEM_ARCHITECTURE.md#security-boundaries), [CLAUDE.md](../CLAUDE.md).

### 12. Why Go, and why two methods?

Go has a mature static toolchain (a VTA call graph from `golang.org/x/tools`, symbols in the binary), so reachability can be decided deterministically, and a reachability tool already exists to compare with. Each method fails differently: VTA can miss edges through reflection, the linker check is conservative about what stays in the binary. Requiring agreement for NOT_REACHABLE turns disagreement into an abstention instead of a wrong answer. On the fixtures the combination had no false verdicts in Mode 1 where each method alone erred.

Evidence: [CP2 results](results/CP2_CALLGRAPH_RESULTS.md), [CP7 results](results/CP7_TRIAGE_RESULTS.md).

### 13. What did running on real code teach you that the fixtures did not?

Real modules found bugs the fixtures never triggered: two linker-method defects (generic functions named without type parameters, and functions in the analysed `main` package) that could have produced a false NOT_REACHABLE, and two verifier false rejections. All were fixed and re-run. The real applications also showed that call-graph paths can be infeasible, which no fixture had.

Evidence: [CP7 review](implementation/checkpoints/CP7.md#review-notes), [CP7 results](results/CP7_TRIAGE_RESULTS.md).

### 14. What would you do next?

First a path-feasibility check for REACHABLE verdicts, since the main weakness is infeasible paths; it changes the verdict rule, so it needs its own checkpoint and a fresh case set. Then use the clear-answer abstentions, more real applications, a human expert adjudicator, and a re-run of Mode 2 with the intended retriever and a newer Go in CI.

Evidence: [final report, section 8](FINAL_REPORT.md#8-what-comes-next-not-done).

### 15. What did you learn about evaluation?

Fix the headline wording before the results, keep negative results, report intervals with the sample size, group by independent clusters (nine D4 cases share one release range), and never let a passing test suite stand in for reading the code: an early selection bug hid behind green tests and was caught by reading it, and the CP6 headline sentence had to be reworded after the results because the first version was true only through a win over a weak baseline.

Evidence: [CP3 review](implementation/checkpoints/CP3.md#review-notes), [CP6 review](implementation/checkpoints/CP6.md#review-notes).
