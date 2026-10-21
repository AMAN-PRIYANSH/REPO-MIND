# Data flow

This document traces one case from input to verdict. Component names (C0 to C8) refer to [system architecture](SYSTEM_ARCHITECTURE.md). Object names refer to [data model](../design/DATA_MODEL.md).

## Inputs

1. An advisory ID (for example `GO-2026-5504`) and a local copy of `golang/vulndb`.
2. A target application: a local directory containing a Go module with at least one `package main`.
3. Run options: whether to hide curated symbols (evaluation only), which LLM model to use, output path.

## Main path

```
advisory ID ──► C0 Case loader ──► VulnCase
                                       │
                 curated symbols? ─────┤
                   yes                 │ no (or hidden for evaluation)
                    │                  ▼
                    │        C1 Fix evidence extractor ──► FixEvidence (candidates + hunks)
                    │                  │
                    │                  ▼
                    │        C2 Root-cause selector (LLM) ──► RootCauseSelection
                    │                  │
                    │                  ▼
                    │        C3 Symbol lifter ──► lifted TargetSymbols
                    ▼                  │
              TargetSymbols ◄──────────┘
                    │
        ┌───────────┴────────────┐
        ▼                        ▼
 C4a Call-graph reach     C4b Linker presence
 (MethodResult per sym)   (MethodResult per sym)
        └───────────┬────────────┘
                    ▼
             C5 Verdict engine ──► draft Verdict
                    ▼
             C6 Evidence verifier ──► final Verdict (+ reason codes)
                    ▼
             C7 Explainer (optional, text only)
                    ▼
             verdict JSON + human-readable report
```

## Stage details

| Stage | Reads | Writes | Fails how |
|---|---|---|---|
| C0 | report YAML | `VulnCase` | Malformed report → case skipped, error recorded. |
| C1 | fix commit URLs; git | `FixEvidence` | Commit unreachable → `FixEvidence.status = UNAVAILABLE`; case goes to the hard-case path. |
| C2 | `VulnCase` text + `FixEvidence` | `RootCauseSelection` | API error, invalid JSON, or IDs outside the candidate set → selection rejected, case gets `NO_TARGET_SYMBOLS`. |
| C3 | module source at `vulnerable_at`; root-cause functions | `TargetSymbol` list (origin `LIFTED`) | Module will not load → fall back to root-cause functions themselves, origin `ROOT_ONLY`, flagged. |
| C4a | target app; `TargetSymbol` list | `MethodResult` per symbol | Load/build failure → `ERROR`. |
| C4b | target app; `TargetSymbol` list | `MethodResult` per symbol | Build failure → `ERROR`. |
| C5 | both `MethodResult` lists | draft `Verdict` | Never fails; applies the rule table. |
| C6 | draft `Verdict`; source; call graph | final `Verdict` | Any unverifiable item → downgrade to `CANT_DETERMINE` with `VERIFIER_REJECTED`. |
| C7 | final `Verdict` | text | Failure only drops the explanation; verdict unchanged. |

## Hard-case path (no fix commit)

If C1 returns `UNAVAILABLE`, version 1 returns `CANT_DETERMINE` with reason `NO_FIX_EVIDENCE`.

Milestone 6 may test experimental strategies for this path (keyword search over the module source, hybrid retrieval, a single tool-using agent). They write the same `RootCauseSelection` object, so the rest of the pipeline is unchanged. They are never enabled by default unless measurement justifies it.

## Evaluation flow

The harness (C8) runs the same pipeline with extra controls:

- `hide_curated_symbols = true` forces the path through C1 to C3, so recovered symbols can be scored against the hidden labels.
- Results for each case are written as JSON lines, one per case, with all intermediate objects, so any metric can be recomputed later without re-running the pipeline or re-calling the LLM.

## Caching and reproducibility

- Git fetches are cached per repository directory.
- LLM responses are cached by a hash of (model ID, prompt template version, input payload). Cached responses are reused in re-runs, so reported numbers are reproducible without new API spend.
- Every output records: Go version, GOOS/GOARCH, helper contract version, pipeline version, vulndb commit SHA.
