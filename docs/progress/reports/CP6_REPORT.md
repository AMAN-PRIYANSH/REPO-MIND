# CP6 report - LangGraph investigation agent (Mode 2)

State: **`AWAITING_REVIEW`**. The owner's four Colab parts are finished and committed; the results document, failure analysis and headline are done. **Headline: the agent does not beat retrieval (A0) on any-hit@1 for either model, and it costs about five times the prompt tokens and about twice the seconds of the one-shot LLM (A1). It beats only A1 for `qwen2.5-coder-7b`, a baseline that answered 35% of cases. A negative result.**

Sessions: (1) Claude Code cloud session on `claude/gracious-carson-ch1i9r`, 26 Oct 2026: code, tests, notebook, dry run. (2) this results session on `claude/vulntrace-ai-build-1wfa8e` (fast-forwarded onto the first at `0f4310c`), 26 Oct 2026: results, failure analysis, report. Sections 1-3, 7 and 8 keep the first session's text where it still holds and add this session's.

## 1. Environment

| Item | Printed value |
|---|---|
| OS | `Linux vm 6.18.44-fc-v153 #1 SMP PREEMPT_DYNAMIC x86_64`, Ubuntu 24.04.5 LTS |
| Python | `Python 3.13.17` (project-local `.venv`, `pip install -e ".[dev,agent]"`; nothing installed system-wide) |
| Go | `go version go1.24.7 linux/amd64` (system). Also `go1.26.10`, fetched from the Go module proxy into the scratch area (`GOTOOLCHAIN=go1.26.10 go version` with a scratch `GOMODCACHE`; checksum-verified by sum.golang.org). It is used only for the neighbour tables, as in CP5b. |
| git | `git version 2.43.0` |
| Docker | `Docker version 29.9.2, build a82e528` (not used) |
| LangGraph | `langgraph==1.2.15` (released 12 Oct 2026; pinned in the new `[agent]` extra), langchain-core 1.7.0 |
| Network | pypi.org 200; proxy.golang.org 200; `git ls-remote https://github.com/golang/vulndb` works. huggingface.co, ollama.com and go.dev/dl: refused by the session's egress proxy (403 `connect_rejected`). |


Results session (printed this session, 26 Oct 2026): `Linux vm 6.18.44-fc-v153 #1 SMP PREEMPT_DYNAMIC @0 x86_64`, Ubuntu 24.04.5 LTS; `Python 3.13.17` (project-local `.venv`, `pip install -e ".[dev,agent]"`, nothing system-wide); `go version go1.24.7 linux/amd64`; `git version 2.43.0`; `Docker version 29.9.2, build a82e528` (not used). Network: pypi.org (pip install) and github.com / proxy.golang.org (`helper fetch`, `dataset materialize`) worked; huggingface.co and ollama.com were not needed and not tried (no model ran in this session).
The Colab run itself (from the committed `colab_run.json` and result files): Tesla T4, Python 3.13.16, go1.24.7, torch 2.11.0+cu130, LangGraph 1.2.15, repository commit `6f08c26`, `repo_dirty: false`; `llama3.1:8b` digest `46e0c10c...a666e` and `qwen2.5-coder:7b-instruct` digest `dae161e2...6f4364`, both Q4_K_M; context 32,768; 4 sessions (PART 1-4).
## 2. Files changed (vs `main`)

| File | Purpose |
|---|---|
| `src/vulntrace/agent/__init__.py` | package |
| `src/vulntrace/agent/graph.py` | LangGraph state graph: budget, act, tool, repair, submit nodes; state; trace |
| `src/vulntrace/agent/protocol.py` | JSON action protocol: parse/validate actions, answer content check |
| `src/vulntrace/agent/tools.py` | the six tools over the closed pool, output caps, escaping, observations |
| `src/vulntrace/agent/world.py` | `CaseWorld` (one case's candidates, commits, diffs, neighbour table, search) |
| `src/vulntrace/agent/budget.py` | budgets and stop/budget reasons |
| `src/vulntrace/agent/prompts.py` | template loading and message builders (advisory read only through `QueryInput`) |
| `src/vulntrace/agent/prompts/*.txt` | 7 frozen templates: system, graph tools, task, observation, last step, repeat, repair |
| `src/vulntrace/agent/prompts/FROZEN.json` | sha256 of every template (freeze) |
| `src/vulntrace/agent/fakes.py` | fake closed-pool world and a broken search (tests) |
| `src/vulntrace/agent/prepare.py` | `agent prepare`: commit diffs (git) and neighbour tables (helper); summary; comparison |
| `src/vulntrace/eval/agent_eval.py` | arms A2/A3 runner, per-case rows, counts, resumable traces |
| `src/vulntrace/eval/agent_cli.py` | `eval symbols --strategy agent`, `agent prepare`, `agent show-trace` |
| `src/vulntrace/eval/agent_report.py` | renderer of `docs/results/CP6_AGENT_RESULTS.md` (A0-A3, both denominators, paired intervals, cost, failure analysis) |
| `src/vulntrace/__main__.py` | new options and the `agent` command; `results render --doc cp6` |
| `src/vulntrace/eval/results_doc.py` | cp6 dispatch |
| `src/vulntrace/eval/retrieval.py` | `Harness.rank_query`; the dense-ranking cache key now includes the query (see deviation 12) |
| `src/vulntrace/models/fakes.py` | `SequenceLLMClient` (scripted replies, latency/token/error injection), `agent_dry_run_responder` |
| `src/vulntrace/llm/factory.py` | the fake answers agent prompts with the agent dry-run responder |
| `src/vulntrace/schemas.py` | three new schemas; local `$ref` registry (no network resolution) |
| `schemas/agent_action.schema.json`, `agent_trace.schema.json`, `agent_result_row.schema.json` | contracts |
| `pyproject.toml` | `[agent]` extra; agent prompts as package data |
| `.github/workflows/ci.yml` | CI installs `.[dev,db,agent]` |
| `notebooks/cp6_agent_colab.ipynb` | Colab run |
| `docs/results/cp6/agent_evidence.json` | committed summary of the agent evidence built here (statuses, counts, hashes; no code) |
| `docs/design/INTERFACES_AND_CONTRACTS.md`, `docs/design/DATA_MODEL.md` | tool contract, JSON protocol, trace fields |
| `README.md` | CP6 commands |
| `docs/progress/STATUS.md` | state, branch, task list, handoff |
| `tests/unit/test_agent_graph.py` | 28 scenario tests (every failure path) |
| `tests/unit/test_agent_prompts_frozen.py` | freeze enforcement |
| `tests/unit/test_agent_report_metrics.py` | renderer maths on hand-computed examples |
| `tests/unit/test_cp6_notebook.py` | notebook rules |
| `tests/unit/test_agent_extra_in_ci.py` | in CI a missing langgraph is a failure, not a skip |
| `tests/contract/test_agent_contract.py` | schema = code = prompt = interfaces doc; trace and row schemas |
| `tests/integration/test_agent_pipeline.py` | end to end on the tiny synthetic D4, CLI, renderer, commit diffs on a real local git repo, neighbour tables from a recorded helper response, shared-range reuse |
| `docs/progress/reports/CP6_REPORT.md` | this report |

Added or changed in the results session:

| File | Purpose |
|---|---|
| `docs/results/cp6/agent__A2__llama3.1-8b.json`, `agent__A2__qwen2.5-coder-7b.json`, `agent__A3__llama3.1-8b.json`, `agent__A3__qwen2.5-coder-7b.json` | the four arm result files from the Colab run (150-153 KB each, 120 rows each, 118 run + 2 NOT_RUN) |
| `docs/results/cp6/colab_run.json`, `agent_evidence_colab.json`, `D4_materialize_colab.json` | Colab run record (models, digests, timings, evidence vs committed summary), Colab's evidence summary, Colab's D4 materialisation |
| `docs/results/cp6/failure_analysis.json` | 18 classified wrong cases and 2 worked traces (function names, no code) |
| `docs/results/CP6_AGENT_RESULTS.md` | the generated results document |
| `src/vulntrace/eval/agent_report.py` | headline rewritten (see deviation 16); new tables: list length and agreement with A0, where A3 differs from A2 |
| `tests/unit/test_agent_report_metrics.py` | 5 new tests for the headline wording and the two tables |
| `docs/progress/STATUS.md`, `docs/progress/reports/CP6_REPORT.md` | state, branch, report |

Not committed: the 472 traces (`.json.gz`, in the owner's zip), `data/` (rebuilt here only to read function names).
## 3. Deliverables

| # | Deliverable | State |
|---|---|---|
| 1 | Agent graph, tools, closed pool, truncation, `submit_answer` rules, budgets, temperature 0 / seed 7, full trace | **Done** |
| 1b | Precomputed `callers`/`callees` tables (CP5b helper modes, gitignored evidence directory) | **Done in this session:** 118 of 118 cases with a usable range (2 D4 cases are EMPTY). Per-candidate coverage is partial; see section 8. |
| 2 | Prompts `agent_system_v1`, `agent_repair_v1` (+5 more templates) frozen before any real run | **Done** (`42da9a4`) |
| 3 | Fake LLM and fake tools; scripted sequences for every listed path | **Done** |
| 4 | `eval symbols --strategy agent --set d4`; arms, metrics, intervals, cost, contamination, results JSON, renderer | **Done.** Real results from the owner's run are committed and rendered; failure analysis (18 cases, 2 worked traces) done from the real traces. |
| 5 | Colab notebook | **Done and executed by the owner** in four parts (see `colab_run.json`). The real-generate check and the Ollama install worked in Colab (every call was answered; 0 server errors in all four files). |
| 6 | Tests; CI green; no network | **Done** |

## 4. Test evidence (commands run in this session)

- `python -m pytest tests/unit tests/contract tests/integration -q` → `734 passed, 12 skipped in 171.23s (0:02:51)`. Skips: 9 pgvector (no psycopg in the venv; CI runs them), 2 opt-in network smoke tests, 1 CI-only check.
- `python -m pytest tests/unit/test_agent_graph.py -q` → `28 passed in 0.65s`
- `python -m pytest tests/contract/test_agent_contract.py -q` → `21 passed in 0.77s`
- `(cd helper && GOTOOLCHAIN=local CGO_ENABLED=0 GOPROXY=off go test ./...)` → `ok  	vulntrace/helper	4.716s`
- CI (GitHub Actions, workflow `CI`, branch `claude/gracious-carson-ch1i9r`): green on every commit except `675405b`. **That commit was pushed with two failing unit tests:** I had added `answer_ids_seen` to the trace's `final` block, and two tests compared that block exactly. I missed it because my local check piped pytest into `tail` without `pipefail`, so the commit went ahead. Fixed in the next commit `761f83c` (CI green), and every later commit was checked with `set -o pipefail`. CI on the latest commit `1d6579c`: success (run 89).
- `dataset materialize --set d4` → `D4 materialize: 120 cases in 1320.8s; actions {'built': 94, 'reused': 26}; status counts {'AVAILABLE': 104, 'TRUNCATED': 14, 'EMPTY': 2} (...); 0 case(s) differ`
- `agent prepare --set d4 --diffs` → `commit diffs: {'NO_RANGE': 2, 'READY': 118}` (9,642 commits, all diffed, 0 git errors, 481 stored with the 30,000-character cut), 1 min 35 s.
- `agent prepare --set d4 --graph` (go1.26.10, three invocations, see section 8) → `neighbour tables: {'NO_RANGE': 2, 'READY': 118}`; 4,711 s summed per-case build time.
- Dry run with the fake LLM and fake embedder on the real D4 evidence (`eval symbols --strategy agent --set d4 --arm A2 --arm A3 --dry-run`), 38 s:
  - `A2 [fake]: 118 run; submitted 106, abstained 7, invalid answer 0, invalid action 0, loop 5, budget 0 {...}, errors 0; 464 calls, 880495 in / 8133 out tokens`
  - `A3 [fake]: 118 run; submitted 106, abstained 6, invalid answer 0, invalid action 0, loop 6, budget 0 {...}, errors 0; 568 calls, 1221338 in / 9455 out tokens`
  - Also exercised on the real evidence: repair turns (4 in A2, 6 in A3), answer rejections (5 / 8), repeated calls (10 / 12), outputs cut to the budget (55 / 57), graph tools available in A3 for 118 of 118. The fake's numbers measure nothing about any model. The rendered dry-run document carries the FAKE warning and is not committed.

Results session:

- `python -m pytest tests/unit tests/contract tests/integration -q` → `740 passed, 12 skipped in 260.06s (0:04:20)` (the first session had 734 passed; 6 new renderer tests).
- `python -m pytest tests/unit/test_agent_report_metrics.py tests/integration/test_agent_pipeline.py -q` → `19 passed in 1.42s` (before the last table was added); `tests/unit/test_agent_report_metrics.py` alone → `8 passed in 0.25s`.
- `python -m vulntrace results render --doc cp6 --input docs/results/cp6 --out docs/results/CP6_AGENT_RESULTS.md` → `wrote docs/results/CP6_AGENT_RESULTS.md`.
- `unzip -tq cp6_results_3.zip` → `No errors detected in compressed data`. Checked by script: 4 arm files, `dry_run: false`, `counts.run` = 118 in each, 118 traces in each of the 4 trace folders, each JSON under 512 KiB (largest 153 KB), `repo_commit` 6f08c26 and `repo_dirty` false in all four, prompt sha256 `98856e73...` in all four, `evidence_vs_committed`: commit diffs 118 same / 0 different, graph 118 same / 0 different. `src/` and `notebooks/` have no diff between `6f08c26` (the commit the Colab ran) and the first commit of this session.
- `dataset materialize --set d4` (this session, for function names) → `D4 materialize: 120 cases in 1983.9s; actions {'built': 94, 'reused': 26}; status counts {'AVAILABLE': 104, 'TRUNCATED': 14, 'EMPTY': 2} (case list: {'AVAILABLE': 104, 'EMPTY': 2, 'TRUNCATED': 14}); 0 case(s) differ`.
- CI (GitHub Actions, via the GitHub MCP): run 93 (`564e494`) success, run 94 (`1033a34`) success; run 95 (`94ab486`) was still in progress when last checked; see section 10.
## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Agent graph and all tools implemented; closed pool enforced; budgets recorded | **Met** | `test_agent_graph.py` (closed pool: `test_tool_error_is_an_observation...`, `test_show_commit_closed_pool_and_diff`, `test_out_of_pool_id...`); `test_world_is_the_cases_closed_pool_without_gold`; budgets in every trace and result file (`test_cli_agent_dry_run_writes_both_arms_and_traces`) |
| 2 | Prompts frozen before any real run; commit order shows it | **Met** | `42da9a4` (freeze, `FROZEN.json` + test) precedes the notebook commit `c3bee1e`; no real run has happened at all |
| 3 | Fake-driven tests cover every failure path of deliverable 3 | **Met** | success, invalid JSON then repair, out-of-pool ID, steps / tokens / time budget, abstention, `LOOP_DETECTED`, tool error: one test each in `test_agent_graph.py` (28 passed) |
| 4 | Notebook ready with gate, resume and real-generate check | **Met (and run by the owner)** | `test_cp6_notebook.py` (7 passed); the owner's four Colab parts completed (`colab_run.json`). The Ollama install and real-generate check, only tested with fakes before, worked in Colab: 0 server errors in all four files |
| 5 | A0-A3 table with paired intervals, both denominators, cost table, failure counts | **Met** | `docs/results/CP6_AGENT_RESULTS.md` (per model, per contamination group, denominators (a) and (b), paired differences, cost table in the headline, failure counts by reason) |
| 6 | ≥10 failure cases classified from traces, 2 worked traces | **Met, with a caveat** | 18 cases and 2 worked traces in `failure_analysis.json` / the document. The cases were chosen by me to cover stop reasons, models and arms; they are not a random sample, so the cause counts (wrong tool use 4, ignored evidence 6, label convention 3, format failure 2, gave up 2, gold not reachable 1) are not rates. Two of the three label-convention calls are judgements not verified against the code. |
| 7 | Honest headline | **Met** | The first line of the document: the agent does not beat retrieval (A0); worse than A0 for qwen A2; it beats A1 only for qwen A3 and the document says A1 answered 35% of cases there. See deviation 16 for why the renderer's wording was changed after the results were seen. |
| 8 | Tests pass locally and in CI; no `data/`, caches, models or traces committed | **Met** | section 4; `git ls-files` shows nothing under `data/`, no `.gz`, no caches or traces; result rows have a closed schema (`agent_result_row.schema.json`) |
| 9 | Report; STATUS `AWAITING_REVIEW` | **Met** | this file; STATUS |

## 6. Results

Everything below is copied from `docs/results/CP6_AGENT_RESULTS.md` (generated by code from the committed files); that document has all groups, denominators and the failure analysis. Headline group of each model on denominator (b), all cases: `llama3.1-8b` post-cutoff (created after 2023-12-31), n = 98 (72 clusters); `qwen2.5-coder-7b` all dated cases (cutoff undocumented), n = 106 (80 clusters).

**any-hit@1 and any-hit@3 (95% cluster-bootstrap intervals)**

| Model | Arm | any-hit@1 | any-hit@3 | answered |
|---|---|---|---|---|
| llama3.1-8b | A0 retrieval | 0.469 [0.356, 0.585] | 0.673 [0.560, 0.778] | 0.980 |
| llama3.1-8b | A1 S1 (CP5) | 0.469 [0.359, 0.586] | 0.541 [0.419, 0.670] | 0.969 |
| llama3.1-8b | A2 agent | 0.469 [0.371, 0.571] | 0.531 [0.430, 0.630] | 0.918 |
| llama3.1-8b | A3 agent + graph | 0.469 [0.374, 0.574] | 0.561 [0.461, 0.667] | 0.949 |
| qwen2.5-coder-7b | A0 retrieval | 0.481 [0.377, 0.591] | 0.670 [0.561, 0.768] | 0.981 |
| qwen2.5-coder-7b | A1 S1 (CP5) | 0.245 [0.163, 0.337] | 0.245 [0.163, 0.337] | 0.368 |
| qwen2.5-coder-7b | A2 agent | 0.274 [0.192, 0.357] | 0.292 [0.208, 0.381] | 0.623 |
| qwen2.5-coder-7b | A3 agent + graph | 0.396 [0.309, 0.487] | 0.396 [0.309, 0.487] | 0.755 |

**Paired differences in any-hit@1** (same groups)

| Model | A2 − A0 | A2 − A1 | A3 − A0 | A3 − A1 | A3 − A2 |
|---|---|---|---|---|---|
| llama3.1-8b | 0.000 [-0.082, 0.082] | 0.000 [-0.076, 0.078] | 0.000 [-0.084, 0.092] | 0.000 [-0.084, 0.088] | 0.000 [-0.071, 0.079] |
| qwen2.5-coder-7b | **-0.208 [-0.304, -0.112]** | 0.028 [-0.081, 0.130] | -0.085 [-0.163, 0.000] | **+0.151 [0.056, 0.248]** | **+0.123 [0.037, 0.213]** |

Bold = interval excludes 0. On any-hit@3 the agent is significantly worse than A0 for llama (A2 -0.143 [-0.235, -0.051], A3 -0.112 [-0.185, -0.038]) and for qwen (A2 -0.377, A3 -0.274, both excluding 0); that comparison is not like for like because agent answers list 1.1-1.4 IDs where A0 lists 3 (table below). On denominator (a) (gold among the candidates) for qwen, A3 − A0 is -0.103 [-0.198, -0.011], which does exclude 0 (on (b) the upper bound is exactly 0.000).

**Cost per case** (llama / qwen; A1 is one call)

| Arm | steps | prompt tokens (mean) | model+tool seconds (mean) |
|---|---|---|---|
| A1 | 1 | 3,574 / 3,654 | 4.9 / 4.1 |
| A2 | 6.4 / 6.1 | 18,603 / 18,138 | 10.2 / 9.7 |
| A3 | 7.5 / 6.8 | 23,406 / 20,196 | 11.2 / 9.9 |

**Failure and stop rates (118 cases run per file)**

| Model | Arm | submitted | abstained | INVALID_ACTION | LOOP_DETECTED | budget stop | cases with an invalid action |
|---|---|---|---|---|---|---|---|
| llama3.1-8b | A2 | 108 (92%) | 0 | 2 (2%) | 8 (7%) | 0 | 5 (4%) |
| llama3.1-8b | A3 | 115 (97%) | 0 | 2 (2%) | 1 (1%) | 0 | 14 (12%) |
| qwen2.5-coder-7b | A2 | 75 (64%) | 2 (2%) | 0 | 40 (34%) | 1 (steps) | 0 |
| qwen2.5-coder-7b | A3 | 92 (78%) | 5 (4%) | 0 | 20 (17%) | 1 (steps) | 1 (1%) |

INVALID_ANSWER 0, server ERROR 0 in all four files. Every problem code behind llama's invalid actions is `ARG_TYPE` (7 in A2, 16 in A3); in the A2 cases I read, the cause was `"k"` given as a string.

**List length and agreement with A0** (all 118 cases run)

| Model | Arm | IDs per answer | top-1 same as A0 | top-1 changed | changed: A0 wrong, agent right | changed: A0 right, agent wrong | no answer although A0's top-1 was right |
|---|---|---|---|---|---|---|---|
| llama3.1-8b | A2 | 1.42 | 66 | 42 | 10 | 8 | 4 |
| llama3.1-8b | A3 | 1.40 | 72 | 43 | 11 | 8 | 2 |
| qwen2.5-coder-7b | A2 | 1.28 | 42 | 33 | 3 | 11 | 19 |
| qwen2.5-coder-7b | A3 | 1.14 | 58 | 34 | 8 | 8 | 10 |

**Where A3 differs from A2 (qwen)**: both answered 63 cases (any-hit@1 25 vs 35); A3 answered 29 cases A2 did not (14 hits), A2 answered 12 that A3 did not (7 hits). For llama: both answered 105 cases (55 vs 55).

**How to read this.** For llama the agent changes A0's top-1 in 42 of 118 cases (A2): 10 gains, 8 losses, and 4 more cases lost to no answer. Net any-hit@1 in the headline group is exactly A0's (0.469), with a paired interval of about ±0.08: no detectable difference, at about 5 times the prompt tokens and about twice the seconds of A1; A0 needs no model call. For qwen, A2's loss to A0 comes mostly from stops with no answer: 40 `LOOP_DETECTED`, in 18 of which A0's top-1 had been right. A3 > A1 is a win over a baseline that answered 35% of cases. A3 > A2 for qwen cannot be attributed to graph information: A3 also answers 29 more cases, and the two arms' interactions differ in length and order. Nothing here supports using the agent over retrieval in CP7.

## 7. Design deviations

1. **Seven prompt templates instead of two.** Besides `agent_system_v1` and `agent_repair_v1`: `agent_task_v1` (advisory and first search), `agent_observation_v1`, `agent_last_step_v1`, `agent_repeat_v1`, `agent_graph_tools_v1` (A3's extra tool lines). This way every text the model reads is a frozen file; code only fills placeholders. Repair turns and rejected answers share `agent_repair_v1`.
2. **Time budget = recorded model time + measured tool time**, not raw wall time. Recorded latency is stored in the response cache, so a run resumed after a Colab disconnect takes exactly the same budget decisions. Raw wall time is recorded separately per case.
3. **An extra fifth budget, `max_prompt_tokens_per_call` (24,000).** It sits below the 32k context the notebook gives Ollama, so a prompt is never silently truncated by the server (stop reason `BUDGET_EXCEEDED/CONTEXT`).
4. **More stop reasons than DATA_MODEL listed:** `ABSTAINED`, `INVALID_ACTION` (a second invalid reply in a row; the spec gives one repair turn but does not say what follows), `LOOP_DETECTED`, plus `budget_reason`. Documented in DATA_MODEL and the trace schema.
5. **An automatic first search.** The task message shows the fixed retriever's top 10 for the advisory text (IDs, names, signatures, first commit subject; no code). This is the A0 ranking. It is not a step. So the agent starts from what A0 knows; whether it does better than that is exactly the question.
6. **What counts as a step.** Repair turns and the one answer retry are not steps; they cost tokens and time. A repeated identical call counts as a step, is answered with a note instead of being run, and the second repeat in a run (of any earlier call) is `LOOP_DETECTED`.
7. **The pool is the case's full candidate set.** Answer IDs need not have been shown before (recorded as `answer_ids_seen`); cited evidence must have appeared in a tool output.
8. **JSON mode.** Ollama's JSON-constrained output (`response_format: json_object`) is on, as in CP5. It is a protocol choice, not a repair; the parser still accepts nothing but the exact two-key object.
9. **How the neighbour tables reach Colab.** The spec has them built "in a session with Go … so the Colab run needs no Go". `data/` is gitignored and this container is ephemeral, so the session handed the tables to the owner as `cp6_graph_tables.zip` (1.3 MB, 118 files, sha256 `613734f5…ebe1e`; function names and call sites, no code). The notebook unpacks it from Drive and checks every file against the committed hashes. Without the zip, the notebook rebuilds the tables with Go 1.26.10. Go is installed in that notebook anyway, because `materialize` needs the helper's `funcs` mode.
10. **MRR is MRR@3** over each arm's list of at most 3 IDs, for all arms (A0's full-ranking MRR is in CP4). Precision@1 is over answered cases, with n.
11. **A1@1** uses S1's first listed ID. S1 was not asked to rank (stated in the document).
12. **Retriever code touched (cache key only).** `Harness._dense_ranking` cached by case ID, so a second query on the same case would have returned the advisory's ranking. The key now includes the query, and `rank_query` reuses `rank_case`. No ranking changes: `test_rank_query_equals_rank_case_for_the_advisory_and_does_not_pollute_its_cache`, and the full CP4 suite passes unchanged.
13. **Committed rows carry the gold candidate IDs** (e.g. `r17`), so the renderer can score A1 from the CP5 files. These are IDs, not code or names.
14. **`show_commit` diffs:** non-test Go files first, then `_test.go`, `vendor/` left out, merges against the first parent; `git show` with `--no-ext-diff --no-textconv`.
15. **No pull request**, as the session instructions say (the supervisor merges).
16. **The renderer's headline was rewritten after the results were seen.** The first version said "The agent beats a baseline in at least one comparison below", which was true only because `qwen2.5-coder-7b` A3 beat A1, a baseline that answered 35% of cases. I changed the lead so that it names the comparison against A0 first, says when a win is only over a mostly abstaining A1, and warns that any-hit@3 is not like for like. This changes wording only: no number, prompt or budget changed. Commit `1033a34`, with 4 tests.
17. **Two renderer tables added after seeing the results** (list length and agreement with A0; where A3 differs from A2). They are descriptive, computed from the committed files, and were added because the equal any-hit@1 of the four llama arms and the qwen A3 > A2 difference needed explaining. They are post-hoc analysis, not pre-registered.
18. **Failure-analysis cases are hand-picked**, not sampled (stated in the document). Cause labels are my judgement; the three "label convention" labels were not checked against the code.
19. **Not done: a second seed, a post-hoc v2, any change to prompts or budgets.** The spec forbids tuning on D4; no real run was made in this session.
## 8. Blockers and limitations

- **(Resolved by the owner's run; kept for the record.) No real run in the first session.** There is no GPU, model or registry access here. The arms' numbers, the cost table, the failure analysis and the headline all wait for the owner's Colab run. The running-time estimate (1-2 h per arm and model) is extrapolated from CP5's ~5 s per call and is **not measured**. The notebook is therefore split into four parts (one arm x one model per Colab session); resume is by trace files and the response cache on Drive, and the D4 evidence is saved to Drive after the first session so later sessions skip the ~25-minute rebuild.
- **Neighbour-table coverage is partial.** About a third of the candidate nodes (4,657 of 14,427) are in packages the helper skipped at load, mostly packages with their own load errors, so `callers`/`callees` answer "no call-graph information" for them. The gold candidate has neighbours in 95 of 101 cases. As CP5b said, A3 is an ablation, and the tools only point to other candidates; they cannot add a function outside the pool.
- **A transient helper failure.** In the first 2-job build, the one rclone range (116k nodes, 1.06M edges; shared by 5 cases) came back `BAD_RESPONSE` for 41 of 44 nodes. Run alone it did not reproduce (44/44 matching results), and a 1-job rebuild gave 40 FOUND, 1 NONE, 3 TARGET_NOT_FOUND. The likely cause is memory pressure with two large helpers running at once; this is not proven. The Colab fallback rebuild (2 jobs, 2 CPUs, ~12 GB) could hit it too; using the zip avoids that.
- **Reproducibility of the tables.** They were built with go1.26.10 from the module proxy and `go mod tidy -e` against the proxy of 26 Oct 2026. A rebuild elsewhere can differ where a module's requirements are incomplete. The notebook reports same/different/missing per case against the committed hashes; it does not stop on a difference.
- **Commit-diff hashes in Colab** may differ from this session if Colab's git prints diffs differently. That is only reported, not gated; the diffs are rebuilt there.
- **Ollama install check:** only tested with fakes (as in CP5b); the CP6 run will exercise it for real.
- **Session mistakes:** the failing-test push (section 4). A `pkill -f` pattern that matched my own shell, killing that command (no data lost; the build was restarted). A watch loop that could never end for the same `pgrep -f` reason (stopped). None of these changed any committed file.
- **One run, one seed, temperature 0.** Run-to-run variance is not measured; the equal 0.469 for llama is a net of gains and losses against A0, not an identical list.
- **The loop rule is a large part of qwen's result.** `LOOP_DETECTED` ends a run with no answer, even when A0's top-1 was right and shown (A2: 40 stops, 18 with A0 right). That is the frozen rule from the first session (the second repeated call in a run). Whether a looser rule would change the verdict is untested; it would need a labelled post-hoc run, which I did not do.
- **Pools of one are not shortcut.** In 11 cases the pool has a single candidate; the agent still spends steps and can fail (llama A2: 3 loop stops and 2 invalid actions in those 11; qwen A2: 4 loop stops and 1 step-budget stop).
- **Contamination groups are small and different per model** (llama pre-cutoff n = 8; D4 has 87 of 120 cases after 2026-06-30). The pre-cutoff rows show A2 worse than A0 for llama on n = 8; do not read more into them.
- **A1@1 is indicative** (S1 was not asked to rank).
- **Function names in the failure analysis come from my rebuild of the D4 evidence** (statuses identical to the committed case list, 0 differences). The traces themselves hold IDs, not names.
- The earlier `model_problems.json` mentioned in the STATUS handoff is not in the zip; nothing in `colab_run.json` or the result files reports a model problem (0 server errors, 0 length stops).
## 9. Suggestions for the next checkpoint (not implemented)

- **Do not use the agent in CP7's verdict path.** It did not beat A0 on any-hit@1 and it costs about 5x the tokens of S1. If CP7 wants an ordering of candidates, use A0's ranked list, with reachability checks for several candidates (the CP5 E1 finding stands).
- A cheap structural filter is worth testing on a fresh case set, not on D4: candidates that exist only in the fixed release (`side` NEW) cannot be the vulnerable function of the vulnerable release, yet they are the top-1 of A0 in 18 of 101 and of the agents in 16-19 cases per arm, while only 9 of 394 gold IDs are NEW-only (counted ad hoc from the rebuilt evidence in this session, not by committed code; verify before relying on it).
- If a second agent version is tried, label it post-hoc and address three observed failure modes: the strict string-typed `k` rejection (llama), the loop stop that discards the answer, and the validator accepting a cited commit that contradicts the answer (GO-2026-5427). Do not tune on D4.
- Run two seeds on a subset to measure variance before reading small differences.
- If PACKAGE_NOT_LOADED matters for A3, investigate the helper's load errors for the largest D4 modules.
## 10. Git

Branch `claude/vulntrace-ai-build-1wfa8e` (results session; fast-forwarded onto `claude/gracious-carson-ch1i9r` at `0f4310c` first, then continued). All pushes of this session succeeded (`git push`, no errors).

```
ddd57cb CP6: report with the real results, STATUS AWAITING_REVIEW
94ab486 CP6: failure analysis (18 wrong cases read from the Colab traces, 2 worked traces) and two renderer tables (A3 vs A2 split)
1033a34 CP6: commit the owner's Colab results (4 arm files, colab_run, evidence summary, D4 materialize log) and render the results document
564e494 CP6: results session starts - STATUS records branch claude/vulntrace-ai-build-1wfa8e (continues claude/gracious-carson-ch1i9r)
(plus the commit that adds this git section)
```

CI: run 93 (`564e494`) and run 94 (`1033a34`) succeeded. **Not confirmed:** run 95 (`94ab486`, failure analysis and renderer tables) was still `in_progress` when last checked, and runs for `ddd57cb` and the final commit had not appeared. The same tests passed locally (`740 passed, 12 skipped`, section 4), but a green CI for the last commits is unverified; the supervisor should check it.
