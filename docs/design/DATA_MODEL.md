# Data model

All objects are JSON. Each object type will have a JSON Schema (draft 2020-12) file under `schemas/`; the schema file is the source of truth, and this document explains it. Milestone 1 creates the schemas it needs; later milestones add the rest.

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

Produced by C2 (or by an experimental strategy in milestone 6).

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
  "llm": {"provider": "<provider>", "model": "<model id>",
          "prompt_template": "root_cause_v1", "prompt_sha256": "...",
          "response_sha256": "...", "input_tokens": 3120, "output_tokens": 210,
          "cached": false},
  "validation": {"status": "VALID", "errors": []}
}
```

Validation rules (enforced by code, not by the LLM):

- Every `candidate_id` must exist in `FixEvidence.candidates`.
- Every `cited_hunk_id` must exist and belong to that candidate.
- `reason` is stored for review but never used as evidence.
- Invalid output → `validation.status = INVALID`; nothing is passed on.

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

## FixtureManifest (synthetic suite, milestone 1)

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

Version 1 stores everything as JSON and JSON Lines files under `data/` and `results/`. A database is not needed at this scale (hundreds of cases). PostgreSQL remains an option if querying across runs becomes painful; see [ADR-006](../decisions/ARCHITECTURE_DECISIONS.md).
