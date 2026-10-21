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

## Mode 2 path (no fix commit)

Used when C1 returns `UNAVAILABLE`, or when the evaluation deliberately hides the fix commit.

```
VulnCase ──► C10 Release-range candidates ──► ReleaseRange (changed functions + commit messages)
                    │
                    ▼
             C11 Indexer ──► CodeChunk records + embeddings ──► C12 Vector store
                    │
                    ▼
advisory ──► C13 Retriever (BM25 + dense → RRF → reranker; optional HyDE) ──► RetrievalRun (ranked candidates)
                    │
           ┌────────┴─────────┐
           ▼                  ▼
   C2 LLM selects       C14 Agent investigates
   from top-k            (tools, budget, trace)
           └────────┬─────────┘
                    ▼
            RootCauseSelection (closed set, validated) ──► C3 Lifter ──► same path as Mode 1
```

| Stage | Reads | Writes | Fails how |
|---|---|---|---|
| C10 | report versions; git tags or pseudo-version commits | `ReleaseRange` | Tag or commit not found → `CANT_DETERMINE` / `NO_FIX_EVIDENCE`. |
| C11 | `ReleaseRange`; module source at both versions | `CodeChunk` rows | Parse failure for a file → file skipped and counted. |
| C12 | chunks + embeddings | indexed store | Database unavailable → in-memory backend only if explicitly configured; never silently. |
| C13 | advisory text; store | `RetrievalRun` | Model endpoint down → stage reported as `ERROR`; no fallback that changes results silently. |
| C2 / C14 | top-k or tools | `RootCauseSelection` | Invalid or out-of-set answer → rejected; budget exceeded → `none_selected` with reason `BUDGET_EXCEEDED`. |

Index freshness: every chunk stores a content hash and the embedding model ID. Re-indexing a module version only re-embeds chunks whose hash or model changed. Chunks from different versions never mix in one query, because every search filters by `(module, version)`.

## Evaluation flow

The harness (C8) runs the same pipeline with extra controls:

- `hide_curated_symbols = true` forces the path through C1 to C3, so recovered symbols can be scored against the hidden labels.
- Results for each case are written as JSON lines, one per case, with all intermediate objects, so any metric can be recomputed later without re-running the pipeline or re-calling the LLM.

## Caching and reproducibility

- Git fetches are cached per repository directory.
- LLM responses, agent traces and embeddings are cached by a hash of (model ID, template or tool version, input payload). Cached outputs are committed (small) or archived with a documented checksum (large), so reported numbers are reproducible without re-running models.
- Every output records: Go version, GOOS/GOARCH, helper contract version, pipeline version, vulndb commit SHA.
