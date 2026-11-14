# Development and evaluation commands

Moved here unchanged from the pre-CP8 README so the README can stay short. The commands for CP1 to CP6 are as they were when written; the current offline quickstart is in the [README](../README.md) and [DEMO.md](DEMO.md).

## Commands (CP1-CP6)

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
python -m vulntrace results render --doc cp1|cp2|cp3|cp4|cp5|cp5b|cp6 --input <report or dir> --out docs/results/<file>.md

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

# CP6: LangGraph investigation agent (Mode 2, D4). pip install -e ".[dev,agent]" (langgraph). Tests and --dry-run use fakes.
python -m vulntrace agent prepare --set d4 --diffs                # Go diffs of every release-range commit (read-only git)
python -m vulntrace agent prepare --set d4 --graph --jobs 2       # one-hop callers/callees of every candidate (Go + module proxy)
python -m vulntrace eval symbols --strategy agent --set d4 --arm A2 --arm A3 --model llama3.1-8b --device cuda   # needs .[ml]
python -m vulntrace eval symbols --strategy agent --set d4 --dry-run           # fake LLM + fake embedder on real evidence
python -m vulntrace agent show-trace --trace data/agent_traces/A2__llama3.1-8b/<case>.json.gz --data-dir data
python -m vulntrace results render --doc cp6 --input docs/results/cp6 --out docs/results/CP6_AGENT_RESULTS.md
# Real runs: notebooks/cp6_agent_colab.ipynb (free Colab GPU + Ollama), which zips the agent result JSON and the traces.

# Opt-in, not run in CI: fetches one real advisory's evidence from the real network
VULNTRACE_NETWORK_TESTS=1 python -m pytest tests/integration/test_network_smoke.py
```
