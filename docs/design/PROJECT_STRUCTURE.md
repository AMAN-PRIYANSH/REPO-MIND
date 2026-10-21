# Planned project structure

This is the planned layout for implementation. None of the code directories exist yet. Each milestone creates only the parts listed for it.

```
REPO-MIND/
├── README.md
├── pyproject.toml                    # M1: Python package metadata, dev dependencies
├── .gitignore                        # M1: ignores results/, caches, .env, built binaries
├── docs/                             # design documents (this phase)
├── prompts/                          # Claude Code handoff prompts
├── schemas/                          # M1+: JSON Schema files (source of truth for data model)
│   ├── fixture_manifest.schema.json  # M1
│   ├── method_result.schema.json     # M1
│   ├── verdict.schema.json           # M2
│   ├── vuln_case.schema.json         # M3
│   ├── fix_evidence.schema.json      # M3
│   └── root_cause_selection.schema.json  # M4
├── src/vulntrace/                    # Python package
│   ├── __main__.py                   # M1: CLI entry (doctor, fixtures score)
│   ├── env.py                        # M1: tool detection for `doctor`
│   ├── schemas.py                    # M1: schema loading and validation helpers
│   ├── methods/linker.py             # M1: linker-presence method
│   ├── methods/callgraph.py          # M2: wrapper around the Go helper
│   ├── verdict.py                    # M2: verdict rule table
│   ├── dataset/                      # M3: vulndb reader, fix evidence extraction
│   ├── llm/                          # M4: provider client, prompt templates, cache
│   ├── lift.py                       # M4: wrapper around helper `lift` mode
│   ├── verify.py                     # M5: evidence verifier
│   ├── pipeline.py                   # M5: end-to-end triage
│   └── eval/                         # M1+: scoring and report writers
├── helper/                           # M2: Go module for vt-helper (VTA, lift, edges, funcs)
├── fixtures/reachability/            # M1: Go module with synthetic cases and manifest.json
├── tests/
│   ├── unit/                         # M1+
│   ├── contract/                     # M2+: recorded Go-helper responses checked against schemas
│   └── integration/                  # M1+ (skip with a clear reason if `go` is missing)
├── data/                             # M3+: generated case files (gitignored except small samples)
└── results/                          # gitignored run outputs; selected reports copied into docs/results/
```

## Rules

- Python 3.11 or newer, `src/` layout.
- Dependencies are added only when a milestone needs them, and recorded with a reason in the milestone report.
- Go helper and fixtures are separate Go modules, so fixture code never mixes with analysis code.
- Fixture modules have no external dependencies, so they build with `GOPROXY=off`.
- Large or regenerable data is not committed. Small, reviewed result summaries are committed under `docs/results/`.
- Whether to redistribute any golang/vulndb content in this repository depends on its licence terms, which have not been checked yet (open question).
