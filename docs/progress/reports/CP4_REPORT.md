# CP4 report: Retrieval stack - chunking, pgvector, BM25, embeddings, fusion, reranker

**Status: AWAITING_REVIEW, with acceptance criterion 6 NOT MET.** Every component is built and tested, and the
no-model part of the evaluation (random, size, B-ID, BM25 on all three chunk variants) ran on the real D4
evidence. The real embedding/reranker runs (dense, hybrid, hybrid+rerank) were **not** run: Hugging Face is
blocked from this session (proxy 403) and the session cannot drive Colab. They need the owner to run
`notebooks/cp4_retrieval_colab.ipynb` and hand the zip to the next session. The checkpoint's question is
answered only for BM25.

## 1. Environment

Printed in this session:

```
uname -a: Linux vm 6.18.44-fc-v140 #1 SMP PREEMPT_DYNAMIC @0 x86_64 x86_64 x86_64 GNU/Linux
/etc/os-release: Ubuntu 24.04.5 LTS
python3 --version: Python 3.13.16
go version: go version go1.24.7 linux/amd64
git --version: git version 2.43.0
docker --version: Docker version 29.9.1, build dfc520d   (daemon was not running; started with `dockerd` in
                  the session - Server Version: 29.9.1)
PostgreSQL 16 binaries present at /usr/lib/postgresql/16/bin; no pgvector extension installed (not used)
CPU: 4 cores, 15 GiB RAM, no GPU
venv packages: numpy 2.5.4, psycopg 3.3.6 (+binary), pgvector 0.5.1, pytest 9.1.1, jsonschema 4.26.0, PyYAML 6.0.3
```

Network checks (this session):

- `git ls-remote https://github.com/golang/vulndb HEAD` -> `e0bad562...` (the pinned commit). Git over HTTPS to
  GitHub works; all D1/D4 re-materialisation fetches succeeded.
- `https://pypi.org/simple/numpy/` -> 200. `proxy.golang.org` reachable (`helper fetch` succeeded).
- `https://huggingface.co` -> **CONNECT 403 from the egress proxy** (policy denial). No model can be downloaded here.
- `https://apt.postgresql.org` -> 403 (not needed; nothing installed system-wide).
- **Q10 (Docker Hub, pgvector image):** first `docker pull pgvector/pgvector:pg16` -> `429 Too Many Requests`;
  second attempt minutes later -> pulled (`sha256:7b822b0a...`). So: yes, with anonymous-pull rate limiting.
  CI pulls the same image as a service container (green, see section 4).

No paid API was configured or called anywhere. The only models touched are the deterministic fakes.

## 2. Files changed

65 files changed between `75f2f96` (CP4 release) and this report (excluding this report and STATUS.md).

Task 0:
- `src/vulntrace/dataset/materialize.py` (new) - `dataset materialize --set d4|d1`: rebuild evidence for the fixed case lists; candidate code extraction.
- `src/vulntrace/dataset/datasets.py` - `cluster_key`, `d4_cluster_key`, `date_bucket` (pre/post/undated), `RCLONE_CLUSTER`.
- `src/vulntrace/dataset/metrics.py` - `cluster_bootstrap_ci`, `summarize_clustered`.
- `src/vulntrace/dataset/build.py` - D4 case summaries carry `cluster_key` on future rebuilds.
- `src/vulntrace/dataset/report.py`, `schemas/vuln_case.schema.json` - additive `details` field (vulndb `description`).
- `src/vulntrace/eval/symbols_score.py` - clustered summaries, undated bucket, B-ID without TRUNCATED / without rclone.
- `src/vulntrace/eval/results_doc.py` - CP3 doc: cluster CIs, undated rows, subsets, widening table, re-materialisation section; `--doc cp4`.
- `docs/results/datasets/D4_cases.json` - only adds `cluster_key` per case and `cluster_count` (all CP3 fields unchanged, asserted).
- `docs/results/datasets/D4_materialize.json`, `D1_materialize.json` (new) - re-materialisation summaries (IDs, counts, actions, differences, timings).
- `docs/results/CP3_DATASETS_AND_BASELINES.md` - regenerated.

Retrieval stack:
- `src/vulntrace/retrieval/__init__.py`, `tokenize.py`, `bm25.py`, `ranking.py`, `fusion.py`, `chunking.py`, `query.py`, `dense.py`, `rerank.py`, `vectorstore.py`, `pgvector_store.py` (new) - D1-D5.
- `src/vulntrace/retrieval/migrations/001_code_chunks.sql` (new) - pgvector schema.
- `src/vulntrace/models/__init__.py`, `base.py`, `fakes.py`, `contract.py`, `registry.py`, `st_models.py` (new) - Embedder/Reranker interfaces, fakes, shared contract checks, model registry, sentence-transformers wrappers (lazy import).
- `src/vulntrace/eval/retrieval.py`, `retrieval_metrics.py`, `retrieval_report.py`, `cp4_plan.py` (new) - D6/D9 harness, metrics, renderer, notebook grid.
- `src/vulntrace/__main__.py` - `dataset materialize`, `eval retrieval`, `index build`, `results render --doc cp4`.
- `docker-compose.yml` (new) - pgvector/pgvector:pg16 on localhost.
- `.github/workflows/ci.yml` - installs `.[dev,db]`; new `pgvector` job with a service container and `VULNTRACE_REQUIRE_PG=1`.
- `pyproject.toml` - `numpy` base dependency; `[db]` (psycopg[binary], pgvector) and `[ml]` (sentence-transformers) extras; SQL package data.
- `notebooks/cp4_retrieval_colab.ipynb` (new) - D7.
- `docs/results/cp4/cases.json`, `docs/results/cp4/runs/*.json` (new, 256 KiB total) - real baseline + BM25 runs.
- `docs/results/CP4_RETRIEVAL_RESULTS.md` (new) - D9, generated.
- `README.md` - CP4 commands.

Tests (new unless noted):
- `tests/unit/test_bm25_rrf.py`, `test_chunking_query.py`, `test_retrieval_metrics.py`, `test_dense_rerank.py`, `test_cluster_stats.py`, `test_d4_selection.py`, `test_materialize_d1.py`, `test_cp4_notebook.py`, `test_committed_results_size.py`; `test_report.py`, `test_results_doc.py` (extended).
- `tests/contract/test_vector_store.py`, `test_model_fakes.py`.
- `tests/integration/test_materialize.py`, `test_retrieval_harness.py`.

## 3. Deliverables

| Item | Status | Note |
|---|---|---|
| Task 0a: materialise D4 evidence | Done | 120/120 cases, 1366.9 s; 1 case differs (listed). D1 also materialised (needed for 0b's E0). |
| Task 0b: cluster-aware statistics | Done | CP3 doc regenerated with cluster CIs, widening table, B-ID without TRUNCATED. |
| Task 0c: undated bucket | Done | Every date split in CP3 and CP4 docs has `undated`. |
| D1 Chunking | Done | Three variants, caps counted, id masking before caps, query-leakage tests, shared per `range_key`. |
| D2 VectorStore + two backends | Done | Shared 9-test suite green on both, locally and in CI; Q10 answered. |
| D3 BM25 | Done | In-repo, hand-computed tests, documented tokeniser. |
| D4 Dense retrieval | **Partly done** | Code, fake, sentence-transformers wrapper, embedding cache done; **no real model run** (Hugging Face blocked here). Models chosen: `BAAI/bge-small-en-v1.5`, `flax-sentence-embeddings/st-codesearch-distilroberta-base`; revisions are recorded at run time, so none are recorded yet. |
| D5 Fusion + reranking | **Partly done** | RRF (k=60) tested; Reranker interface, fake, cross-encoder wrapper (`cross-encoder/ms-marco-MiniLM-L-6-v2`, `BAAI/bge-reranker-base`), top-50 head rerank done; **no real reranker run**. |
| D6 Evaluation harness | Done (code); **partly run** | All configs implemented and tested on fakes; real runs only for random, size, B-ID, B-ID-only, BM25 x 3 variants. |
| D7 Colab notebook | Done, **not executed in Colab** | Notebook plus a dry run of its exact grid on the real D4 evidence with fakes (16 runs, 91 s, scratch only). No Colab running times exist yet. |
| D8 Tests | Done | See section 4. |
| D9 Results document | Done for what ran | Generated by code; states in its first paragraph what beats B-ID, and that dense/hybrid/rerank were not run. |

## 4. Test evidence

Commands run in this session, with their summary lines:

```
$ VULNTRACE_REQUIRE_PG=1 .venv/bin/python -m pytest tests/unit tests/contract -q -rs
329 passed in 1.74s
```
(unit + contract, with the local pgvector container up; the 9 shared VectorStore tests ran on **both** backends.)

```
$ .venv/bin/python -m pytest tests/contract/test_vector_store.py -q          # container up
18 passed in 0.53s
$ .venv/bin/python -m pytest tests/contract/test_vector_store.py -q -rs      # container stopped
9 passed, 9 skipped in 0.19s     (skip reason: "SKIPPED pgvector backend: no PostgreSQL + pgvector reachable at VULNTRACE_PG_DSN (OperationalError: ... Connection refused ...")
$ VULNTRACE_REQUIRE_PG=1 ... (container stopped)
9 passed, 9 errors in 0.25s      (the CI setting turns a missing database into a failure)

$ (cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 go test -count=1 ./...)
ok  	vulntrace/helper	0.324s

$ .venv/bin/python -m pytest tests/integration -q -rs
66 passed, 2 skipped in 137.05s (0:02:17)
SKIPPED: tests/integration/test_network_smoke.py (x2): opt-in network test (set VULNTRACE_NETWORK_TESTS=1) - unchanged from CP3, never in CI
```

Real runs:

```
$ python -m vulntrace dataset materialize --set d4
D4 materialize: 120 cases in 1366.9s; actions {'built': 94, 'reused': 26}; status counts {'AVAILABLE': 104, 'TRUNCATED': 14, 'EMPTY': 2} (case list: {'AVAILABLE': 103, 'EMPTY': 2, 'PSEUDO_VERSION_UNRESOLVED': 1, 'TRUNCATED': 14}); 1 case(s) differ
  DIFFERS GO-2020-0006: status PSEUDO_VERSION_UNRESOLVED -> AVAILABLE; candidate_count 0 -> 1; commit_count 0 -> 4
$ python -m vulntrace dataset materialize --set d1
D1 materialize: 150 cases in 288.5s; actions {'built': 150}; status counts {'AVAILABLE': 144, 'EMPTY': 4, 'UNAVAILABLE': 2} (case list: {'AVAILABLE': 144, 'EMPTY': 4, 'UNAVAILABLE': 2}); 1 case(s) differ
  DIFFERS GO-2026-4360: candidate_count 4 -> 5
$ python -m vulntrace eval symbols --strategy e0
precision=0.585 recall=0.847 f1=0.631 exact_match=46
$ python -m vulntrace eval symbols --strategy id-search
precision=0.503 recall=0.303 f1=0.201 exact_match=7
$ python -m vulntrace results render --doc cp3 --input results/cp3 --out docs/results/CP3_DATASETS_AND_BASELINES.md
$ python -m vulntrace eval retrieval --config random --config size --config bid --config bid-only --config bm25 --out docs/results/cp4
random [-]: R@1=0.200 R@10=0.475 MRR=0.281 (n=120, all scored cases)
size [-]: R@1=0.217 R@10=0.550 MRR=0.310 (n=120, all scored cases)
bid [-]: R@1=0.283 R@10=0.642 MRR=0.397 (n=120, all scored cases)
bid-only [-]: R@1=0.150 R@10=0.300 MRR=0.208 (n=120, all scored cases)
bm25 [code_only]: R@1=0.392 R@10=0.725 MRR=0.507 (n=120, all scored cases)
bm25 [code+commits]: R@1=0.450 R@10=0.775 MRR=0.571 (n=120, all scored cases)
bm25 [code+commits_idmasked]: R@1=0.450 R@10=0.775 MRR=0.572 (n=120, all scored cases)
$ python -m vulntrace results render --doc cp4 --input docs/results/cp4 --out docs/results/CP4_RETRIEVAL_RESULTS.md
```

Dry run of the notebook grid (`cp4_plan.configs(gpu=True, dry_run=True)`) on the real D4 evidence, fakes only,
output in the session scratchpad (not committed): 16 runs, `TOTAL_SECONDS=91`.

CI: all completed runs on this branch are green: runs #18 to #33, 16 runs, each `conclusion: success` (GitHub
Actions API, this session). Latest: https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39653095845. First
run with the pgvector job: https://github.com/AMAN-PRIYANSH/REPO-MIND/actions/runs/39649425037 (job `pgvector`
success). Evidence that it really exercised the database: the service container's log in that job shows
`ERROR: different vector dimensions 2 and 3`, which is the query `test_contract_errors` sends on purpose.

## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Task 0 done; status differences listed; cluster bootstrap + undated in CP3 results, regenerated | Met | `D4_materialize.json`, `D1_materialize.json`; CP3 doc sections "Evidence re-materialisation", cluster CI columns, undated rows, widening table |
| 2 | Both backends pass one shared suite; pgvector job in CI; Q10 answered | Met | `tests/contract/test_vector_store.py` (18 passed locally); CI job `pgvector` green; Q10: pull works, first attempt hit a 429 |
| 3 | BM25, RRF, metrics, cluster bootstrap match hand-computed tests | Met | `test_bm25_rrf.py`, `test_retrieval_metrics.py`, `test_cluster_stats.py` in the 329 passed |
| 4 | Three chunk variants; query provably excludes gold/fix fields | Met | `test_chunking_query.py` (access-recording case: only `summary`/`details` read; sentinel symbols/fix SHA absent; `build_query` rejects a raw case) |
| 5 | Harness end to end on fakes in default tests; no network or model | Met | `test_retrieval_harness.py` blocks sockets and makes `sentence_transformers`/`torch`/`transformers` unimportable; runs every config and renders the doc; CI green |
| 6 | At least one real run of BM25, dense, hybrid, hybrid+rerank with variants, from Colab | **Not met** | Only BM25 (and the baselines) ran for real, here. Dense/hybrid/rerank need Hugging Face models: blocked here (proxy 403) and the session cannot run Colab. Notebook ready; owner run needed. |
| 7 | Two denominators, size buckets, date buckets, rclone-removed, cluster intervals | Met (for the runs that exist) | `CP4_RETRIEVAL_RESULTS.md` |
| 8 | Random + B-ID in the same tables; first paragraph says whether retrieval beats B-ID | Met | First paragraph: BM25 `code+commits` (both variants) clearly beats B-ID on MRR; `code_only` does not by the non-overlap rule |
| 9 | All tests pass locally and in CI | Met | Section 4 |
| 10 | No models, embeddings, `data/`, caches or vulndb text committed | Met | `git ls-files \| grep -E "^data/\|\.npz$\|\.npy$\|\.safetensors\|\.bin$\|vulndb-src\|\.yaml$\|\.env"` -> no output; committed JSON holds ids, counts, ranks and cluster keys only |
| 11 | Report in wrapper format; STATUS `AWAITING_REVIEW` | Met | This file; STATUS.md |

## 6. Results

Copied from `docs/results/CP4_RETRIEVAL_RESULTS.md` (generated by code from `docs/results/cp4/`). Only
no-model configurations exist.

**Retrieval configurations that clearly beat B-ID** over all 120 scored D4 cases (non-overlapping 95% cluster-bootstrap intervals): `bm25 · code+commits_idmasked` (mrr), `bm25 · code+commits` (mrr). The best by MRR is `bm25 · code+commits_idmasked`: MRR 0.572 [0.495, 0.653] vs B-ID 0.397 [0.317, 0.478]; paired difference 0.175 [0.104, 0.248].

In the `>100`-candidate bucket, where ranking matters, `bm25 · code+commits_idmasked` has MRR 0.526 [0.363, 0.664] vs B-ID 0.211 [0.052, 0.362] (n=38, 22 clusters).

**Not run yet:** dense, hybrid, hybrid+rerank configurations need the real embedding/reranker models and are produced by `notebooks/cp4_retrieval_colab.ipynb`. Until then this document compares only what is listed below; it is not the checkpoint's full answer.

Variant `code+commits` (each variant has the same tables in the results doc):

### All scored cases - denominator (b), n = 120

| Config | n (clusters) | R@1 | R@5 | R@10 | R@20 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|---|
| random | 120 (94) | 0.200 | 0.375 | 0.475 [0.376, 0.579] | 0.575 | 0.281 [0.209, 0.366] | 0.260 |
| size | 120 (94) | 0.217 | 0.400 | 0.550 [0.457, 0.653] | 0.625 | 0.310 [0.236, 0.392] | 0.311 |
| bid | 120 (94) | 0.283 | 0.558 | 0.642 [0.539, 0.733] | 0.692 | 0.397 [0.317, 0.478] | 0.406 |
| bid-only | 120 (94) | 0.150 | 0.300 | 0.300 [0.175, 0.427] | 0.308 | 0.208 [0.122, 0.296] | 0.222 |
| bm25 · code+commits | 120 (94) | 0.450 | 0.717 | 0.775 [0.690, 0.856] | 0.800 | 0.571 [0.495, 0.651] | 0.549 |

### Gold inside the candidate set - denominator (a), n = 101

| Config | n (clusters) | R@1 | R@5 | R@10 | R@20 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|---|
| random | 101 (78) | 0.238 | 0.446 | 0.564 [0.446, 0.692] | 0.683 | 0.334 [0.246, 0.434] | 0.309 |
| size | 101 (78) | 0.257 | 0.475 | 0.653 [0.535, 0.779] | 0.743 | 0.368 [0.275, 0.480] | 0.370 |
| bid | 101 (78) | 0.337 | 0.663 | 0.762 [0.663, 0.848] | 0.822 | 0.472 [0.384, 0.563] | 0.482 |
| bid-only | 101 (78) | 0.178 | 0.356 | 0.356 [0.206, 0.496] | 0.366 | 0.248 [0.141, 0.349] | 0.264 |
| bm25 · code+commits | 101 (78) | 0.535 | 0.851 | 0.921 [0.848, 0.981] | 0.950 | 0.678 [0.597, 0.754] | 0.652 |

### By candidate-set size

Cases per bucket - <=10: (a) 24, (b) 34; 11-100: (a) 41, (b) 48; >100: (a) 36, (b) 38.

| Config | <=10: R@10 (a) | <=10: MRR (a) | <=10: R@10 (b) | <=10: MRR (b) | 11-100: R@10 (a) | 11-100: MRR (a) | 11-100: R@10 (b) | 11-100: MRR (b) | >100: R@10 (a) | >100: MRR (a) | >100: R@10 (b) | >100: MRR (b) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| random | 1.000 | 0.814 | 0.706 [0.529, 0.853] | 0.575 [0.413, 0.733] | 0.634 | 0.284 | 0.542 [0.400, 0.692] | 0.242 [0.161, 0.334] | 0.194 | 0.072 | 0.184 [0.045, 0.348] | 0.068 [0.027, 0.120] |
| size | 1.000 | 0.829 | 0.706 [0.529, 0.853] | 0.585 [0.419, 0.742] | 0.756 | 0.338 | 0.646 [0.532, 0.771] | 0.288 [0.202, 0.378] | 0.306 | 0.095 | 0.289 [0.161, 0.464] | 0.090 [0.046, 0.167] |
| bid | 1.000 | 0.814 | 0.706 [0.529, 0.853] | 0.575 [0.413, 0.733] | 0.902 | 0.491 | 0.771 [0.642, 0.885] | 0.419 [0.305, 0.527] | 0.444 | 0.222 | 0.421 [0.133, 0.615] | 0.211 [0.052, 0.362] |
| bid-only | 0.250 | 0.250 | 0.176 [0.059, 0.324] | 0.176 [0.059, 0.324] | 0.488 | 0.324 | 0.417 [0.233, 0.580] | 0.277 [0.155, 0.394] | 0.278 | 0.159 | 0.263 [0.000, 0.522] | 0.151 [0.000, 0.333] |
| bm25 · code+commits | 1.000 | 0.917 | 0.706 [0.529, 0.853] | 0.647 [0.485, 0.794] | 0.927 | 0.649 | 0.792 [0.667, 0.900] | 0.554 [0.435, 0.679] | 0.861 | 0.552 | 0.816 [0.625, 0.962] | 0.523 [0.363, 0.659] |


### Without the nine-case rclone cluster - denominator (b)

| Config | n (clusters) | R@1 | R@5 | R@10 | R@20 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|---|
| random | 111 (93) | 0.216 | 0.405 | 0.505 [0.405, 0.606] | 0.604 | 0.302 [0.228, 0.379] | 0.280 |
| size | 111 (93) | 0.234 | 0.432 | 0.577 [0.486, 0.673] | 0.658 | 0.331 [0.260, 0.412] | 0.334 |
| bid | 111 (93) | 0.279 | 0.532 | 0.622 [0.527, 0.718] | 0.667 | 0.381 [0.298, 0.464] | 0.392 |
| bid-only | 111 (93) | 0.135 | 0.252 | 0.252 [0.152, 0.358] | 0.252 | 0.177 [0.104, 0.256] | 0.194 |
| bm25 · code+commits | 111 (93) | 0.441 | 0.694 | 0.757 [0.670, 0.836] | 0.784 | 0.560 [0.477, 0.647] | 0.536 |

## Paired differences against B-ID and random

Method minus baseline, paired cluster bootstrap, denominator (b). An interval that excludes 0 is a difference in the paired analysis; the headline uses the evaluation plan's stricter non-overlap rule.

| Config | ΔMRR vs B-ID (all) | ΔR@10 vs B-ID (all) | ΔMRR vs B-ID (>100) | ΔMRR vs random (all) |
|---|---|---|---|---|
| bm25 · code+commits | 0.173 [0.103, 0.246] | 0.133 [0.063, 0.209] | 0.312 [0.197, 0.525] | 0.289 [0.199, 0.379] |
| bm25 · code+commits_idmasked | 0.175 [0.104, 0.248] | 0.133 [0.063, 0.209] | 0.316 [0.202, 0.525] | 0.291 [0.199, 0.381] |
| bm25 · code_only | 0.110 [0.037, 0.187] | 0.083 [0.025, 0.150] | 0.213 [0.093, 0.399] | 0.226 [0.141, 0.309] |

## Leakage control: do advisory identifiers in commit messages explain the gains?

Chunks whose commit subjects contain an advisory identifier: 524; chunks whose code or doc comment contains one: 5. The query (summary + details only) contains an identifier in 0 of 120 cases. **So no lexical match on an advisory identifier is possible in this setup, and the masked variant cannot test that channel**: any difference between `code+commits` and `code+commits_idmasked` comes only from the changed tokens (document length, IDF) or, for dense models, from the slightly different text.

A different, legitimate shortcut: in 17 of 120 cases the advisory text names a gold function (its bare name as a case-sensitive whole word). This is real advisory text, not a leak, but it hands lexical retrieval a direct hit, so MRR is also shown without those cases (denominator (b)):

| Config | MRR all | MRR without named-gold cases |
|---|---|---|
| random | 0.281 [0.209, 0.366] | 0.297 [0.223, 0.386] |
| bid | 0.397 [0.317, 0.478] | 0.400 [0.315, 0.484] |
| bm25 · code+commits | 0.571 [0.495, 0.651] | 0.545 [0.459, 0.630] |
| bm25 · code+commits_idmasked | 0.572 [0.495, 0.653] | 0.546 [0.460, 0.632] |
| bm25 · code_only | 0.507 [0.433, 0.586] | 0.482 [0.403, 0.566] |

Variant comparison (MRR, denominator (b); differences are paired):

| Config | MRR code_only | MRR code+commits | MRR idmasked | Δ commits − idmasked | Δ commits − code_only |
|---|---|---|---|---|---|
| bm25 | 0.507 [0.433, 0.586] | 0.571 [0.495, 0.651] | 0.572 [0.495, 0.653] | -0.001 [-0.003, 0.000] | 0.064 [0.028, 0.102] |


CP3 regeneration (task 0b), copied from `docs/results/CP3_DATASETS_AND_BASELINES.md`:

| Subset | Cases | Precision | Recall | F1 | F1 cluster CI |
|---|---|---|---|---|---|
| All | 120 | 0.503 [0.399, 0.615] (n=41) | 0.303 [0.227, 0.390] (n=120) | 0.201 [0.145, 0.267] (n=120) | [0.114, 0.284] (94 clusters) |
| Without TRUNCATED | 106 | 0.497 [0.374, 0.620] (n=32) | 0.258 [0.178, 0.344] (n=106) | 0.174 [0.117, 0.241] (n=106) | [0.107, 0.255] (88 clusters) |
| Without the nine-case rclone cluster | 111 | 0.497 [0.383, 0.621] (n=32) | 0.247 [0.169, 0.325] (n=111) | 0.167 [0.109, 0.228] (n=111) | [0.100, 0.237] (93 clusters) |

| Baseline | Metric | Case-CI width | Cluster-CI width | Ratio |
|---|---|---|---|---|
| E0 (D1) | precision | 0.117 | 0.119 | 1.01× |
| E0 (D1) | recall | 0.112 | 0.110 | 0.98× |
| E0 (D1) | f1 | 0.111 | 0.108 | 0.97× |
| B-ID (D4) | precision | 0.216 | 0.217 | 1.01× |
| B-ID (D4) | recall | 0.163 | 0.270 | 1.66× |
| B-ID (D4) | f1 | 0.122 | 0.170 | 1.40× |


**How to read these numbers (my assessment, not generated):**

- BM25 with commit subjects beats B-ID on MRR over all 120 cases by the plan's strict rule. In the `>100` bucket
  (38 cases, 22 clusters) the paired difference also excludes 0, but both intervals there are wide.
- The gain does **not** come from advisory IDs: no query contains one (0/120), so a lexical ID match is
  impossible, and the masked variant scores the same (Δ −0.001 [−0.003, 0.000]). This also means the
  masked variant is a **weak** test in this setup, and the results doc says so. Commit subjects help through
  their words (Δ vs `code_only` +0.064 [0.028, 0.102]), e.g. a fix commit's subject describing the bug.
- 17/120 queries name a gold function. Without those cases BM25 `code+commits` drops from 0.571 to 0.545,
  still well above B-ID (0.400). Part of BM25's lead is that shortcut, but not most of it.
- B-ID's ranking variant ("B-ID, then random") is the fair comparison for ranking metrics. Strict B-ID
  (`bid-only`) is weaker (MRR 0.208) because it abstains in 78/120 cases.
- 19/120 cases have no core symbol among their candidates, so they are misses for every method. This is the
  ceiling, and it is why denominator (a) (n=101) numbers are higher.

## 7. Design deviations

1. **`dataset materialize --set d1` added** (not asked for). Task 0b requires E0 with cluster intervals, and
   E0 needs D1's fix evidence, which was also gone. Same rules as D4: fixed IDs, resumable, differences listed.
2. **`VulnCase.details` added** (vulndb `description`, additive schema change). The spec's query is "summary
   and details", and CP3's VulnCase had no details. 77/120 D4 reports have no description, so their query is
   the one-line summary only.
3. **Candidate code goes in a separate `data/candidate_code/<id>.json`** instead of extending the ReleaseRange
   schema. This keeps CP3's schema and baselines untouched. Doc comments are found in Python (contiguous `//`
   lines above the declaration) and the helper is unchanged; `/* */` doc comments are not recognised.
4. **Chunk shape differs from DATA_MODEL's `CodeChunk`.** It adds `range_key`, the variant, commit subjects and
   `body_side`; embeddings are not stored on the chunk; `chunk_id` is `range_key|candidate_id|file|symbol`. No
   `code_chunk.schema.json` was added (ADR-012 would prefer one); the pgvector table is the stored shape.
5. **`Embedder.embed_query` and `info()`** extend the informal interface, because bge models expect a query
   instruction prefix.
6. **B-ID in the ranking tables** has two forms: `bid` (B-ID's candidates first, then the rest, both in seeded
   random order) and `bid-only` (strict). CP3's B-ID is a set, not a ranking; some conversion was needed.
7. **Recall@k is a hit rate** (any gold in the top k), as the evaluation plan defines it, not a fraction of
   gold found.
8. **Paired cluster-bootstrap differences** are reported in addition to the plan's non-overlap rule. The
   headline uses only the stricter non-overlap rule.
9. **Gold-name control group** (`query_names_gold`) added to expose a shortcut the spec did not list.
10. **Tasks 0b and 0c share commits** (`b0d7120` code, `dcdac10` regeneration). The spec asked for one commit
    each. Both changes touch the same scorer function, and splitting them would have been artificial.
11. **Code embedder choice (Q6):** `st-codesearch-distilroberta-base`, a native sentence-transformers model
    trained on CodeSearchNet (which includes Go), so no remote model code has to run in Colab. A stronger
    choice like `jina-embeddings-v2-base-code` needs `trust_remote_code`; I judged that less reliable on Colab.
12. **pgvector:** the `vector` column has no fixed dimension (two models share one table), so exact
    brute-force search with no ANN index. This is fine at ≤15.5k chunks per range, and every search must
    filter on `embedding_model`. psycopg/pgvector are in a `[db]` extra, not the base install.
13. **Caps chosen:** 2000 characters per chunk (about 512 model tokens, so BM25 and dense models see roughly
    the same text) and 500 for the commit line. 2402 of 36,801 `code+commits` chunks hit the chunk cap; 5823
    had their commit line cut.
14. **Evaluation runs use the in-memory store.** pgvector is exercised by the contract suite and by
    `index build --store pgvector`, but no evaluation in this checkpoint ran through it.

## 8. Blockers and limitations

- **No real dense, hybrid or rerank run (criterion 6 not met).** Hugging Face is blocked here (proxy 403) and
  I cannot run Colab. `notebooks/cp4_retrieval_colab.ipynb` has **not** been executed in Colab: its cell
  mechanics (`!` commands with `{var}` interpolation, `%cd`, Go install, `files.download`) are untested, and
  only the grid it runs was dry-run here. Expect possible small fixes on first use.
- **Colab will re-materialise D4 itself.** Its evidence may differ from this session's, for example if a tag
  moved. `eval retrieval` refuses to mix runs from a different `cases.json`, so the next session must compare
  the Colab `cases.json` with `docs/results/cp4/cases.json`, report differences, and render from one
  consistent bundle. If the Colab bundle contains every config, it should replace the committed BM25 runs.
- **Two re-materialisation differences from CP3**, both listed in the docs. GO-2020-0006 now resolves its
  pseudo-version (CP3: unresolved). GO-2026-4360 now has all 3 fix commits fetched (CP3 recorded 1 as
  unfetchable). CP3's logs are gone, so I cannot confirm the CP3 failures were transient, only that the
  new evidence is consistent (GO-2020-0006 resolves to the advisory's own fix commit).
- **CP3 numbers moved slightly** after regeneration: B-ID recall 0.295 → 0.303, exact 6 → 7; E0 recall
  0.845 → 0.847. That is the effect of the two differences above.
- **Pseudo-replication is wider than finding 1 said.** 120 cases form 94 clusters. Besides the nine-case
  rclone range there is a second rclone range (5 cases), gobgp (5), oras-go (4), hugo (3), excelize (3) and
  four pairs. The cluster bootstrap covers all of them. The "without rclone" rows drop only the nine-case
  cluster, as specified.
- **Docker** was installed but its daemon was not running; I started `dockerd` in the session. The pull hit a
  Docker Hub 429 once.
- **Large ranges are dominated by new code.** 25,600 of 36,801 chunks are fixed-side-only functions, mostly
  from two ranges (aws-sdk-go 1.30→1.34: 13,187 of 13,805 candidates are new). The `body_side` flag
  records this.
- The ceiling investigation's "exists unchanged" check is still CP3's `git grep` approximation.

## 9. Suggestions for the next checkpoint

- First, run the Colab notebook, commit its zip contents under `docs/results/cp4/`, and re-render. Report
  model revisions and GPU times. Only then are Q1-Q4 answered.
- If dense or hybrid do not beat BM25 `code+commits`, CP5's S1 should probably use BM25 `code+commits` top-k.
- HyDE (Q5) only changes the query side, and the queries are short (median 109 characters; 77/120
  summary-only). That is where it may help most; measure it against the `query_names_gold` control.
- Consider a stricter gold match (package + symbol) now that candidate import paths exist. Name-level matching
  can count same-named functions in other packages as gold.

## 10. Git

Branch: `claude/vulntrace-ai-build-9qhbjg` (fresh from `main` at `75f2f96`; no continuation candidate
existed). Commits (`git log --oneline 75f2f96..HEAD`, newest first, before this report's commit):

```
895647d CP4: results doc warns at the top when any run used a FAKE model
dcdac10 CP4 tasks 0b/0c: regenerate CP3 results with cluster intervals and an undated bucket
f3739d6 CP4 task 0a (D1 counterpart): D1 fix evidence re-materialised for the 150 fixed IDs
7cea026 CP4 D6/D9: real baseline and BM25 runs on D4 (no model needed), results doc rendered
35ad765 CP4: record git state before eval retrieval writes its output (repo_dirty was self-inflicted)
7933173 CP4 D6: report cases whose advisory text names a gold function, with a control group
5e9b8b0 CP4 task 0a: D4 evidence re-materialised; cluster_key added to D4_cases.json
9689322 CP4: README commands; size limits for committed result files (512 KiB/file, 2 MiB for cp4/)
64e7c7f CP4: update STATUS.md task list
1f1c607 CP4 D7: Colab notebook for the real retrieval run, with the grid defined in code
1f6dd9d CP4 D6: retrieval evaluation harness, metrics, CLI, and the CP4 results renderer
b74cca2 CP4 D4/D5: dense retrieval with a content-hash embedding cache; head-only reranking
39ff46d CP4 D1: function-level chunks with three leakage-control variants; summary+details query
b357700 CP4 D2: CI job running the VectorStore suite against a pgvector service container
1d8d2cf CP4 D2: VectorStore interface, in-memory and pgvector backends, one shared suite
78c9c24 CP4 D3 (+RRF of D5): in-repo BM25, code-aware tokeniser, RRF k=60, seeded tie-breaking
b0d7120 CP4 tasks 0b/0c (code): cluster bootstrap, undated date bucket, B-ID subsets
8652bf4 CP4 task 0a: dataset materialize --set d4 rebuilds D4 evidence from the fixed case list
e34b77d CP4: set IN_PROGRESS on claude/vulntrace-ai-build-9qhbjg; copy task list
```

Every commit above was pushed to `origin/claude/vulntrace-ai-build-9qhbjg` right after it was made, and no push
failed. No pull request was opened, as the session instructions say: the supervising assistant merges after
review.

---

# Fix round (CHANGES_REQUESTED, FIX-1..FIX-6)

Session branch note: this session's container was assigned `claude/vulntrace-ai-build-v2kb3a`; it was fast-forwarded to
`claude/vulntrace-ai-build-9qhbjg` (`6a75cb7`) and pushed to `claude/vulntrace-ai-build-9qhbjg`, as the review notes and the
owner instructed. CP5 was not started. The retrieval results in `docs/results/` were not touched.

## Environment (fix session)

Linux 6.18; Python 3.13.16 (project-local venv outside the repo, `pip install -e ".[dev,db]"`); go1.24.7; git 2.43.0;
Docker 29.9.1 installed but **no PostgreSQL/pgvector reachable**, so the 9 pgvector contract tests skipped. GitHub reachable
(`git ls-remote` worked). Hugging Face and Google Drive/Colab not available here.

## Deliverables

| Fix | State | What |
|---|---|---|
| FIX-1 diagnose | done, **root cause NOT established** | `python -m vulntrace dataset diagnose --case ID` builds one case without writing to `data/` and prints every git command with exit code and stderr. Run on `GO-2020-0038` with the cache on local disk (ext filesystem): `AVAILABLE`, 81 candidates, 99 git calls, 2 exit-128 (`git show` of files absent in the old tree, expected), no differences from the case list. This shows the code works on local disk. It does **not** show that Drive was the cause: there is no Drive here. The Colab run with the fixed notebook is the test. |
| FIX-2 resume rule | done | `is_complete(case_id, data_dir, expected)` also requires status and counts to match the case list; the "reused" path copies only a result that matches the target's expected status/counts; a failed result is never registered as a reuse source. Same rule for D1. |
| FIX-3 git errors | done | `git_error` (first stderr line) is stored in the release-range file for TAG_NOT_FOUND / PSEUDO_VERSION_UNRESOLVED (schema gained an optional `git_error`); the summary has `top_git_errors` and the CLI prints the top 3. |
| FIX-4 notebook | done, **not run in Colab** | git/vulndb cache `/content/cache`, evidence `/content/data` (local); Drive keeps embeddings, materialise summary, results. New gate cell raises `SystemExit` if the evidence differs in >3 cases or has 0 candidates. |
| FIX-5 refuse empty runs | done | `eval/evidence_gate.py`; `eval retrieval` and `index build` exit 2 and write nothing; notebook gate uses the same functions. |
| FIX-6 tests | done | see below |

## Test evidence

- `python -m pytest tests -q` (full, incl. Go and git integration): `399 passed, 11 skipped in 154.26s`. Skips: 9 pgvector
  (no database here), the opt-in network smoke test, and one more opt-in/model test (not individually inspected beyond the
  list printed by `-rs`, which showed the pgvector and network ones above).
- New tests: `tests/unit/test_materialize_resume.py`, `tests/unit/test_evidence_gate.py` (29 passed together with the
  touched notebook/D1/schema tests, run alone).
- CI status of the pushed commits was **not checked** in this session.

## Design deviations

- `schemas/release_range.schema.json` gained an optional `git_error` property (needed to store the error in the evidence file).
- Three existing assertions were changed because the required behaviour changed (not to hide a failure): the D1 and D4
  resume tests (a mismatching result is now rebuilt on a re-run) and the notebook test (data on local disk).
- A case whose true result legitimately differs from the case list (1 known in D4, 1 in D1) is now rebuilt on every resume
  instead of skipped; slower, not wrong.
- `dataset materialize` still exits 0 when cases differ; the gate (notebook / eval commands) is what stops the run.

## Limitations

- The cause of the first invalid Colab run is still unproven; Drive is only a hypothesis.
- No Colab run, no GPU, no real models here. Criterion 6 still needs the owner's new Colab run.

## Git

Commits on `claude/vulntrace-ai-build-9qhbjg` after `6a75cb7`: `5dfde4e` (set IN_PROGRESS), `5ed5fb3` (FIX-1..6), plus this
report's commit; pushes succeeded.


## Supervisor addendum (22 Oct 2026)

Acceptance criterion 6 is met: the owner ran the fixed notebook in Colab (T4); the valid bundle was committed to `docs/results/cp4/` and `docs/results/CP4_RETRIEVAL_RESULTS.md` was regenerated from it. See the supervisor review notes in `checkpoints/CP4.md`.
