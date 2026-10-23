# VulnTrace AI

VulnTrace AI is a Go vulnerability reachability triage system.

Given a vulnerability advisory and a Go application's source code, it answers:

> Can this application's code actually reach the vulnerable function?

It returns one of three verdicts, with evidence:

- `REACHABLE` - a verified call path exists from the application's entry point to a vulnerable function.
- `NOT_REACHABLE` - two independent analysis methods agree that no path exists.
- `CANT_DETERMINE` - evidence is missing, analysis failed, or the methods disagree.

It reports reachability, not exploitability.

## Two modes

**Mode 1 - fix commit available.** The fix diff is small, so a local LLM reads the whole diff and picks the root-cause function from a closed list. No retrieval needed.

**Mode 2 - investigation mode.** No fix commit. The system searches the functions that changed between the vulnerable and the fixed release, which can be hundreds or thousands. This mode uses advanced RAG (hybrid BM25 + dense search, Reciprocal Rank Fusion, cross-encoder reranking, HyDE query rewriting), a PostgreSQL + pgvector store with versioned indexing, and a LangGraph investigation agent. Every one of these is measured against simpler baselines.

Both modes end in deterministic reachability analysis (a VTA call graph and a linker check) and an evidence verifier that can only downgrade a verdict.

Everything runs on free, open models (local or Google Colab). Total cost: zero.

## Project status

Design complete. Implementation runs in 8 checkpoints; see [progress status](docs/progress/STATUS.md) and the [roadmap](docs/implementation/IMPLEMENTATION_ROADMAP.md).

The repository is named `REPO-MIND` for historical reasons (the project started as a codebase-chat idea called RepoMind).

## How the build works

- Claude Code builds one checkpoint at a time, following [CLAUDE.md](CLAUDE.md).
- Start every Claude Code session by pasting [the session wrapper](prompts/SESSION_WRAPPER.md).
- Progress and handoff notes live in [docs/progress/STATUS.md](docs/progress/STATUS.md).
- Each checkpoint ends with a report in `docs/progress/reports/` and waits for review.

## Documents

Start here:

1. [Project definition](docs/PROJECT_DEFINITION.md) - problem, two modes, scope, zero-cost constraint, success criteria.
2. [Feasibility findings](docs/research/FEASIBILITY_FINDINGS.md) - what was measured before design, and what was not.
3. [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) - components, models, verdict rule.

Design detail:

- [Data flow](docs/architecture/DATA_FLOW.md)
- [Data model](docs/design/DATA_MODEL.md)
- [Interfaces and contracts](docs/design/INTERFACES_AND_CONTRACTS.md)
- [Planned project structure](docs/design/PROJECT_STRUCTURE.md)

Evaluation and testing:

- [Evaluation plan, metrics and baselines](docs/evaluation/EVALUATION_PLAN.md)
- [Dataset strategy](docs/evaluation/DATASET_STRATEGY.md)
- [Testing strategy](docs/testing/TESTING_STRATEGY.md)

Delivery:

- [Implementation roadmap](docs/implementation/IMPLEMENTATION_ROADMAP.md)
- [Checkpoint 1 specification](docs/implementation/checkpoints/CP1.md)

Decisions:

- [Architecture decisions](docs/decisions/ARCHITECTURE_DECISIONS.md)
- [Risks and open questions](docs/decisions/RISKS_AND_OPEN_QUESTIONS.md)

## How facts are labelled

- **Verified** - observed in a recorded experiment or stated in a cited primary source.
- **Assumption** - believed true but not yet checked.
- **Proposal** - a design choice to be validated during implementation.

## Development (CP1-CP5b)

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
python -m pytest tests/unit tests/contract   # needs only Python
python -m pytest tests/integration           # needs Go and git; skips with a message if missing
(cd helper && GOTOOLCHAIN=local GOPROXY=off go test ./...)
python -m vulntrace doctor
python -m vulntrace helper fetch             # once: downloads the helper's Go dependencies (network)
python -m vulntrace helper build             # offline build into ~/.cache/vulntrace (never into the repo)
python -m vulntrace fixtures score --method linker [--out results/cp1] [--compare-inlining]
python -m vulntrace fixtures score --method naive|vta|combined [--out results/cp2] [--timeout 300]
python -m vulntrace results render --doc cp1|cp2|cp3|cp4|cp5|cp5b --input <report or dir> --out docs/results/<file>.md

# CP3: datasets (network) and baselines
python -m vulntrace dataset fetch                     # pin golang/vulndb's data/reports/ snapshot
python -m vulntrace dataset build --mode fix           # D1: FixEvidence for 150 sampled advisories
python -m vulntrace dataset build --mode release       # D4: ReleaseRange for 120 sampled advisories
python -m vulntrace eval symbols --strategy e0          # baseline: every changed function
python -m vulntrace eval symbols --strategy id-search   # baseline: commit-message identifier search

# CP4: re-materialise evidence for the committed case lists (network; resumable; never re-selects)
python -m vulntrace dataset materialize --set d4       # data/release_range + data/candidate_code
python -m vulntrace dataset materialize --set d1       # data/fix_evidence (for E0 re-scoring)
# CP4: retrieval (fakes and BM25 need no model; real models via .[ml], normally in Colab)
pip install -e ".[dev,db]"                             # db: psycopg + pgvector for the pgvector store
docker compose up -d pgvector                          # optional: PostgreSQL 16 + pgvector on localhost
VULNTRACE_REQUIRE_PG=1 python -m pytest tests/contract/test_vector_store.py   # both backends, no skips
python -m vulntrace eval retrieval --config random --config size --config bid --config bid-only --config bm25
python -m vulntrace index build --set d4 --embedder bge-small --device cuda     # needs .[ml]
python -m vulntrace eval retrieval --config dense:bge-small --config hybrid:bge-small \
    --config hybrid+rerank:bge-small+minilm --device cuda                       # needs .[ml]
# Real-model runs: notebooks/cp4_retrieval_colab.ipynb (free Colab GPU), which zips results/cp4 JSON.

# CP5: local LLM layer (Ollama on localhost only; paid API hosts are refused). Tests and --dry-run use fakes.
python -m vulntrace eval select --mode fix --model qwen2.5-coder-7b                # E1 on D1, E0 in the same file
python -m vulntrace eval select --mode release --model qwen2.5-coder-7b --k 10     # S1 on D4, retriever top-1 in the same file
python -m vulntrace eval retrieval --hyde query+hyde --hyde hyde-only --model qwen2.5-coder-7b   # HyDE on D4
python -m vulntrace eval select --mode release --dry-run                           # pipeline check with fake LLM + fake embedder
# Real runs: notebooks/cp5_llm_colab.ipynb (free Colab GPU + Ollama), which zips results/cp5 JSON.

# CP5b: lifting and call-graph queries (Go helper modes lift, callers, callees; no model). `eval lift` uses the network
# (module proxy, GitHub via the materialised git cache) and writes per-case evidence under data/lift (gitignored).
# Modules that need a newer Go than the local one fail with the first error line; use a newer local `go` on PATH (GOTOOLCHAIN stays local).
python -m vulntrace eval lift --set d1 --jobs 2 --out docs/results/cp5b            # lifting vs derived_symbols + E1+L on the committed CP5 selections
python -m vulntrace eval lift --set d4-ceiling --jobs 2 --out docs/results/cp5b    # needs `dataset materialize --set d4` first
python -m vulntrace results render --doc cp5b --input docs/results/cp5b --out docs/results/CP5B_LIFTING_RESULTS.md

# Opt-in, not run in CI: fetches one real advisory's evidence from the real network
VULNTRACE_NETWORK_TESTS=1 python -m pytest tests/integration/test_network_smoke.py
```
