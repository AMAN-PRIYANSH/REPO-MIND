# CP5 report: Local LLM layer, root-cause selection, HyDE

**Status: AWAITING_REVIEW, with acceptance criterion 6 NOT MET.** Everything is built and tested, the whole pipeline
(E1, S1 at k=10 and k=5, HyDE, results document) ran end to end with the **fake** LLM and fake embedder on the **real** D1 and D4
evidence, and the Colab notebook is written and tested. **No real language model was run**: Ollama's registry and Hugging Face
are unreachable from this session (HTTP code 000), there is no GPU, and this session cannot drive Colab. So no E1, S1 or HyDE
*result* exists, `docs/results/CP5_LLM_RESULTS.md` is deliberately **not** committed (a document built from fake runs would carry
no information), and the question "does the LLM help?" is **unanswered**. The owner must run `notebooks/cp5_llm_colab.ipynb`
and hand the zip to the next session.

## 1. Environment

Printed in this session:

```
uname -a: Linux vm 6.18.44-fc-v140 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
OS: Ubuntu 24.04.5 LTS
Python 3.13.16 (venv .venv: numpy 2.5.4, pytest 9.1.1, jsonschema 4.26.0, PyYAML 6.0.3)
go version go1.24.7 linux/amd64
git version 2.43.0
Docker version 29.9.1 (not used in CP5)
GPU: none (nvidia-smi: command not found). CPU only.
```

Network checks:
- `git` over HTTPS to GitHub works: `dataset fetch`, `helper fetch` and both `dataset materialize` runs succeeded.
- `https://registry.ollama.ai/v2/` -> curl code `000` (no connection). `https://huggingface.co` -> `000`. `which ollama` -> not installed.
  WebFetch to huggingface.co failed with `ENOTFOUND`. Consequence: no model could be pulled or run here.
- No paid API was configured or called. The only LLM objects used were `FakeLLMClient` instances.

## 2. Files changed (grouped)

Task 0:
- `src/vulntrace/eval/retrieval_report.py` - neutral headline ("No clear winner" unless the paired interval of the best configuration vs the runner-up excludes 0; the ID-masked/code-only variants of a method are not competitors), new "Method vs method" paired table (`method_comparison_pairs`).
- `docs/results/CP4_RETRIEVAL_RESULTS.md` - regenerated from the committed result files (no model re-run). New headline: no clear winner; `dense:bge-small` vs `hybrid:bge-small` ΔMRR 0.003 [-0.039, 0.042]; dense vs BM25 +0.032 [-0.023, 0.084], hybrid vs BM25 +0.028 [-0.011, 0.065]; rerank vs hybrid -0.034 [-0.103, 0.038] / -0.018 [-0.070, 0.034].
- `notebooks/cp4_retrieval_colab.ipynb` - `sys.path.insert(0, "/content/REPO-MIND/src")` + `importlib.invalidate_caches()` after `pip install -e`.
- `src/vulntrace/retrieval/fixed_retriever.json`, `retrieval/fixed.py` - the fixed retriever (`hybrid:bge-small`, `code+commits`, secondary `bm25`, k=10, ablation k=5) as data; no CLI flag can name another one.

LLM layer:
- `src/vulntrace/models/llm.py` - `LLMClient`, `OpenAICompatClient` (stdlib HTTP, Ollama default), endpoint rule, `LLMResponse` provenance (model, digest, settings, tokens, latency).
- `src/vulntrace/models/llm_cache.py` - disk cache (key = model identity+digest, settings, messages), `CachedLLMClient`.
- `src/vulntrace/models/fakes.py` - `FakeLLMClient` (scripted by request hash, retry sequences), canned invalid/empty/injected responses, dry-run responders.
- `src/vulntrace/llm/prompts.py`, `llm/prompts/*.txt` (+ `FROZEN.json`) - versioned templates, Mode 1/Mode 2 builders, truncation rules.
- `src/vulntrace/llm/select.py` - closed-set validation, one retry, INVALID/ERROR statuses.
- `src/vulntrace/llm/hyde.py` - HyDE generation and query assembly.
- `src/vulntrace/llm/models_config.py` - the two models, cutoffs with sources, contamination buckets.
- `src/vulntrace/llm/factory.py` - client factory (cache, fake).
- `src/vulntrace/eval/cp5_stats.py` - set metrics, case matrices, paired cluster bootstrap (`Group`).
- `src/vulntrace/eval/select_eval.py` (E1, S1), `hyde_eval.py` (HyDE), `cp5_cli.py` (commands), `llm_report.py` (results document).
- `src/vulntrace/__main__.py` - `eval select`, `eval retrieval --hyde`, LLM flags, `results render --doc cp5`; `results_doc.py` dispatch.
- `src/vulntrace/eval/retrieval.py` - `EvalCase.summary/details` (the two advisory fields; `cases.json` unchanged), `Harness.set_queries`.
- `src/vulntrace/eval/evidence_gate.py` - `subdir` argument (D1 `fix_evidence`).
- `notebooks/cp5_llm_colab.ipynb` - D8. `pyproject.toml` (package data), `README.md` (commands).
- `docs/progress/reports/CP5_DRYRUN.log` - output of the fake-LLM dry run on real evidence.

Tests (new): `tests/unit/test_llm_client.py`, `test_llm_cache.py`, `test_llm_prompts_select.py`, `test_hyde.py`, `test_cp5_stats.py`, `test_contamination.py`, `test_fixed_retriever.py`, `test_retrieval_report_headline.py`, `test_notebook_import_path.py`, `test_cp5_notebook.py`, `test_prompts_frozen.py`; `tests/integration/test_cp5_pipeline.py`.

## 3. Deliverables

| Item | Status | Note |
|---|---|---|
| 0a Neutral headline + paired method rows | Done | CP4 doc regenerated |
| 0b Notebook import path | Done | CP4 notebook; CP5 notebook has it; one test globs all notebooks |
| 0c Retrieval config as data | Done | |
| 1 LLMClient | Done | real client tested only against a stub server on 127.0.0.1, **never against a real Ollama** |
| 2 Response cache | Done | |
| 3 Prompts + closed-set validation | Done | frozen (see section 7) |
| 4 HyDE | Done | |
| 5 Evaluation commands | Done (code); **not run with a real model** | |
| 6 Contamination split | Done (code); **no real-run counts** | see note below |
| 7 Models | Configured only | tags `qwen2.5-coder:7b-instruct`, `llama3.1:8b` are requests; **availability, size and digests unchecked** |
| 8 Colab notebook | Done, **not executed in Colab** | fake dry run on real evidence done |
| 9 Tests | Done | |
| 10 Results document | Generator done; **document not produced** (no real run) | |

Contamination, from the committed case lists (date = advisory `created`): D1: 150 cases, 132 dated, 18 undated; with a Dec 2023 cutoff 111 post-cutoff (11 from 2024, 7 from 2025, 93 from 2026), 21 pre. D4: 120 cases, 14 undated; 98 post-cutoff with Dec 2023. Cutoffs: Llama 3.1 8B = "December 2023" per Meta's model card, **read only through third-party copies** (search results), so the owner should confirm on the official card; Qwen2.5-Coder = **not documented** (only third-party listings said "Jun 2024"), so for it every case is "possibly seen" and its headline uses all dated cases, flagged.

## 4. Test evidence

```
$ .venv/bin/python -m pytest tests -q -rs          (unit + contract + integration, full)
531 passed, 11 skipped in 130.24s (0:02:10)
  skips: 9 pgvector contract tests (psycopg not installed here; CI runs them), 2 opt-in network smoke tests
$ (cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 go test -count=1 ./...)
ok  	vulntrace/helper	0.261s
CI (GitHub Actions, branch run #45-#55): every completed run `success`; latest checked: run 55 on fe55458,
https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39724280340 (the final commit e27b8ef, which only adds a package-data glob, had not been checked when this report was written).
```

Real-evidence rebuild in this session:

```
$ python -m vulntrace dataset materialize --set d4
D4 materialize: 120 cases in 1164.3s; actions {'built': 94, 'reused': 26}; status counts {'AVAILABLE': 104, 'TRUNCATED': 14, 'EMPTY': 2} (case list: {'AVAILABLE': 103, 'EMPTY': 2, 'PSEUDO_VERSION_UNRESOLVED': 1, 'TRUNCATED': 14}); 1 case(s) differ   (GO-2020-0006, same as in CP4)
$ python -m vulntrace dataset materialize --set d1      (first pass)
D1 materialize: 150 cases in 375.3s; ... {'AVAILABLE': 139, 'EMPTY': 4, 'UNAVAILABLE': 7} ...; 9 case(s) differ
$ python -m vulntrace dataset materialize --set d1      (second pass, resume rule)
D1 materialize: 150 cases in 9.4s; actions {'skipped': 141, 'built': 9}; {'AVAILABLE': 144, 'EMPTY': 4, 'UNAVAILABLE': 2} (case list: same); 0 case(s) differ
```
The 9 first-pass differences were transient fetch failures (cause not diagnosed: the D1 summary records no git errors); the CP4 resume rule rebuilt exactly those 9. The `eval select` evidence gate correctly refused to run on the first-pass evidence (9 > 3 differences).

Dry run (fake LLM, fake embedder, real evidence; full log `CP5_DRYRUN.log`; 1m16s total):

```
E1 [fake]: 144 asked, 144 valid, 0 INVALID, 0 errors, 8 abstained, 14 retried; 264852 in / 1514 out tokens (fake count = chars/4)
S1 [fake] k=10: 118 asked, 118 valid, 0 INVALID, 5 abstained, 22 retried
S1 [fake] k=5:  118 asked, 118 valid, 0 INVALID, 9 abstained, 11 retried
HyDE: 120 cases, 0 empty, 0 truncated, 0 errors; bm25 + query: R@1=0.450 R@10=0.775 MRR=0.571 (n=120)
```
The BM25 `query` row reproduces CP4's committed BM25 `code+commits` row (MRR 0.571), which checks that the HyDE path with the original query changes nothing. The stand-in LLM's retry always answers validly, so the dry run shows 0 INVALID; the INVALID path is covered by unit and integration tests. The largest E1 prompt was 13112 estimated tokens (chars/4); real tokenizers count more, hence the notebook's 32768 context. These numbers say nothing about any language model.

## 5. Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Task 0 done; CP4 results regenerated | Met | `test_retrieval_report_headline.py`, `test_notebook_import_path.py`, `test_fixed_retriever.py`; regenerated CP4 doc |
| 2 | Endpoint rule | Met | `test_llm_client.py`: loopback accepted; each of the 9 required paid hosts rejected with port, upper case, trailing dot, sub-domain, userinfo, and when named in `VULNTRACE_LLM_ALLOWED_HOST`; look-alike and numeric-IP hosts rejected; redirects refused; proxies ignored |
| 3 | Closed-set validation, one retry, invalid/abstain counted, injection | Met | `test_llm_prompts_select.py` (20+ invalid forms, retry exactly once, no repair of fenced JSON, injected answer -> INVALID after 2 attempts) |
| 4 | Prompt builders cannot see gold/fix fields | Met | access-recording case test: only `summary`,`details` read; sentinel core/derived/fix strings absent; input dataclass fields asserted |
| 5 | Pipeline on fakes; dry run on real D1/D4 | Met | section 4, `CP5_DRYRUN.log`, `test_cp5_pipeline.py` |
| 6 | At least one real run committed | **Not met** | no Ollama/model access; see top of report |
| 7 | Prompt versions frozen before first real run | Met (vacuously) | `FROZEN.json` + `test_prompts_frozen.py`, frozen at commit fe55458; no real run has happened, so no post-result change exists |
| 8 | Contamination split with real cutoff, counts, headline post-cutoff | Partly | code, cutoffs and case-list counts done (section 3); real-run counts and a document using them do not exist; Llama cutoff unverified against the official card |
| 9 | Two denominators, paired intervals, size and date buckets | Partly | implemented in `llm_report.py` and rendered on fake data (dry-run document inspected, scratch only); no real numbers |
| 10 | All tests pass locally and in CI; nothing forbidden committed | Met (CI: through fe55458) | section 4; `git ls-files` shows no `data/`, `results/`, cache, zip or model files |
| 11 | Report + STATUS AWAITING_REVIEW | Met | this file |

## 6. Results

None. No real-model result files exist. (The CP4 table changes are in the regenerated CP4 document.)

## 7. Design deviations

1. **Mode 2 prompt includes commit subjects.** The spec lists "ID, signature, code". I also give each candidate the subjects of range commits that touched its file (capped at 500 chars, in an untrusted block), because the retriever being compared against saw them (the fixed `code+commits` chunk) and the CP4 gain came from them; without them S1 would compare a blind selector with a sighted retriever. It also makes "injection in a commit message" testable. The fix commit, gold and derived symbols are still absent. Say so if you want them removed.
2. Mode 1 has no commit-message field (FixEvidence stores none), so the commit-message injection fixture lives in Mode 2; Mode 1 is tested with an injected advisory.
3. "Prompt must not contain core or derived symbols" (Mode 1) is implemented as "the gold *label* is never an input". The fix-changed functions are the candidates, so gold functions appear among them by construction.
4. Output validation is stricter than the spec: exactly the keys `selected` and `abstain`; `abstain:true` with a non-empty list or `abstain:false` with an empty list is invalid. Two extra row statuses: `NOT_ASKED` (no candidates; scored as predicting nothing) and `ERROR` (server failure; three in a row abort the run and nothing is written).
5. Selection settings: `json_mode` (OpenAI `response_format: json_object`), temperature 0, seed 7, `max_tokens` 300. Whether Ollama honours `response_format` and `seed` on its OpenAI endpoint is **unverified here**.
6. `--dry-run` flag (fake LLM + fake embedder instead of `bge-small`; nothing else about the fixed retriever file can be overridden). Result files from it carry `dry_run: true` and the document prints a warning.
7. Results default to `results/cp5` (gitignored, as in CP4); committed copies go to `docs/results/cp5/`.
8. Tasks 0b and 0c share one commit (spec asked for separate commits).
9. Notebook context is 32768 tokens (not the 16384 first drafted) after the dry run showed prompts up to 13k estimated tokens.
10. Mode 2 candidate IDs are the range's own `candidate_id`s, presented in retrieval order and described as such to the model (so the selector can use the rank, as a pipeline would).
11. E1 includes cases whose evidence is EMPTY/UNAVAILABLE as predicting nothing for both methods (same rule as CP3's scoring), not asked, counted in `not_asked`.

Prompt freeze: v1 files frozen at fe55458. If a later session changes one after seeing real results it must add a `_v2` file and list it here with the reason (none yet).

## 8. Blockers and limitations

- No real model run (criterion 6) and therefore no answer to E1, S1 or HyDE.
- The real client has been tested only against a local stub; unverified against Ollama: `/api/tags` digest lookup, `response_format`, `seed`, `OLLAMA_CONTEXT_LENGTH` honoured, the tags `qwen2.5-coder:7b-instruct` and `llama3.1:8b`, T4 memory/time for 7-8B at 32k context.
- The notebook's Ollama install (`curl ... | sh`, `apt-get install zstd`) and the Colab flow are untested.
- Cutoffs: Qwen undocumented; Llama read via third-party copies.
- With a Dec 2023 cutoff most cases are post-cutoff, but the CP3 finding stands: 26% (CP4: 16%) of D4 cases have gold outside the candidates, so selection cannot fix them.
- Bootstrap on the headline groups will be wide for S1 denominator (a) (about 58-70 cases in the fake dry run).
- pgvector tests skipped locally (psycopg absent); CI covers them.

## 9. Suggestions for the next checkpoint

- Owner runs the Colab notebook; next session commits `docs/results/cp5/`, renders `CP5_LLM_RESULTS.md`, and verifies the zip's `colab_run.json` (digests, timings), the invalid rate and that no prompt text is in it.
- If the invalid rate is high for a model, report it first; do not widen the validator. A `_v2` prompt is the only allowed response, listed with the reason.
- Confirm Llama's cutoff on the official card before the document is committed.
- CP5b (lifting, caller/callee) is the lever for the cases with gold outside the candidates.

## 10. Git

Branch `claude/vulntrace-ai-build-o31zls` (fresh from `main` `f65b3f2`; no earlier CP5 branch existed). Every push succeeded.

```
e27b8ef CP5: package data for FROZEN.json
fe55458 CP5: freeze prompt templates v1 (hash test), dry-run log on real D1/D4 evidence, notebook context 32768
738ab9d CP5: record largest prompt in counts
862da2b CP5: stats tests, README commands
687e33b CP5: Colab notebook (Ollama, E1/S1/HyDE, gates, timings) and notebook tests
a7c60d9 CP5: results document renderer (results render --doc cp5) and tests
1b749b1 CP5: E1/S1/HyDE runners, stats, CLI (eval select, eval retrieval --hyde), model config, contamination buckets, integration tests
68733aa CP5: prompt templates v1, closed-set validation with one retry, HyDE, tests
57084ee CP5: LLMClient with loopback-only endpoint rule, fake LLM, on-disk response cache, tests
14054e5 CP5 0b: sys.path line in CP4 notebook + test; 0c: fixed retriever config file
0f3daa7 CP5 0a: neutral CP4 headline and paired method-vs-method rows; regenerate CP4 results
9f2a60a CP5: set IN_PROGRESS, record branch, copy task list
(+ the final report/STATUS commit)
```
