# CP6 report - LangGraph investigation agent (Mode 2)

State: **`AWAITING_COLAB`**. The code, the frozen prompts, the tests, the renderer and the notebook are done. The dry run on the real D4 evidence is done too. The measurement itself (criteria 5-7) needs the owner's Colab run: this session has no GPU and cannot reach Hugging Face or the Ollama registry. No real model has seen the agent prompts, and no CP6 result number exists yet.

Session: Claude Code cloud session, branch `claude/gracious-carson-ch1i9r`, 26 Oct 2026.

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

## 3. Deliverables

| # | Deliverable | State |
|---|---|---|
| 1 | Agent graph, tools, closed pool, truncation, `submit_answer` rules, budgets, temperature 0 / seed 7, full trace | **Done** |
| 1b | Precomputed `callers`/`callees` tables (CP5b helper modes, gitignored evidence directory) | **Done in this session:** 118 of 118 cases with a usable range (2 D4 cases are EMPTY). Per-candidate coverage is partial; see section 8. |
| 2 | Prompts `agent_system_v1`, `agent_repair_v1` (+5 more templates) frozen before any real run | **Done** (`42da9a4`) |
| 3 | Fake LLM and fake tools; scripted sequences for every listed path | **Done** |
| 4 | `eval symbols --strategy agent --set d4`; arms, metrics, intervals, cost, contamination, results JSON, renderer | **Code done.** Real results: **not done** (owner's Colab run). Failure analysis: **not done** (needs real traces). |
| 5 | Colab notebook | **Done.** Not executed in Colab by this session. |
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

## 5. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Agent graph and all tools implemented; closed pool enforced; budgets recorded | **Met** | `test_agent_graph.py` (closed pool: `test_tool_error_is_an_observation...`, `test_show_commit_closed_pool_and_diff`, `test_out_of_pool_id...`); `test_world_is_the_cases_closed_pool_without_gold`; budgets in every trace and result file (`test_cli_agent_dry_run_writes_both_arms_and_traces`) |
| 2 | Prompts frozen before any real run; commit order shows it | **Met** | `42da9a4` (freeze, `FROZEN.json` + test) precedes the notebook commit `c3bee1e`; no real run has happened at all |
| 3 | Fake-driven tests cover every failure path of deliverable 3 | **Met** | success, invalid JSON then repair, out-of-pool ID, steps / tokens / time budget, abstention, `LOOP_DETECTED`, tool error: one test each in `test_agent_graph.py` (28 passed) |
| 4 | Notebook ready with gate, resume and real-generate check | **Met (not run in Colab)** | `test_cp6_notebook.py` (7 passed). The real-generate check is the CP5b `ollama_setup.ensure_working`, which CP5b's review noted has only been tested with fakes |
| 5 | A0-A3 table with paired intervals, both denominators, cost table, failure counts | **Not met yet** | renderer done and tested on fakes; needs the owner's run |
| 6 | ≥10 failure cases classified from traces, 2 worked traces | **Not met yet** | needs real traces; `agent show-trace` and the renderer section (`failure_analysis.json`) are ready |
| 7 | Honest headline | **Could not verify** | the renderer states "does not beat" unless a paired interval excludes 0 and puts the cost table in the headline. Shown on the dry run only. |
| 8 | Tests pass locally and in CI; no `data/`, caches, models or traces committed | **Met** | section 4; `git ls-files` shows nothing under `data/`, no `.gz`, no caches or traces; result rows have a closed schema (`agent_result_row.schema.json`) |
| 9 | Report; STATUS `AWAITING_COLAB` | **Met** | this file; STATUS |

## 6. Results

No model results yet. Committed so far: `docs/results/cp6/agent_evidence.json`, the agent evidence built in this session:

| Evidence | Cases | Detail |
|---|---|---|
| Commit diffs (`show_commit`) | 118 READY, 2 NO_RANGE (EMPTY ranges) | 9,642 commits, all with a diff, 0 errors; 481 stored cut at 30,000 characters (the tool shows at most 3,000 anyway) |
| Neighbour tables (A3) | 118 READY, 2 NO_RANGE | 14,427 candidate nodes (candidates of the vulnerable release inside the module). Per node: FOUND 7,661, NONE 576, PACKAGE_NOT_LOADED 4,657, PACKAGE_NOT_IN_PROGRAM 1,184, TARGET_NOT_FOUND 349. 33,858 caller and 110,789 callee edges; 165 nodes hit the 200-result cap |

Diagnostic (dry run plus tables): of the 101 D4 cases with a gold function among the candidates, the gold candidate has graph neighbours in 95, has none in 2, and sits in a package that failed to load in 4. The other 19 cases have no gold candidate, so every arm misses them.

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

## 8. Blockers and limitations

- **No real run.** There is no GPU, model or registry access here. The arms' numbers, the cost table, the failure analysis and the headline all wait for the owner's Colab run. The notebook's running-time estimate (1-2 h per arm and model, 4-8 h in total) is extrapolated from CP5's ~5 s per call and is **not measured**. Expect more than one Colab session; resume is by trace files and the cache on Drive.
- **Neighbour-table coverage is partial.** About a third of the candidate nodes (4,657 of 14,427) are in packages the helper skipped at load, mostly packages with their own load errors, so `callers`/`callees` answer "no call-graph information" for them. The gold candidate has neighbours in 95 of 101 cases. As CP5b said, A3 is an ablation, and the tools only point to other candidates; they cannot add a function outside the pool.
- **A transient helper failure.** In the first 2-job build, the one rclone range (116k nodes, 1.06M edges; shared by 5 cases) came back `BAD_RESPONSE` for 41 of 44 nodes. Run alone it did not reproduce (44/44 matching results), and a 1-job rebuild gave 40 FOUND, 1 NONE, 3 TARGET_NOT_FOUND. The likely cause is memory pressure with two large helpers running at once; this is not proven. The Colab fallback rebuild (2 jobs, 2 CPUs, ~12 GB) could hit it too; using the zip avoids that.
- **Reproducibility of the tables.** They were built with go1.26.10 from the module proxy and `go mod tidy -e` against the proxy of 26 Oct 2026. A rebuild elsewhere can differ where a module's requirements are incomplete. The notebook reports same/different/missing per case against the committed hashes; it does not stop on a difference.
- **Commit-diff hashes in Colab** may differ from this session if Colab's git prints diffs differently. That is only reported, not gated; the diffs are rebuilt there.
- **Ollama install check:** only tested with fakes (as in CP5b); the CP6 run will exercise it for real.
- **Session mistakes:** the failing-test push (section 4). A `pkill -f` pattern that matched my own shell, killing that command (no data lost; the build was restarted). A watch loop that could never end for the same `pgrep -f` reason (stopped). None of these changed any committed file.

## 9. Suggestions for the next checkpoint (not implemented)

- Run the agent twice with different seeds on a subset to measure run-to-run variance before reading small differences.
- If CP7 uses the agent at all, use its ranked list only as an ordering for reachability checks of several candidates, never as a single pick (the CP5 E1 finding).
- If the PACKAGE_NOT_LOADED share matters for A3, investigate the load errors (the helper's `first_errors`) for the largest D4 modules.

## 10. Git

Branch `claude/gracious-carson-ch1i9r`. Every commit below was pushed successfully (`git push`, no errors):

```
1d6579c CP6: committed summary of the agent evidence built in this session (...)
dc88703 CP6: budget comment states the repeat limit as it is coded (per run)
b06a23a CP6: STATUS - deliverables 1-6 ticked, handoff notes
f02d9bb CP6: document the agent tool contract, JSON action protocol and trace fields; README commands
6d1c1dc CP6: agent prepare builds one neighbour table per shared release range (118 D4 cases, 88 distinct ranges)
c3bee1e CP6: Colab notebook cp6_agent_colab.ipynb (...)
42da9a4 CP6: freeze agent prompts agent_v1 (FROZEN.json + test) before any real run
a55f200 CP6: contract tests - action schema = protocol code = system prompt = interfaces doc; (...)
29c1269 CP6: results renderer (results render --doc cp6): (...)
761f83c CP6: fix two agent unit tests for the new answer_ids_seen field (the previous commit was pushed with them failing)
675405b CP6: eval symbols --strategy agent (...)   <- CI red (two unit tests), fixed by 761f83c
235dfa7 CP6: CI installs the [agent] extra; (...)
a0eb361 CP6: agent core - LangGraph graph, JSON action protocol, closed-pool tools, budgets, (...)
dfb0b66 CP6: start - STATUS IN_PROGRESS, branch, task list
```
(plus the commit that adds this report and sets STATUS.)

## What the owner does next

1. Upload `cp6_graph_tables.zip` (sent with this session's final message) to Google Drive as `MyDrive/vulntrace_cp6/cp6_graph_tables.zip`.
2. In Colab (T4 GPU), open `notebooks/cp6_agent_colab.ipynb` from branch `claude/gracious-carson-ch1i9r` and run all cells. Re-run after a disconnect; finished cases are reused.
3. Hand `MyDrive/vulntrace_cp6/cp6_results.zip` (result JSON + traces) to the next Claude Code session.
