# Implementation roadmap and checkpoint gates

Target: about 4 weeks of calendar time. The work is split into 8 checkpoints. Each checkpoint is built by Claude Code, reviewed by the supervising assistant and the owner, and only then is the next one released.

Only CP1 has a full specification now. Each later specification is written by the supervising assistant when the previous checkpoint is approved, using what was actually learned. The outlines below fix scope and acceptance themes so nothing important is forgotten.

## How a checkpoint moves

1. The supervising assistant writes `docs/implementation/checkpoints/CPn.md` and sets STATUS.md to `READY`.
2. The owner starts Claude Code with the model and effort named in the spec and pastes `prompts/SESSION_WRAPPER.md`.
3. Claude Code works on its own session branch (`claude/...`), committing and pushing after each task. If it hits a usage limit, it leaves handoff notes in STATUS.md on that branch; the owner pastes the same wrapper in a new session, which finds that branch and fast-forwards onto it (`CLAUDE.md` section 5).
4. Claude Code writes the report and sets `AWAITING_REVIEW`.
5. The supervising assistant reviews the branch: runs or inspects tests, checks every acceptance criterion against evidence, reads samples of output. Result: `APPROVED` (branch merged into `main`) or `CHANGES_REQUESTED` (notes added to the spec).

## Model and effort per checkpoint

| CP | Model | Effort | Why |
|---|---|---|---|
| CP1 | Sonnet 5.5 | medium | Routine Python, small Go fixtures |
| CP2 | Opus 5.5 | high | Go SSA/VTA analysis code is subtle |
| CP3 | Sonnet 5.5 | high | Data parsing, git edge cases, CI setup |
| CP4 | Opus 5.5 | high | Retrieval architecture, interfaces, evaluation harness |
| CP5 | Sonnet 5.5 | high | LLM client, validation, caching, notebooks |
| CP5b | Opus 5.5 | high | Go call-graph lifting and caller/callee queries (subtle analysis code) |
| CP6 | Opus 5.5 | high | Agent design, tools, budgets, failure handling |
| CP7 | Opus 5.5 | high | Verifier and end-to-end integration |
| CP7b | Sonnet 5.5 | high | D3 real applications, adjudication sheets, static demo page (Streamlit dropped) |
| CP8 | Sonnet 5.5 | medium | Experiment variant, reports, README |

Never use Fable or 1M-context models (they can use paid credits). Avoid `max` effort.

## Checkpoint outlines

### CP1 - Ground truth and linker presence (week 1)

Full spec: [checkpoints/CP1.md](checkpoints/CP1.md).

### CP2 - Go call-graph helper and verdict rule (week 1)

- `helper/` Go module (pins `golang.org/x/tools`) with modes `funcs`, `reach` (VTA), `edges`, `naive`. (`lift` is added in CP5b.)
- Python wrapper with timeouts and error codes; contract tests with recorded responses.
- Naive name-only call graph as a negative control (R1).
- Verdict rule (two-method agreement) and verdict schema; fixtures extended to about 20 cases.
- Gate: R1-R4 scored on the fixture suite; zero false `NOT_REACHABLE` for the combined rule, or each exception explained.

### CP3 - Advisory dataset, fix evidence, release-range candidates, baselines, CI (week 2)

- vulndb report reader at a pinned commit; `VulnCase` builder.
- Fix-commit evidence (Mode 1) and release-range candidate extraction (Mode 2: functions changed between `vulnerable_at` and the first fixed tag), including pseudo-version handling.
- Datasets D1 (fix commit) and D4 (release range, fix commit hidden).
- Baselines: E0 (all changed functions) and B-ID (search commit messages in the release range for the advisory's CVE/GHSA IDs).
- Gate: re-run of feasibility trials 2 and 5 at full size, reported with intervals.

### CP4 - Retrieval stack (week 2)

- Function-level chunking via the helper; chunk text = package, signature, doc comment, body, plus linked commit messages.
- `VectorStore` interface with two backends: in-memory (tests) and PostgreSQL + pgvector (real runs, via Docker Compose).
- BM25 (Python), dense embeddings (`Embedder` interface; fake for tests, sentence-transformers model for real runs), Reciprocal Rank Fusion, cross-encoder reranker interface.
- Retrieval evaluation harness (Recall@k, MRR, nDCG) over D4.
- Colab notebook that runs the real models and writes result files.
- Gate: harness runs end-to-end on fakes in tests; at least one real run (BM25, dense, hybrid, hybrid+rerank) produced in Colab and committed as result files.

### CP5 - Local LLM layer, root-cause selection, HyDE (week 2-3)

Full spec: [checkpoints/CP5.md](checkpoints/CP5.md). `LLMClient` (any OpenAI-compatible local endpoint, paid hosts rejected), response cache, closed-set validation; E1 (Mode 1) vs E0; S1 (Mode 2 top-k) vs retrieval top-1; HyDE; contamination split with the real model cutoff; Colab notebook running Ollama. Lifting was moved to CP5b because it is Go analysis work and the CP6 agent tools (`callers`, `callees`) need the same helper mode.

### CP5b - Lifting and caller/callee queries (week 3)

- Go helper `lift` mode (and `callers`/`callees` queries): from a root-cause function, find exported callers; stopping rule per open question Q4 (nearest exported caller vs all), measured on both.
- Scored against vulndb `derived_symbols` (they are exactly the lifted symbols) and used for E1+L; addresses CP3 finding 4 (labelled function unchanged in the range) and risk R5.
- Report dependency-loading success rate honestly (real modules need their dependencies; builds use `GOTOOLCHAIN=local`, `CGO_ENABLED=0`, never run target code).
- Gate: lift recall and precision against `derived_symbols` with intervals; E1+L reported next to E1.

### CP6 - LangGraph investigation agent (week 3)

- Single agent built with LangGraph; tools: search_code, read_function, search_commits, show_commit, callers, callees, submit_answer.
- Step and time budgets; closed-set validation of the final answer; full trace saved.
- Evaluated on D4 against the best non-agent retrieval pipeline.
- Gate: agent vs pipeline report, including cost in time and tokens, failures and traces.

### CP7 - End-to-end triage and verifier (week 4)

- `triage` command for both modes: symbols (Mode 1: all changed non-test functions, no LLM narrowing; Mode 2: retrieval top-k), optional lifting as candidate widening only, two-method reachability, verdict rule, downgrade-only evidence verifier.
- No agent in the pipeline (CP6 negative result).
- Evaluated on D1/D4 evidence and the fixtures: verdict distribution, false NOT_REACHABLE rate, verifier rejections.
- Gate: every `REACHABLE` has a verified path; every `NOT_REACHABLE` states what it covers; failures reported.

### CP7b - Real applications and demo (week 4)

- D3: 5 real applications, adjudicated by the owner with the supervising assistant's help.
- A minimal local demo (CLI output, plus a small Streamlit page if time allows).
- Gate: D3 results reported with failures and the owner's adjudication.

### CP8 - Multi-agent experiment (stretch) and final report (week 4)

- Optional: investigator + sceptic-reviewer pair in LangGraph vs the single agent, on D4.
- Final results summary, README with real numbers, limitations, interview notes.
- Gate: every headline number reproducible from committed result files.

## If time runs short

Drop in this order: CP8 multi-agent experiment, then the Streamlit page, then D3 down to 3 apps. Never drop baselines, the verifier, or honest reporting.
