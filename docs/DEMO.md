# Demo: one offline page with verdicts

`python -m vulntrace demo build` turns verdict JSON files into **one** static HTML file: verdict, mode, target
symbols with origin and rank, call paths with file and line, the evidence verifier's checks, coverage and
limitations. The page has no scripts and no external assets, and its Content-Security-Policy forbids loading
anything, so it works offline and can be opened straight from disk. A verdict is about **reachability only**
(a call path from a `main` package exists in the call graph), never exploitability.

All commands run from the repository root. Builds of analysed code use `GOTOOLCHAIN=local` and `CGO_ENABLED=0`;
nothing from an analysed application is executed.

## Setup (once)

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

```bash
.venv/bin/python -m vulntrace helper fetch
```

`helper fetch` downloads the Go helper's dependencies (network). Go must be on `PATH`.

## 1. A fixture (no network after setup)

Write a small advisory file for the synthetic fixture suite:

```bash
mkdir -p data/demo && printf '%s' '{"id": "FIXTURE-PARSE", "summary": "vulnlib.Parse mishandles input (synthetic fixture)", "module": "vtfixtures", "fix_commits": []}' > data/demo/fixture_advisory.json
```

Triage the `direct_call` fixture for the target `vtfixtures/vulnlib.Parse` (expected: `REACHABLE`, verifier `PASSED`):

```bash
.venv/bin/python -m vulntrace triage --advisory-file data/demo/fixture_advisory.json --app fixtures/reachability --mode targets --target vtfixtures/vulnlib:Parse --main ./cmd/direct_call --out data/demo/fixture_direct_call.json
```

Build the page:

```bash
.venv/bin/python -m vulntrace demo build --verdict data/demo/fixture_direct_call.json --out data/demo/fixture.html
```

Open `data/demo/fixture.html` in a browser.

## 2. A D3 case (a real application; committed verdict, no network)

Every D3 verdict is committed under `docs/results/cp7b/verdicts/` (local paths rewritten: `$GOMODCACHE/...` for
module-cache files, `$GOROOT/...` for the standard library). Build the page for one case:

```bash
.venv/bin/python -m vulntrace demo build --verdict docs/results/cp7b/verdicts/gitleaks__GO-2025-4020.json --out data/demo/d3.html
```

Or all D3 cases on one page:

```bash
.venv/bin/python -m vulntrace demo build --dir docs/results/cp7b/verdicts --out data/demo/d3_all.html
```

To recompute a D3 verdict instead of using the committed one (network: git, Go module proxy; Go 1.26 on `PATH`, as
recorded in the results), fetch the vulndb snapshot, extract the pinned application with `d3 select --out`, run the
one case into a scratch directory, and build the page from it. Writing to `data/demo/...` keeps the committed files
in `docs/results/cp7b/` unchanged:

```bash
.venv/bin/python -m vulntrace dataset fetch
```

```bash
.venv/bin/python -m vulntrace d3 select --out data/demo/d3_select
```

```bash
.venv/bin/python -m vulntrace eval triage --set d3 --cases data/demo/d3_select/d3_cases.json --only gitleaks__GO-2025-4020 --out data/demo/d3_rerun
```

```bash
.venv/bin/python -m vulntrace demo build --dir data/demo/d3_rerun/verdicts --out data/demo/d3_rerun.html
```
