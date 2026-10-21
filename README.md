# VulnTrace AI

VulnTrace AI is a Go-focused vulnerability reachability triage system.

Given a vulnerability advisory and a Go application's source code, it answers one question:

> Can this application's code actually reach the vulnerable function?

It returns one of three verdicts, with evidence:

- `REACHABLE` - a verified call path exists from the application's entry point to a vulnerable function.
- `NOT_REACHABLE` - independent analysis methods agree that no path exists.
- `CANT_DETERMINE` - evidence is missing, analysis failed, or the methods disagree.

VulnTrace AI reports reachability, not exploitability. A reachable function is not proof that the vulnerability can be exploited.

## Project status

Design phase. No application code exists yet.

Implementation will happen in small milestones. Each milestone must pass its acceptance criteria and be approved before the next one starts. See [the implementation roadmap](docs/implementation/IMPLEMENTATION_ROADMAP.md).

The repository is named `REPO-MIND` for historical reasons (the project started as a codebase-chat idea called RepoMind). Renaming it is an open question; see [risks and open questions](docs/decisions/RISKS_AND_OPEN_QUESTIONS.md).

## Design in one paragraph

Python orchestrates the pipeline. A small Go helper performs program analysis, because Go's own analysis libraries only exist in Go. Almost every step is deterministic code. One step uses an LLM: reading the advisory and the complete fix commit to choose the root-cause function. Code then lifts that function to public entry points, checks reachability with two independent methods, and verifies every piece of evidence before a verdict is produced. When the methods disagree, the system abstains.

## Documents

Start here:

1. [Project definition](docs/PROJECT_DEFINITION.md) - problem, users, scope, non-goals, success criteria.
2. [Feasibility findings](docs/research/FEASIBILITY_FINDINGS.md) - what was actually measured before design, and what was not.
3. [System architecture](docs/architecture/SYSTEM_ARCHITECTURE.md) - components, boundaries, deterministic vs LLM steps, verdict rule.

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

- [Implementation roadmap and milestone gates](docs/implementation/IMPLEMENTATION_ROADMAP.md)
- [Milestone 1 specification](docs/implementation/MILESTONE_1.md)
- [Claude Code Round 1 prompt](prompts/CLAUDE_CODE_ROUND_1.md)

Decisions:

- [Architecture decisions](docs/decisions/ARCHITECTURE_DECISIONS.md)
- [Risks and open questions](docs/decisions/RISKS_AND_OPEN_QUESTIONS.md)

## How facts are labelled in these documents

- **Verified** - observed in a recorded experiment or stated in a cited primary source.
- **Assumption** - believed true but not yet checked in this project.
- **Proposal** - a design choice that must be validated during implementation.
