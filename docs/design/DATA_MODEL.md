# Data model

All objects are JSON. Each object type will have a JSON Schema (draft 2020-12) file under `schemas/`; the schema file is the source of truth, and this document explains it. CP1 creates the schemas it needs; later checkpoints add the rest.

Every top-level object carries `"schema_version"`. Version 1 objects use `"1.0"`. Breaking changes bump the major number.

## Conventions

- File paths are relative to the repository or module root and always use forward slashes, including on Windows.
- Line numbers are 1-based and inclusive.
- Go symbols use the Go vulnerability database format: `Func` for functions, `Type.Method` for methods (no pointer star). Package path is stored separately.
- Timestamps are ISO 8601 UTC.
- Enum values are UPPER_SNAKE_CASE.

## VulnCase

One advisory, as loaded by C0.

```json
{
  "schema_version": "1.0",
  "id": "GO-2026-5504",
  "aliases": ["CVE-2026-35166", "GHSA-mcv8-8m8x-48pg"],
  "summary": "Hugo: Certain markdown links are not properly escaped",
  "module": "github.com/gohugoio/hugo",
  "vulnerable_at": "0.159.1",
  "fixed_in": "0.159.2",
  "review_status": "REVIEWED",
  "created": "2026-07-07",
  "fix_commits": [
    {"host": "github.com", "owner": "gohugoio", "repo": "hugo",
     "sha": "479fe6c654937a850b65e74551dc4e857d52898f"}
  ],
  "curated_symbols": {
    "core": [
      {"package": "github.com/gohugoio/hugo/markup/goldmark",
       "symbol": "hookedRenderer.renderImageDefault"}
    ],
    "derived": [
      {"package": "github.com/gohugoio/hugo/markup/goldmark",
       "symbol": "goldmarkConverter.Convert"}
    ]
  },
  "source": {"vulndb_commit": "<sha of golang/vulndb checkout>", "report_path": "data/reports/GO-2026-5504.yaml"}
}
```

`curated_symbols` is used as ground truth in evaluation and is hidden from C1 to C3 when `hide_curated_symbols` is set.

## FixEvidence

Produced by C1.

```json
{
  "schema_version": "1.0",
  "case_id": "GO-2026-5504",
  "status": "AVAILABLE",
  "commits": [{"sha": "479fe6c6...", "parent_sha": "a1b2c3d4..."}],
  "candidates": [
    {
      "candidate_id": "c1",
      "package_dir": "markup/goldmark",
      "symbol": "hookedRenderer.renderImageDefault",
      "side": "BOTH",
      "old_range": {"file": "markup/goldmark/render_hooks.go", "start": 210, "end": 248},
      "new_range": {"file": "markup/goldmark/render_hooks.go", "start": 210, "end": 251},
      "hunk_ids": ["h3", "h4"]
    }
  ],
  "hunks": [
    {"hunk_id": "h3", "file": "markup/goldmark/render_hooks.go",
     "old_start": 231, "old_lines": 1, "new_start": 231, "new_lines": 2,
     "text": "-    w.Write(...)\n+    ..."}
  ],
  "non_go_files_changed": ["docs/content/en/..."],
  "estimated_tokens": 572
}
```

- `status`: `AVAILABLE`, `UNAVAILABLE` (no fetchable commit), `EMPTY` (no non-test Go changes).
- `side`: `OLD` (function deleted), `NEW` (added), `BOTH`.
- Test files (`_test.go`) are excluded from `candidates` but their count is recorded.

## RootCauseSelection

Produced by C2 (Mode 1), or by C13/C14 (Mode 2).

```json
{
  "schema_version": "1.0",
  "case_id": "GO-2026-5504",
  "strategy": "LLM_FULL_DIFF",
  "selected": [
    {"candidate_id": "c1", "cited_hunk_ids": ["h3"],
     "reason": "Image destination is written without escaping."}
  ],
  "none_selected": false,
  "llm": {"endpoint_kind": "OLLAMA", "model": "qwen2.5-coder:7b-instruct",
          "model_digest": "<digest reported by the server>",
          "prompt_template": "root_cause_v1", "prompt_sha256": "...",
          "response_sha256": "...", "input_tokens": 3120, "output_tokens": 210,
          "temperature": 0, "seed": 7, "cached": false},
  "retrieval_run_id": null,
  "agent_trace_id": null,
  "validation": {"status": "VALID", "errors": []}
}
```

`strategy`: `LLM_FULL_DIFF` (Mode 1), `LLM_TOPK` (Mode 2, selection from retrieved top k), `AGENT` (Mode 2, LangGraph agent), `MULTI_AGENT` (CP8 experiment), `BASELINE_E0`, `BASELINE_ID_SEARCH`.

In Mode 2, `candidate_id` refers to `ReleaseRange.candidates` instead of `FixEvidence.candidates`.

Validation rules (enforced by code, not by the LLM):

- Every `candidate_id` must exist in `FixEvidence.candidates`.
- Every `cited_hunk_id` must exist and belong to that candidate.
- `reason` is stored for review but never used as evidence.
- Invalid output → `validation.status = INVALID`; nothing is passed on.

## ReleaseRange (Mode 2)

Produced by C10.

```json
{
  "schema_version": "1.0",
  "case_id": "GO-2026-5504",
  "module": "github.com/gohugoio/hugo",
  "from": {"version": "0.159.1", "ref": "v0.159.1", "commit": "..."},
  "to":   {"version": "0.159.2", "ref": "v0.159.2", "commit": "..."},
  "candidates": [
    {"candidate_id": "r17", "package_dir": "markup/goldmark",
     "symbol": "hookedRenderer.renderImageDefault", "side": "BOTH",
     "new_range": {"file": "markup/goldmark/render_hooks.go", "start": 210, "end": 251}}
  ],
  "commits": [{"sha": "...", "subject": "markup/goldmark: escape image destinations",
               "touches_candidates": ["r17"]}],
  "status": "AVAILABLE"
}
```

`status`: `AVAILABLE`, `TAG_NOT_FOUND`, `PSEUDO_VERSION_UNRESOLVED`, `EMPTY`.

## CodeChunk (Mode 2)

One indexed function. Stored in the vector store (C12).

```json
{
  "chunk_id": "github.com/gohugoio/hugo@0.159.2:markup/goldmark:hookedRenderer.renderImageDefault",
  "module": "github.com/gohugoio/hugo",
  "version": "0.159.2",
  "package": "github.com/gohugoio/hugo/markup/goldmark",
  "symbol": "hookedRenderer.renderImageDefault",
  "file": "markup/goldmark/render_hooks.go", "start": 210, "end": 251,
  "changed_in_range": true,
  "candidate_id": "r17",
  "text": "package goldmark\nfunc (r *hookedRenderer) renderImageDefault(...)\n// doc comment...\n<body>\nCommits: escape image destinations",
  "content_sha256": "...",
  "embedding_model": "<model id>",
  "embedding": [0.012, -0.044, "..."]
}
```

## RetrievalRun (Mode 2)

```json
{
  "schema_version": "1.0",
  "run_id": "...",
  "case_id": "GO-2026-5504",
  "config": {"sparse": "BM25", "dense": "<embedding model>", "fusion": "RRF", "rrf_k": 60,
             "reranker": "<model or null>", "hyde": false, "top_k": 20},
  "ranked": [{"candidate_id": "r17", "score": 0.91, "sources": ["BM25", "DENSE"]}],
  "timing_ms": {"sparse": 12, "dense": 40, "rerank": 900},
  "provenance": {"index_built_at": "...", "pipeline_version": "0.x"}
}
```

## AgentTrace (Mode 2)

```json
{
  "schema_version": "1.0",
  "trace_id": "...",
  "case_id": "GO-2026-5504",
  "agent": "investigator_v1",
  "budget": {"max_steps": 12, "max_seconds": 600},
  "steps": [
    {"n": 1, "tool": "search_commits", "args": {"query": "escape image"},
     "result_summary": "2 commits", "duration_ms": 30},
    {"n": 2, "tool": "read_function", "args": {"candidate_id": "r17"},
     "result_summary": "42 lines", "duration_ms": 5}
  ],
  "final": {"tool": "submit_answer", "candidate_ids": ["r17"], "valid": true},
  "stop_reason": "SUBMITTED",
  "llm": {"model": "...", "input_tokens": 18400, "output_tokens": 920}
}
```

`stop_reason`: `SUBMITTED`, `BUDGET_EXCEEDED`, `INVALID_ANSWER`, `ERROR`.

## TargetSymbol

The symbols whose reachability is checked.

```json
{
  "package": "github.com/gohugoio/hugo/markup/goldmark",
  "symbol": "goldmarkConverter.Convert",
  "origin": "LIFTED",
  "lifted_from": ["hookedRenderer.renderImageDefault"]
}
```

`origin`: `CURATED_CORE`, `CURATED_DERIVED`, `ROOT_CAUSE`, `LIFTED`, `ROOT_ONLY` (lifting failed), `FIXTURE` (synthetic suite).

## SourceLocation

```json
{"module": "example.com/app", "version_or_commit": "v1.2.3",
 "file": "cmd/server/main.go", "line": 42}
```

## CallPath

An ordered list of edges from an entry point to a target symbol.

```json
{
  "entry": {"package": "example.com/app/cmd/server", "symbol": "main"},
  "target": {"package": "github.com/gohugoio/hugo/markup/goldmark", "symbol": "goldmarkConverter.Convert"},
  "edges": [
    {"caller": "example.com/app/cmd/server.main",
     "callee": "example.com/app/internal/render.Page",
     "call_site": {"file": "cmd/server/main.go", "line": 42},
     "kind": "STATIC"},
    {"caller": "example.com/app/internal/render.Page",
     "callee": "github.com/gohugoio/hugo/markup/goldmark.goldmarkConverter.Convert",
     "call_site": {"file": "internal/render/page.go", "line": 88},
     "kind": "DYNAMIC"}
  ]
}
```

`kind`: `STATIC` (direct call), `DYNAMIC` (interface or function-value call resolved by VTA). Dynamic edges are shown to the user so they can judge them.

## MethodResult

One reachability method's answer for one target symbol.

```json
{
  "schema_version": "1.0",
  "method": "LINKER_PRESENCE",
  "target": {"package": "ctrl/vulnlib", "symbol": "Parse"},
  "main_package": "ctrl/cmd/a_direct",
  "result": "PRESENT",
  "details": {"matched_binary_symbols": ["ctrl/vulnlib.Parse"],
              "build_flags": ["-gcflags=all=-l"],
              "go_version": "go1.24.7", "goos": "linux", "goarch": "amd64"},
  "error": null,
  "duration_ms": 812
}
```

- `method`: `LINKER_PRESENCE` or `CALLGRAPH_VTA`.
- `result` for linker: `PRESENT`, `ABSENT`, `ERROR`. For call graph: `PATH_FOUND`, `NO_PATH`, `ERROR`.
- Call-graph results put the shortest found `CallPath` in `details.path`.
- `error`: `{"code": "...", "message": "..."}` when `result` is `ERROR`.

## Verdict

```json
{
  "schema_version": "1.0",
  "case_id": "GO-2026-5504",
  "target_app": {"path": "examples/app1", "module": "example.com/app", "commit": "..."},
  "verdict": "CANT_DETERMINE",
  "reason_codes": ["METHOD_DISAGREEMENT"],
  "per_symbol": [
    {"target": {"package": "...", "symbol": "goldmarkConverter.Convert"},
     "result": "CANT_DETERMINE",
     "reason_code": "METHOD_DISAGREEMENT",
     "methods": {"CALLGRAPH_VTA": "NO_PATH", "LINKER_PRESENCE": "PRESENT"},
     "verified_path": null}
  ],
  "verification": {"status": "PASSED", "checks_run": 14, "failures": []},
  "statement": "Reachability only. This verdict does not assess exploitability.",
  "provenance": {"pipeline_version": "0.x", "helper_contract": "1.0",
                 "vulndb_commit": "...", "created_at": "2026-10-21T10:00:00Z"}
}
```

- `verdict`: `REACHABLE`, `NOT_REACHABLE`, `CANT_DETERMINE`.
- `reason_codes`: `NO_TARGET_SYMBOLS`, `NO_FIX_EVIDENCE`, `METHOD_DISAGREEMENT`, `ANALYSIS_FAILED`, `VERIFIER_REJECTED`, `UNSUPPORTED_TARGET` (e.g. no `main` package).
- `statement` is fixed text and always present.

## FixtureManifest (synthetic suite, CP1)

```json
{
  "schema_version": "1.0",
  "module_dir": "fixtures/reachability",
  "vulnerable_package": "vtfixtures/vulnlib",
  "cases": [
    {"id": "direct_call", "category": "DIRECT",
     "main_package": "vtfixtures/cmd/direct_call",
     "targets": [{"package": "vtfixtures/vulnlib", "symbol": "Parse"}],
     "truth": "REACHABLE",
     "rationale": "main calls vulnlib.Parse directly."}
  ]
}
```

`truth` is set by construction and must be justified in `rationale`. Expected outcomes of individual methods are not stored in the manifest; they are observed and reported.

## Storage

- Cases, verdicts, retrieval runs, agent traces and reports: JSON / JSON Lines files under `data/` and `results/` (easy to diff and review). See [ADR-006](../decisions/ARCHITECTURE_DECISIONS.md).
- Code chunks and embeddings: PostgreSQL + pgvector, one table with metadata columns (`module`, `version`, `package`, `symbol`, `changed_in_range`, `content_sha256`, `embedding_model`) and a vector column, plus an in-memory backend with the same interface for tests. See [ADR-007](../decisions/ARCHITECTURE_DECISIONS.md).
