# D3c selection rules (CP10, held-out set, two strata)

Written and committed **before** any D3c candidate was probed and before any D3c triage result
existed, in the same commit as the candidate list [`d3c_candidates.json`](d3c_candidates.json), its
seed and the selection code (`select_d3c` in `src/vulntrace/d3/select.py`). D3c is the held-out
evidence of CP10: verdict-level accuracy of VulnTrace (CP10 target hygiene and `--legacy-targets`)
against govulncheck, measured against adjudicated truth. D3 (CP7b) and D3b (CP9) are in-sample for
CP10, because the hygiene rules were written after reading their adjudications.

## What is the same as D3 and D3b

Every rule of [D3_SELECTION_RULES.md](D3_SELECTION_RULES.md) applies unchanged and is applied by the
same code: the candidate order by a seeded hash, application rules A1-A11 in the same order (pin
cutoff 2025-12-31T23:59:59Z, at most 150 `require` entries, 1-10 `main` packages, every main
builds), V2/V3 (the version required in go.mod and the version selected in the build list are inside
the advisory's affected range), the per-stratum case choice below is the D3 round-robin over modules
in seeded order, the pinned vulndb snapshot `e0bad56276e9`, toolchain go1.26.10 with
`GOTOOLCHAIN=local`, `CGO_ENABLED=0`, nothing of an application ever executed.

## What is different

| Item | D3 (CP7b) | D3b (CP9) | D3c (CP10) |
|---|---|---|---|
| Candidate list | `d3_candidates.json` (37) | the D3 list minus the 5 D3 apps (32) | `d3c_candidates.json`: the D3 list minus the 8 D3/D3b apps (29), **plus 28 applications added for CP10** (57) |
| Excluded | - | 5 D3 apps | the 8 D3/D3b apps: XTLS/Xray-core, gitleaks/gitleaks, smallstep/cli, sosedoff/pgweb, wagoodman/dive, go-task/task, fatedier/frp, gogs/gogs |
| Seed | 20261028 | 20261117 | **20261126** |
| Advisory index | V1 (curated symbols required) | V1 | **two strata**: S = V1 unchanged and the module entry has curated symbols; N = V1N (below) and the module entry has no curated symbols |
| Cases per application | up to 4 | up to 4 | up to **3 per stratum** (up to 6) |
| Applications kept | 5 | 3 | **at least 4**; more are added, by the same rules and in the same order, until at least 8 S cases and at least 8 N cases are taken; at most 8 applications |
| Diversity rule A1 | among kept D3 apps | among kept D3b apps | among kept D3c apps only |

### Why candidates were added

Of the 29 D3 candidates that remain after the exclusion, 15 were dropped by CP7b or CP9 at the same
pin for reasons the strata do not change (13 `TOO_LARGE`, 1 `TOO_MANY_MAINS`, 1
`NO_TAG_BEFORE_CUTOFF`); the rules are deterministic, so they drop again. 5 were dropped only because
no advisory **with curated symbols** applied (`NO_ELIGIBLE_ADVISORY`; stratum N may now apply), and 9
were never evaluated. At most 14 can pass, too few to be confident of filling two strata of 8. The 28 added applications
are well-known open-source Go applications from the same and some new domains (system-tools,
kubernetes-tools, media, backup, auth-identity), written down from memory without looking at their
size, dependencies or advisories. This is a change of the input list, not of the rules, and it is
reported as a design deviation in the CP10 report.

### Stratum rules

| Rule | Check |
|---|---|
| V1S | Stratum S: the D3 rule V1 unchanged (`eligible_for_d1`: `REVIEWED`, not withdrawn, not the standard library or toolchain, at least one curated symbol, at least one GitHub fix commit) **and** the module entry required by the application has curated symbols. These are exactly the D3/D3b advisories. |
| V1N | Stratum N: `REVIEWED` or `UNREVIEWED`, not withdrawn, not the standard library or toolchain, at least one GitHub fix commit, **and** the module entry required by the application has **no** curated symbols. `UNREVIEWED` reports (imported from GHSA) are allowed because they are the main real-world case without curated symbols; they often list no packages at all, so govulncheck can answer only at module level. |
| V2, V3 | As in D3, per module entry and stratum. |

A case is (application, advisory, module); its stratum is the stratum of that module entry. An
advisory taken in stratum S for an application is not taken again in stratum N for it.

### Case choice (per kept application)

For S and then N: the D3 round-robin (modules ordered by `sha256("20261126:" + app + ":" + module)`,
the advisories of each module by `sha256("20261126:" + app + ":" + advisory id)`, one per module per
round) until 3 are taken or the stratum is empty.

### Stopping

Candidates are processed in seeded order. Before each candidate: if at least 4 applications are
kept and both strata have at least 8 cases, or 8 applications are kept, the remaining candidates
are `NOT_EVALUATED_QUOTA_FILLED`. If the candidates run out first, D3c has fewer cases than the
quotas and the report says so, with the number of candidates tried; no rule is relaxed.

## Run

Every D3c case is triaged twice with the same inputs (filter on, N = 20 examined paths, CP10
evidence stage on): with the CP10 target hygiene and with `--legacy-targets`. govulncheck v1.9.0
runs once per application (source mode, `-scan symbol`, the main packages as roots, `GOPROXY=off`,
the pinned vulndb snapshot as its database). Verdict-level adjudication sheets are prepared for
**every** case; the builder stops at `AWAITING_ADJUDICATION`. Nothing is swapped or re-selected
after any result is seen; the owner may veto an application, which is then not replaced.

## Known consequences, stated up front

- Stratum N may stay below its quota: few applications pin a vulnerable version of a module whose
  advisory has a GitHub fix commit but no curated symbols.
- `UNREVIEWED` advisories have not been checked by the Go security team; their affected ranges and
  fix links can be wrong. That affects both tools equally (govulncheck uses the same snapshot).
- With 4-8 applications, n is small and cases are clustered by application.
