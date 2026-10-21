# Evaluation plan, metrics and baselines

This document combines the originally proposed `EVALUATION_PLAN.md` and `METRICS_AND_BASELINES.md`. Datasets are described in [dataset strategy](DATASET_STRATEGY.md).

## Questions the evaluation must answer

1. Does each reachability method avoid false `NOT_REACHABLE` on cases with known truth?
2. Does combining two methods with abstention reduce wrong verdicts, and at what abstention cost?
3. Can an LLM, given the full fix diff, identify root-cause functions better than "every changed function"?
4. Does deterministic lifting bring LLM selections closer to the curated labels?
5. Does any of this hold on advisories created after the model's training cutoff?
6. On real applications, how often is the final verdict correct, and how often does the system abstain?
7. For cases without a fix commit, does retrieval or an agent help at all? (experimental)

## Experiments

| ID | What | Dataset | Milestone | Status |
|---|---|---|---|---|
| R1 | Naive name-only call graph (negative control) | D2 | 2 | Required |
| R2 | Linker presence alone | D2 | 1 | Required |
| R3 | VTA call graph alone | D2 | 2 | Required |
| R4 | R2 + R3 with the verdict rule | D2 | 2 | Required |
| E0 | Every changed non-test function = vulnerable | D1 | 3 | Required (re-run of feasibility trial 2 at full size) |
| E1 | LLM selects from candidates, full diff in context | D1 | 4 | Required |
| E1+L | E1 followed by deterministic lifting | D1 | 4 | Required |
| E5 | Full pipeline end to end | D3 | 5 | Required |
| X1 | No-fix cases: keyword search, then hybrid (keyword + embeddings), over module source | D4 | 6 | Experimental |
| X2 | No-fix cases: single tool-using agent | D4 | 6 | Experimental |

Not planned: rerankers (candidate sets are tiny, median 2 per the feasibility findings), multi-agent systems (no expected advantage; see ADRs), vector database (scale does not need one).

R1 is included on purpose. It reproduces the most common portfolio approach so the report can show, with numbers, why it is unsafe.

## Baselines

- **Import-level baseline:** every application that imports the vulnerable package is `REACHABLE`. This is what happens today when an advisory lists no symbols.
- **E0:** every changed function. Feasibility trial 2 measured mean precision 0.70 and all-symbols recall in 52/59 cases on a sample; the full run replaces those numbers.
- **R1:** naive call graph.
- **govulncheck (reference only):** where curated symbols exist, govulncheck results are reported side by side. They are not ground truth, because govulncheck and R3 use the same analysis library.

## Metrics

### Reachability (D2, D3)

- 3×3 confusion matrix: truth (REACHABLE / NOT_REACHABLE) against output (REACHABLE / NOT_REACHABLE / CANT_DETERMINE).
- **False NOT_REACHABLE rate** = truly reachable cases answered `NOT_REACHABLE`, divided by truly reachable cases. Reported first, in every report.
- Precision and recall of `REACHABLE` and of `NOT_REACHABLE` among answered cases.
- Coverage = fraction of cases not answered `CANT_DETERMINE`.
- Selective accuracy = accuracy on answered cases.
- Risk–coverage view: for each method combination, show coverage against error rate.
- Accuracy alone is never reported, because real data is dominated by `NOT_REACHABLE`.

### Symbol identification (D1)

Per case, compared with curated core symbols (name plus package):

- Precision, recall, F1; macro-averaged over cases.
- Exact-set match rate.
- "Any hit" rate (at least one core symbol found).
- Secondary scoring against core ∪ derived symbols, because lifted symbols are often derived ones.
- All results split by advisory `created` date: before vs after the evaluated model's training cutoff.

### Evidence correctness (D2, D3)

- Verified-path rate: fraction of `REACHABLE` verdicts whose every edge, file and line passed the verifier.
- Verifier rejection count and reasons.
- For D3, human adjudication of each `REACHABLE` path: correct, infeasible, or wrong.

### Cost and resources

- Wall time per case (p50, p95) per stage.
- Peak memory of the Go helper on each D3 application (must fit the 16 GB laptop).
- LLM input/output tokens and cost per case; cache hit rate.

### Uncertainty

- Sample sizes are small (tens to low hundreds). Every rate is reported with a 95% bootstrap confidence interval and the raw counts.
- Differences between experiments are only called improvements if intervals do not overlap heavily; otherwise they are reported as "no clear difference".

## Contamination controls

- LLMs may have memorised public advisories and fix commits.
- D1 is split by the report's `source.created` date relative to each evaluated model's published training cutoff.
- Headline symbol-identification numbers use only the post-cutoff split.
- Pre-cutoff numbers are still reported, labelled as possibly contaminated.

## Reproducibility requirements

- Every run writes: git commit of this repository, vulndb commit SHA, Go version, GOOS/GOARCH, x/tools version, helper contract version, Python version, model ID, prompt template version, random seeds.
- LLM responses are cached and committed as hashes plus raw files (or a documented archive), so metrics can be recomputed without API calls.
- Reports are generated by code from result files. Numbers are never typed by hand.
- A `docs/results/` summary is committed only after the run that produced it is reproducible from a clean checkout.

## Gates

An experiment's result may be cited in the README or an interview only after:

1. It ran on the full planned dataset.
2. Its report includes counts, intervals and failure examples.
3. Someone other than the code (the project owner) has read at least five individual case outputs.
