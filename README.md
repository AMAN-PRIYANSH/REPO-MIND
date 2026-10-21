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

## Development (CP1)

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
python -m pytest tests/unit          # needs only Python
python -m pytest tests/integration   # needs Go; skips with a message if missing
python -m vulntrace doctor
python -m vulntrace fixtures score --method linker [--out results/cp1] [--compare-inlining]
```
