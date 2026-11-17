# D3b selection rules (CP9, held-out set)

Written and committed **before** any D3b candidate was probed and before any D3b triage result
existed. D3b is the held-out test of the CP9 path-feasibility filter: the filter's patterns were
designed from the D3 (CP7b) cases, so D3 is in-sample and only D3b counts as evidence.

## What is the same as D3

Every rule of [D3_SELECTION_RULES.md](D3_SELECTION_RULES.md) applies unchanged and is applied by the
same code (`python -m vulntrace d3 select`, `src/vulntrace/d3/select.py`): the candidate order by a
seeded hash, application rules A1-A11 in the same order (same pin cutoff 2025-12-31T23:59:59Z, at
most 150 `require` entries, 1-10 `main` packages, every main builds), advisory rules V1-V3 on the
same pinned vulndb snapshot, the case choice (up to 4 advisories per application, round-robin over
modules in seeded order), toolchain go1.26.10 with `GOTOOLCHAIN=local`, `CGO_ENABLED=0`.

## What is different

| Item | D3 (CP7b) | D3b (CP9) |
|---|---|---|
| Candidate list | `d3_candidates.json` (37) | `d3b_candidates.json`: the same list minus the five D3 applications (32) |
| Excluded | - | github.com/XTLS/Xray-core, github.com/gitleaks/gitleaks, github.com/smallstep/cli, github.com/sosedoff/pgweb, github.com/wagoodman/dive |
| Seed | 20261028 | **20261117** |
| Applications kept | 5 | **3** (as the CP9 specification asks) |
| Diversity rule A1 | among the kept D3 applications | among the kept D3b applications only (the D3 applications are excluded outright) |

## Run

Triage runs twice on every D3b case with the same inputs: without the filter (`--no-feasibility`,
the CP7b pipeline) and with it (N = 20 examined paths). Adjudication sheets in the CP7b format are
prepared for every case that is REACHABLE in either run, and the builder stops at
`AWAITING_ADJUDICATION`. The supervisor adjudicates with the CP7b method. Nothing is swapped or
re-selected after any result is seen; the owner may veto an application, which is then not
replaced.

## Known consequences, stated up front

- Many of the remaining candidates were dropped in CP7b as `TOO_LARGE` (rule A6), and the
  dropped ones will be dropped again; if fewer than three applications pass, D3b has fewer than
  three applications and the report says so. No rule is relaxed to fill the quota.
- With three applications, D3b's n is small and its cases are clustered by application.
