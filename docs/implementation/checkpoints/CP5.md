# CP5 - Local LLM layer, root-cause selection, HyDE

- Recommended model: **Sonnet 5.5**, effort **high**
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `docs/implementation/checkpoints/CP3.md` and `CP4.md` (**review notes at the end of both bind this checkpoint**), `docs/progress/reports/CP4_REPORT.md`, `docs/results/CP4_RETRIEVAL_RESULTS.md`, `docs/design/DATA_MODEL.md` (RootCauseSelection), `docs/design/INTERFACES_AND_CONTRACTS.md` (sections 4 and 5), `docs/evaluation/EVALUATION_PLAN.md` (E1, S1, Q5, contamination), `docs/testing/TESTING_STRATEGY.md`

## Goal

Add the local LLM layer and use the model only as a **closed-set selector** and as a **query rewriter**, measured against what we already have.

Three questions, each answered with paired cluster-bootstrap intervals and no tuning on the test data:

1. **E1 (Mode 1, D1).** Given the full fix diff, does an LLM choosing from the changed functions beat E0 (predict all changed functions)?
2. **S1 (Mode 2, D4).** Given the top-k of the best fixed retrieval pipeline, does an LLM choosing from those k beat simply taking the retriever's top-1?
3. **HyDE (Mode 2, D4).** Does a hypothetical function written by the LLM improve retrieval (Q5)?

"The LLM does not help" is an acceptable, reportable answer. Do not tune prompts on the evaluation cases until a number looks good. Prompts are versioned files, frozen before the first real run; any change after seeing results is a new version, listed in the report with the reason.

**Out of scope:** lifting and caller/callee queries (they move to CP5b), the agent, the verifier, real target applications, fine-tuning, any paid API.

## Fixed choices (from the CP4 results; do not reopen)

- Retriever for S1 and HyDE: **`hybrid:bge-small`, chunk variant `code+commits`** (BM25 + dense fused with RRF). Reason: CP4 found BM25, dense and hybrid statistically indistinguishable, and rerankers did not help; this is the simplest strong choice. Report BM25-only HyDE as a secondary row so the choice can be checked.
- No reranker in CP5.
- Default top-k for S1: 10 (ablation k=5 allowed).

## Task 0 - carry-overs (each its own commit)

0a. **Neutral headline in the results renderer.** The CP4 document called `dense:bge-small` "best by MRR" although BM25, dense and hybrid are statistically indistinguishable. Add paired method-vs-method rows (BM25 vs dense vs hybrid; rerank vs hybrid) to the CP4 renderer, and make the headline say "no clear winner" when the best configuration's paired interval against the runner-up includes 0. Regenerate `docs/results/CP4_RETRIEVAL_RESULTS.md` from the committed result files (no re-run of models).

0b. **Notebook import path.** In every Colab notebook (CP4 and the new CP5 one), add `sys.path.insert(0, "/content/REPO-MIND/src")` plus `importlib.invalidate_caches()` right after `pip install -e`, because the notebook's Python session does not see the install until restarted. Keep the evidence gate and the "refuse empty runs" rule from the CP4 fix round in the new notebook too.

0c. **Retrieval config as data.** Record the fixed retriever above in one config file read by the harness, so S1 and HyDE cannot silently use another one.

## Deliverables

1. **`LLMClient`** - suggested `src/vulntrace/models/llm.py`
   - Interface from section 4. Real client: any OpenAI-compatible endpoint over HTTP, using only the standard library (no new dependency). Default `http://localhost:11434/v1` (Ollama).
   - **Endpoint rule (required, tested):** only loopback hosts are accepted by default. Known paid API hostnames (at least api.openai.com, api.anthropic.com, generativelanguage.googleapis.com, api.mistral.ai, api.cohere.com, api.groq.com, openrouter.ai, api.together.xyz, api.deepseek.com) are rejected even if the user sets them. A non-loopback host needs an explicit environment variable naming that exact host and is still rejected if it is on the paid list.
   - Fake `LLMClient`: scripted responses keyed by input hash, including invalid JSON, out-of-set IDs, empty output and an injected-instruction response.
   - Every real call records model name, digest/tag, temperature, seed, max tokens, token counts and latency.

2. **Response cache** - `models/llm_cache.py`
   - Key = hash of (model id, settings, messages). Stored on disk under the gitignored data directory. A re-run costs nothing and makes metrics recomputable.
   - **Committed results never contain prompts or raw responses** (they carry third-party code and advisory text). Commit only parsed selections, validity flags, token counts and latencies. Raw traces stay in the gitignored cache (and on Drive in Colab).

3. **Prompt templates and closed-set validation** - `src/vulntrace/llm/prompts/` (versioned text files), `llm/select.py`
   - Mode 1 prompt: advisory summary and details, plus the non-test diff as numbered hunks, plus the candidate list with IDs. The prompt must not contain the core or derived symbols. Truncate oversized diffs by a stated rule and record every truncated case.
   - Mode 2 prompt: advisory text plus the top-k candidates (ID, signature, code, truncated by a stated cap). No fix commit, no gold, no `derived_symbols`; add a test that proves the prompt builder cannot see those fields.
   - Output: JSON only `{"selected": [ids], "abstain": bool}`. Code validates it: IDs must be in the candidate list, at most N IDs (N stated), JSON must parse. **One** retry with the validation error shown to the model; both attempts are recorded. A still-invalid output counts as `INVALID` (never silently repaired, never dropped). Report the invalid rate and the abstain rate for every run.
   - Untrusted text (advisory, commits, code) is wrapped in delimiters and described to the model as data. A test with an injected instruction inside a commit message and inside code must show that the closed-set rule holds (an out-of-set answer is rejected).

4. **HyDE** - `llm/hyde.py`
   - From the advisory text, the model writes one short hypothetical Go function (plain text, length cap). The hypothetical text is used only as a retrieval query and never shown as evidence.
   - Variants: `query` (original query only, = CP4), `query+hyde`, `hyde-only`. Evaluate with `hybrid:bge-small` (fixed) and, as a secondary row, BM25 only.

5. **Evaluation commands** - extend `eval`
   - `python -m vulntrace eval select --mode fix --model <name>` (E1 on D1, with E0 in the same table).
   - `python -m vulntrace eval select --mode release --model <name> --k 10` (S1 on D4, with retrieval top-1 in the same table).
   - `python -m vulntrace eval retrieval --hyde <variant> --model <name>` (HyDE on D4).
   - Metrics: reuse CP3/CP4 code. E1: precision, recall, F1, exact match, any-hit against core and against core ∪ derived, abstention, invalid rate. S1: any-hit in the selection, precision, R@1 of the retriever on the same cases, with **two denominators** as in CP4 (gold inside the top-k; all scored cases). HyDE: the CP4 retrieval metrics.
   - Cluster bootstrap for D4 (CP4 `cluster_key`), paired differences against the baseline on the same draws. Size buckets and date buckets as in CP4, plus the contamination split below.
   - Results as JSON under `results/cp5/`; rendered by code to `docs/results/CP5_LLM_RESULTS.md`.

6. **Contamination split (replaces the placeholder cutoff).** Record each model's documented training-data cutoff from its model card (cite where it came from). If no cutoff is documented, say so and treat every case as possibly seen. The **headline numbers use only cases created after the model's cutoff**; the earlier cases are reported separately. The 14 undated D4 cases are their own bucket. Say plainly how many cases are in each group.

7. **Models.** Compare **at most two** open instruction-tuned models served by Ollama, one around 7-8 billion parameters and, optionally, a smaller one. They must fit a free Colab T4 (16 GB) at 4-bit. Record the exact Ollama tag and the digest. Examples to consider (availability and size must be checked in Colab, not assumed): a Qwen2.5-Coder-7B-Instruct build, a Llama-3.1-8B-Instruct build. If a model cannot be pulled, report it and do not substitute a paid API.

8. **Colab notebook** - `notebooks/cp5_llm_colab.ipynb`
   - Steps: clone the branch, `sys.path` line, install Go and the project, install and start Ollama on the Colab machine, pull the chosen models, rebuild D1 and D4 evidence on **local disk** (`dataset materialize --set d1` and `--set d4`) with the evidence gate, run the three evaluations for each model, write a small results zip.
   - Same rules as CP4: git cache and evidence on local disk, only caches and results on Drive; a gate that stops the notebook if evidence differs from the committed case lists; `eval` refuses to write when 0 cases or 0 chunks; plain-English comment at the start of every cell; expected running time per step recorded from the real run.
   - The owner runs it in Colab and hands the zip to the next session. The session cannot reach Hugging Face or the Ollama registry. Do a **dry run with the fake LLM on the real evidence** in the session (as in CP4); documents built from fake runs must carry the loud warning.

9. **Tests**
   - Unit: endpoint rule (loopback accepted; every listed paid host rejected, including with a port, upper case and a trailing dot), cache hit and miss, prompt builders cannot see gold or fix fields, closed-set validation (valid, out-of-set, malformed JSON, empty, duplicate IDs, abstain), one-retry logic, injected-instruction fixtures, HyDE query assembly, paired bootstrap for the new metrics, contamination bucketing (including undated).
   - Integration: E1, S1 and HyDE run end to end on a tiny synthetic case set using only the fake LLM and the in-memory store, no network.
   - Nothing in the default run touches the network or a model. CI stays green.

10. **Results document** - `docs/results/CP5_LLM_RESULTS.md`, generated by code: models and digests, prompt versions, E1 vs E0, S1 vs retrieval top-1, HyDE variants vs CP4 retrieval, invalid and abstain rates, token and time cost per case, contamination split with counts, and a plain statement of what the LLM adds or does not add. First paragraph states the main finding, including a negative one.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Task 0 done (neutral headline, notebook path line, retriever config file); CP4 results regenerated. | Results doc, tests |
| 2 | Endpoint rule: every listed paid host rejected, loopback accepted. | Test names |
| 3 | Closed-set validation, one retry, invalid and abstain counted; injection fixtures pass. | Tests |
| 4 | Prompt builders provably cannot see gold or fix fields (Mode 2) or core/derived symbols (Mode 1). | Tests |
| 5 | Full pipeline runs end to end on fakes; dry run with the fake LLM on real D1 and D4 evidence done. | Printed summary, dry-run log |
| 6 | At least one real run (E1, S1, HyDE) for at least one model produced in Colab and committed as small result files. If not run, say so plainly and mark the checkpoint accordingly. | Result files |
| 7 | Prompt versions frozen before the first real run; every later change listed with its reason. | Report |
| 8 | Contamination split with real model cutoff (or "not documented"), counts shown; headline on post-cutoff cases only. | Results doc |
| 9 | Two denominators, paired intervals, size and date buckets reported. | Results doc |
| 10 | All tests pass locally and in CI; no model, cache, raw prompt or response, or `data/` content committed. | Printed summaries, `git ls-files` |
| 11 | Report `docs/progress/reports/CP5_REPORT.md` in the wrapper format; STATUS `AWAITING_REVIEW`. | Files |

## Known risks

- A 7B model may often return invalid JSON; that is a result (report the rate), not something to hide by repairing outputs.
- A model may have memorised old advisories; the contamination split exists for that reason.
- The Colab T4 may be unavailable or slow; keep runs resumable through the cache and report what did not finish.
- The Ollama registry or Colab network may be blocked; report it, do not switch to a paid service.

## Review notes

(The supervising assistant adds notes here if the state becomes `CHANGES_REQUESTED`.)

**Supervisor review, 22 Oct 2026 - APPROVED** (branch `claude/vulntrace-ai-build-o31zls` at `05a565d` plus the real Colab results committed by the supervisor).

Checked by the supervisor: `pytest tests/unit tests/contract` -> 452 passed, 9 skipped (pgvector; CI ran it); CI green on the branch tip. The Colab bundle is valid: both models pulled (digests and 4-bit quantisation recorded), E1 144/144 valid, S1 118/118 valid, HyDE 120/120 per model, 0 server errors, repo commit `05a565d`, Tesla T4. The results document renders from the bundle and carries no `(dirty)` flag. The owner's run hit three problems that are all operational and were handled honestly: the D1 evidence needed a second `materialize` pass; a partial Ollama install (llama-server missing, every call HTTP 500, the run aborted correctly after 3 failures); a free-tier GPU disconnect (the Drive cache resumed it).

What the results say (honest reading; numbers in `docs/results/CP5_LLM_RESULTS.md`):

1. **E1: the LLM does not beat E0.** Choosing from the changed functions raised precision slightly (llama +0.048 [0.009, 0.086]) but cut recall from 0.84 to 0.57 (paired -0.271 [-0.337, -0.207]); F1 -0.067 [-0.112, -0.025] and any-hit -0.099 [-0.161, -0.045] are worse for llama, similar for qwen. A single wrongly narrowed pick is exactly the error that could produce a false NOT_REACHABLE later. Design implication for CP7: do not let an LLM pick narrow Mode 1 to one function without keeping the others (for example check reachability for all changed functions or the LLM's ranked list). Decide in the CP7 spec.
2. **S1: llama3.1-8b improves on the retriever's top-1; qwen2.5-coder does not, because it abstains.** llama: any-hit +0.071 [0.022, 0.124] over all scored cases and +0.095 [0.030, 0.163] when gold is in the top-10; precision unchanged (+0.014 [-0.027, 0.053]). qwen abstained on 76 of 118 (k=10) and 73 of 118 (k=5), so it is far below top-1 (-0.31). The frozen prompt explicitly invites abstention, so this measures how the model follows that instruction, not its code understanding. Do **not** tune the prompt on these cases; a prompt change needs a fresh, untouched case set.
3. **HyDE is weak at best.** Only one of many comparisons excludes 0 (qwen, `hybrid:bge-small`, query+hyde, MRR +0.055 [0.003, 0.110]; the lower bound is 0.003). llama +0.035 [-0.050, 0.117]; BM25 and hyde-only show no detectable difference. With about twelve comparisons per model and no correction for that, this is not a headline.
4. **Contamination.** llama3.1-8b: documented cutoff December 2023, taken from third-party copies of the model card, so the owner should check the official page. qwen2.5-coder: cutoff not documented, so all dated cases count as possibly seen. The two models' headline groups therefore differ in size; cross-model comparisons are indicative only.
5. The GO-2020-0006 difference (committed list `PSEUDO_VERSION_UNRESOLVED`, rebuilds `AVAILABLE` in every environment) is accepted; the committed case list should be corrected (see below).

Requests carried into CP5b (small, each its own commit, before the main work): (a) find the cause of the D1 first-pass mismatch (the same 9 cases in two environments; second pass fixes them in seconds), fix it so one pass converges, and remove the double-run workaround from the notebook; use `dataset diagnose` on one of the 9 with a fresh cache and report the git error; (b) the Ollama install cell must check that the server really works (for example a one-token generate call) instead of only `which ollama`; (c) correct `GO-2020-0006` in `docs/results/datasets/D4_cases.json` (and its counts) to the reproducible status, as its own commit with the reason; (d) add a line to the results renderer stating how many comparisons each model's HyDE table contains, so a single borderline interval cannot read as a finding.
