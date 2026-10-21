# CP4 - Retrieval stack: chunking, pgvector, BM25, embeddings, fusion, reranker

- Recommended model: **Opus 5.5**, effort **high**
- Branch: this session's own `claude/...` branch (see `CLAUDE.md` section 5)
- Target duration: 3-4 days
- Required reading: `CLAUDE.md`, `docs/progress/STATUS.md`, `docs/implementation/checkpoints/CP3.md` (**review notes at the end - findings 1-5 bind this checkpoint**), `docs/progress/reports/CP3_REPORT.md`, `docs/results/CP3_DATASETS_AND_BASELINES.md`, `docs/design/DATA_MODEL.md`, `docs/design/INTERFACES_AND_CONTRACTS.md` (section 4), `docs/design/PROJECT_STRUCTURE.md`, `docs/evaluation/DATASET_STRATEGY.md` (D4), `docs/evaluation/EVALUATION_PLAN.md` (retrieval metrics, uncertainty), `docs/testing/TESTING_STRATEGY.md`, the ADRs about retrieval and the vector store in `docs/decisions/ARCHITECTURE_DECISIONS.md`

## Goal

Build the Mode 2 retrieval stack and measure it honestly against the baselines from CP3.

Question to answer: **inside a release range, which retrieval configuration ranks the true vulnerable function highest, and is any of it better than B-ID (search commit messages for the advisory ID)?**

"Retrieval does not beat B-ID" is an acceptable, reportable result (risk R9). Do not tune until it wins.

No LLM in CP4 (no HyDE, no selection, no agent). Models used are free open embedding and reranker models only, and only in Colab; tests use fakes.

## Task 0 - carry-overs from the CP3 review (each its own commit)

0a. **Materialise D4 evidence.** The bulky D4 evidence from CP3 was gitignored and lived on an earlier session's machine, so it does not exist now. Add (or reuse if it already exists) `python -m vulntrace dataset materialize --set d4`: reads `docs/results/datasets/D4_cases.json` and the pinned vulndb commit, and rebuilds each case's release-range evidence (candidate functions with bodies, commits) into the gitignored `data/` directory. It must **not** re-select cases: the 120 IDs are fixed. Resumable (skip finished cases), sequential, small delay between fetches. Report how long it took and how many cases ended in which status; any case whose status differs from `D4_cases.json` must be listed, not hidden.

0b. **Cluster-aware statistics.** CP3 finding 1: nine rclone advisories share one range. Add a `cluster_key` (module + vulnerable_at + fixed version) to D4 cases and make the bootstrap resample **clusters**, not cases. Regenerate `docs/results/CP3_DATASETS_AND_BASELINES.md` with cluster bootstrap intervals for E0 and B-ID, and add rows for B-ID without `TRUNCATED` cases (finding 3). Report how much the intervals widen.

0c. **Undated cases.** CP3 finding 2: 14 D4 cases have no `created` date and were counted as pre-cutoff. Give them their own `undated` bucket in every date split. Regenerate the CP3 results doc.

## Deliverables

1. **Chunking** - suggested `src/vulntrace/retrieval/chunking.py`
   - One chunk per candidate function. Corpus = the candidates of one release range (not the whole repository).
   - Chunk fields: stable `chunk_id`, `range_key`, package, symbol, signature, doc comment, body (vulnerable-side body; fixed-side body only for functions that exist only in the fixed version, flagged `side`), and the subjects of commits in the range that touched the file (file-level, as in CP3).
   - Cap chunk text length (record the cap; count and report truncated chunks).
   - **Leakage controls (required).** Build chunk text in three variants: `code_only`, `code+commits`, `code+commits_idmasked` (advisory IDs such as CVE, GHSA and GO ids replaced by a placeholder). The query is the advisory summary and details only; it never contains the fix commit, symbols, or `derived_symbols`. Add a test that proves the query builder cannot see those fields.
   - Share work across cases with an identical `range_key` (embed once, filter by `case_id` or `range_key` at query time).

2. **`VectorStore` interface and two backends** (interface section 4)
   - In-memory brute-force cosine (tests, default).
   - PostgreSQL + pgvector: `docker-compose.yml` (image `pgvector/pgvector:pg16` or equivalent), schema/migration in the repository, `upsert`, `search(vector, filters, k)`, `delete(filters)`.
   - **One shared test suite runs against both backends** (parametrised); the pgvector run skips with a clear message when no database is reachable.
   - Add a CI job that runs the pgvector tests with a GitHub Actions service container. Report whether the image could be pulled from the Claude Code session (open question Q10) and whether CI ran it.
   - Allowed new dependencies: `numpy`, `psycopg` (binary), `pgvector` (Python client). Real embedding models go in an optional extra (for example `.[ml]` with `sentence-transformers`); the base install and CI never install or download models.

3. **Lexical retrieval** - suggested `retrieval/bm25.py`
   - BM25 implemented in the repository (no new dependency), tested on hand-computed examples.
   - Code-aware tokenisation: split `camelCase`, `snake_case`, dots and slashes; lower-case; no stop-word list invented for code. Document the choices.

4. **Dense retrieval** - `retrieval/dense.py`
   - Uses the `Embedder` interface. Fake embedder (deterministic, hash-based) for tests. Real run: a small open embedding model through sentence-transformers.
   - Compare **at most two** embedding models (open question Q6): one general small text model and one code-oriented model. Record the exact model ids and revisions used. If a model cannot be loaded in Colab, report it and use the other; do not substitute a paid API.

5. **Fusion and reranking** - `retrieval/fusion.py`, `retrieval/rerank.py`
   - Reciprocal Rank Fusion (k=60, tested on hand-computed examples).
   - `Reranker` interface (cross-encoder). Fake reranker for tests. Real run: one small open cross-encoder, reranking the top 50 of the hybrid result (record that number). Compare at most two rerankers.

6. **Retrieval evaluation harness** - `eval/retrieval.py`, CLI `python -m vulntrace eval retrieval --config <name>`
   - Configs: `bm25`, `dense:<model>`, `hybrid`, `hybrid+rerank`, each with a chunk variant (`code_only`, `code+commits`, `code+commits_idmasked`).
   - Metrics (evaluation plan): Recall@1, @5, @10, @20, MRR, nDCG@10. Gold = core symbols (and report core ∪ derived separately).
   - **Report two denominators**, never one: (a) cases whose gold is inside the candidate set; (b) all scored cases, where gold-outside-candidates counts as a miss (CP3 finding 4: about 26% of cases).
   - Break results down by candidate-set size bucket (`<=10`, `11-100`, `>100`) and by date bucket (`pre`, `post`, `undated`). The `>100` bucket is where retrieval matters; for `<=10` any method is nearly trivial, say so.
   - Cluster bootstrap 95% intervals (task 0b), fixed seed. Also report each metric with the nine rclone cases removed.
   - Include B-ID and E0-style random/size-ordered baselines in the same tables (a random-order baseline with a fixed seed is required, so Recall@k has a floor).
   - Results written as JSON under `results/cp4/` and rendered by code to `docs/results/CP4_RETRIEVAL_RESULTS.md`.

7. **Colab notebook** - `notebooks/cp4_retrieval_colab.ipynb`
   - Steps: clone the repository, install `.[ml]`, run `dataset materialize --set d4` (resumable; cache on Google Drive), build chunks, embed, run all configs, write a small `results/cp4/` bundle and a zip of it.
   - Plain-English cell explanations (the owner is learning): each cell begins with a comment saying what it does and why.
   - The notebook must work on the free Colab GPU and degrade to CPU for the small configs. Note expected running time per step from the real run.
   - The owner will run it and hand the downloaded zip to the next session; the zip contains only result JSON (no repository code, no model files, no embeddings). Do not commit anything large.
   - If the session cannot execute Colab itself, say so; the notebook and a dry-run on fakes are still required deliverables (see tests).

8. **Tests**
   - Unit: chunk construction (all three variants, caps, masking), query builder cannot see gold/fix fields, BM25 and RRF and metric maths on hand-computed examples, cluster bootstrap determinism and cluster resampling, undated bucket, random baseline determinism.
   - A test that the D4 case-list selection logic really shuffles and really keeps forced post-cutoff cases (CP3 finding 5).
   - Contract tests: the two `VectorStore` backends and the fake embedder/reranker obey the same interface tests.
   - Integration: the whole harness runs end to end on a tiny synthetic range using only fakes and the in-memory store, with no network and no model download.
   - Nothing in the default test run touches the network or a model.

9. **Results document** - `docs/results/CP4_RETRIEVAL_RESULTS.md`, generated by code from result files: environment (including model ids and Colab GPU), the metric tables per config and variant, both denominators, size and date buckets, comparison with B-ID and random, the leakage-control comparison (does the ID in commit messages explain the gains?), and a plain statement of what retrieval can and cannot do given the ceiling.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Task 0 done: D4 evidence materialised with status differences listed; cluster bootstrap and undated bucket in CP3 results, regenerated. | Report, results doc |
| 2 | In-memory and pgvector backends pass one shared test suite; pgvector job runs in CI; Q10 answered. | Test names, CI link |
| 3 | BM25, RRF, metrics and cluster bootstrap match hand-computed tests. | Printed summaries |
| 4 | Leakage controls: three chunk variants exist; query provably excludes gold/fix fields. | Tests |
| 5 | Harness runs end to end on fakes in default tests; no test needs network or a model. | Printed summary, CI |
| 6 | At least one real run (BM25, dense, hybrid, hybrid+rerank, each with the variants) produced in Colab, committed as small result files. If it could not be run, say so plainly and mark the checkpoint accordingly. | Result files, results doc |
| 7 | Two denominators, size buckets, date buckets, rclone-removed rows and cluster intervals all reported. | Results doc |
| 8 | Random baseline and B-ID in the same tables. If retrieval does not beat B-ID, the document says so in its first paragraph. | Results doc |
| 9 | All tests pass locally and in CI. | Printed summaries, CI |
| 10 | No models, embeddings, `data/` contents, caches or vulndb text committed. | `git ls-files` |
| 11 | Report `docs/progress/reports/CP4_REPORT.md` in the wrapper format; STATUS `AWAITING_REVIEW`. | Files |

## Out of scope

Any LLM call, HyDE, closed-set selection, lifting, caller/callee expansion, the agent, the verifier, real target applications, Streamlit.

## Known risks

- Re-materialising D4 is network-heavy (git fetches); go sequentially, resume, never hammer GitHub.
- Ranges with thousands of candidates (up to about 15,000) make embedding slow on CPU; use the Colab GPU, batch, and cache.
- A good-looking score caused only by advisory IDs in commit messages is a leak, not a result; the masked variant exists to expose it.
- 26% of cases have gold outside the candidates; retrieval cannot fix that in CP4. Do not hide it inside a single headline number.

## Review notes

**Supervisor review, 22 Oct 2026 - CHANGES_REQUESTED (small fix, then a valid Colab run).**

What the supervisor found: the first Colab bundle (`cp4_results.zip`) is invalid. Inside it: 0 chunks, every case has 0 candidates, every rank is `None`. Colab's own D4 materialisation produced 0 AVAILABLE cases (62 TAG_NOT_FOUND, 31 EMPTY, 18 TRUNCATED, 9 PSEUDO_VERSION_UNRESOLVED; expected 103 AVAILABLE), and 119 of 120 cases differed from `D4_cases.json`. The notebook did not stop; it wrote empty results. The BM25 results made in the Claude Code session on real evidence are not affected.

Two bugs are visible in `src/vulntrace/dataset/materialize.py` (read by the supervisor, not yet fixed):

- `is_complete()` treats any case whose files exist as finished, **whatever its status**. A failed result (TAG_NOT_FOUND, EMPTY) is therefore skipped on every re-run and also copied by the "reused" path to every case with the same range. In the Colab log, 21 cases were `skipped` at the very start and 26 were `reused`.
- git failures are turned into `None` (for example `return p.stdout.strip() if p.returncode == 0 else None`) and end as `TAG_NOT_FOUND`, so the real git error message is never shown. A git problem in Colab is therefore reported as "tag not found".

The root cause of the first failure is **not proven**. Suspected: the git cache sat on the Google Drive mount (`VULNTRACE_CACHE` on Drive). Drive is a network file system and git is known to behave badly on it. Do not assume this; FIX-1 finds out.

Fix list (all small; do not start CP5; do not re-select D4 cases):

- **FIX-1 Diagnose.** Add a command or notebook cell that runs ONE case (for example `GO-2020-0038`) with the cache on local disk and prints every git command's stderr. Report what it shows.
- **FIX-2 Resume rule.** Skip a case only if its stored result matches the expected status and counts in `D4_cases.json`. A mismatching or failed result must be rebuilt. Same rule for the "reused" path (never copy a failed result).
- **FIX-3 No silent git errors.** Keep the status values, but record the first line of the git error in the evidence file and print the three most common error messages at the end of the summary.
- **FIX-4 Notebook.** Put `VULNTRACE_CACHE` (git and vulndb cache) on local Colab disk (`/content/cache`). Only embeddings and the final result JSON go on Drive. After the materialise cell add a gate cell that stops the notebook with a clear message if the materialised statuses differ from `D4_cases.json` in more than 3 cases.
- **FIX-5 Refuse empty runs.** `eval retrieval` and `index build` must exit with an error and write nothing when the total number of chunks is 0, or when the evidence statuses differ from the case list beyond the same threshold. Put the check in one tested function that the notebook gate also uses.
- **FIX-6 Tests.** Unit tests (no network, no Go) for FIX-2 (a failed result is rebuilt; a good one is skipped), for FIX-5 and for the gate function. Full unit and contract tests must still pass, and CI must be green.

After the fix: the owner re-runs the notebook in Colab and hands the new zip to the supervisor. The supervisor will check the zip for chunk counts and statuses before reading any metric. Do not edit or "improve" retrieval results.

Branch rule for this fix session: work directly on branch `claude/vulntrace-ai-build-9qhbjg` (check it out; it already exists; do not create another branch). If the session runs on the owner's laptop and cannot run Go or Docker, say which tests were not run and why.

