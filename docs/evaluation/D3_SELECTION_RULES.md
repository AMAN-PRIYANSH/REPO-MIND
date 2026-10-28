# D3 selection rules (CP7b deliverable 1)

Written and committed **before** any candidate repository was probed and before any D3 triage
result existed. `python -m vulntrace d3 select` applies these rules by code
(`src/vulntrace/d3/select.py`) and prints, for every candidate, the rule that kept or dropped it.
A rule change after this commit is disclosed in the CP7b report with its reason; nothing is
changed after triage results are seen. The owner may veto an application; a vetoed application is
not replaced by one chosen after results.

## Inputs

- Candidate applications: [`d3_candidates.json`](d3_candidates.json), fixed with this document.
  Well-known open-source Go applications from different domains, written down without probing
  them. Each has a coarse `domain` label, assigned up front, used only by the diversity rule.
- Advisories: the pinned golang/vulndb snapshot (`vulndb.json`), report YAML files.
- Toolchain: go1.26.10 (fetched from the Go module proxy into a scratch directory, as in CP5b),
  `GOTOOLCHAIN=local`, `CGO_ENABLED=0`. Recorded in the selection output and every result.

## Candidate order

Candidates are processed in ascending order of `sha256("20261028:" + repo)` (fixed seed), not
in file order, so the order in the file does not favour any application. Processing stops when
five applications are kept; the remaining candidates are listed as `NOT_EVALUATED_QUOTA_FILLED`.

## Application rules (applied in this order; the first failing rule drops the application)

| Rule | Check | Drop status |
|---|---|---|
| A1 | Diversity: neither the GitHub owner nor the `domain` of the candidate equals that of an application already kept | `DIVERSITY_OWNER` / `DIVERSITY_DOMAIN` |
| A2 | The repository answers `git ls-remote` | `REPO_UNREACHABLE` |
| A3 | Pin: the first tag, in descending semantic-version order, of the form `vMAJOR.MINOR.PATCH` (no pre-release, no path prefix) whose tagged commit's committer date is on or before **2025-12-31T23:59:59Z**. At most 60 tags are probed | `NO_TAG_BEFORE_CUTOFF` |
| A4 | A `go.mod` with a `module` line at the repository root at the pinned commit | `NO_ROOT_GO_MOD` |
| A5 | Its `go` directive is not newer than the toolchain (go1.26.10) | `GO_TOO_NEW` |
| A6 | At most 150 `require` entries (direct and indirect): small-to-medium apps that fit in 16 GB for whole-program analysis | `TOO_LARGE` |
| A7 | At least one eligible advisory by the go.mod versions (rules V1-V2) | `NO_ELIGIBLE_ADVISORY` |
| A8 | Load: the tree is extracted with `git archive` (no checkout hooks or filters run), dependencies are downloaded with `go mod download` (module proxy, `GOFLAGS=-mod=readonly`, go.mod and go.sum are never changed), and `go list -e ./...` lists the module | `LOAD_FAILED` |
| A9 | Between 1 and 10 `main` packages that list without errors (10 is the triage default `--max-mains`, so coverage can be complete) | `NO_MAIN` / `TOO_MANY_MAINS` |
| A10 | Every one of those `main` packages builds with `go build -o <temp file>` (`CGO_ENABLED=0`, `GOTOOLCHAIN=local`, `GOPROXY=off`); the binary is deleted, never run | `BUILD_FAILED` |
| A11 | At least one eligible advisory remains when the version is the one selected in the build list (`go list -m`, rule V3) | `NO_ELIGIBLE_ADVISORY_SELECTED` |

An application that passes every rule is `KEPT`.

## Advisory rules (per application)

| Rule | Check |
|---|---|
| V1 | The D1 eligibility rule from CP3 (`eligible_for_d1`): `REVIEWED`, not withdrawn, not the standard library or toolchain, at least one core symbol, at least one GitHub fix commit. The standard library is excluded because its version is the analysis toolchain's, not the application's. The GitHub fix commit is needed because both Mode 1 (fix diff) and Mode 2 (release range) locate the repository through it. |
| V2 | A module entry of the report that has core symbols is required in the app's `go.mod` at a version inside that entry's affected ranges (`introduced <= v < fixed`, vulndb `versions`, `+incompatible` ignored). |
| V3 | The same check with the version selected in the build list (`go list -m <module>` after download). |

## Case choice (per kept application)

Up to **4** advisories: modules are ordered by `sha256("20261028:" + app + ":" + module)`, the
advisories of each module by `sha256("20261028:" + app + ":" + advisory id)`, and advisories are
taken round-robin over the modules (one per module per round) until four are taken. All
`main` packages of A9 are analysed.

The rules do not look at whether the application imports the vulnerable package. That would
anticipate the verdict; it is measured by the triage run instead.

## Known consequences, stated up front

- V1 excludes advisories whose fix links are not GitHub commits, which removes most
  `golang.org/x/...` advisories (their fix links are `go.dev/cl/...`). This is a limitation of
  the pipeline's evidence (it needs a repository), not a choice about the applications.
- A3 pins every application to a release from 2025 or earlier, so its dependencies are likely to
  be inside the range of advisories published in 2026. The applications have probably upgraded
  since; D3 judges the pinned releases, not the current ones.
- Expected outputs are mostly Mode 1 (every selected advisory has a GitHub fix commit); Mode 2
  runs only where the fix evidence is unusable, with BM25 (no dense retriever: Hugging Face is
  blocked in this environment).
