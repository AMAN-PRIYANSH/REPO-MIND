# CP10 adjudication: d3b\_\_gogs\_gogs

- rule: D3c: every case \(truth; plus the route judgement when the CP10 verdict is REACHABLE\)\. Truth\-only: the D3 \(CP7b\) cases whose verdict was REACHABLE and the D3b \(CP9\) cases whose verdict was not REACHABLE\.

How to adjudicate (the same text for every item):

- Judge **reachability**, never exploitability.
- `truth`: is **any decision target listed for the item** reachable from a `main` package of the application, by any
  route at all (not only the one shown)? `REACHABLE` (give one route in `route`, as `file:line` steps or a short
  description), `NOT_REACHABLE` (none can be called; say why in `note`), or `UNKNOWN` (the code does not settle it, for
  example run-time configuration decides). The decision targets are the CP10 hygiene targets: the advisory's curated
  vulndb symbols (stratum S) or, without them, the functions the fix changed whose own lines changed (stratum N).
- `confidence`: `HIGH` or `LOW`, how sure the `truth` answer is.
- `path_judgement` (only where asked: the CP10 verdict is REACHABLE): the route shown below. `CORRECT` if every step is a
  real call that can run in the application; `INFEASIBLE_PATH` if the calls exist but this route cannot run; `WRONG` if a
  step does not exist or does not call the next function; `CANNOT_JUDGE` otherwise. Steps marked unconfirmed are dynamic
  calls (interface method, function value, closure through a parameter) that the call graph could not confirm.
- `by`: who adjudicated. `note`: one or two sentences.
- Verdicts of VulnTrace (with hygiene and with legacy targets) and of govulncheck are shown for reference; none of them
  is truth. Fill `adjudication.json`; the Markdown files are for reading.

## gogs\_\_GO\-2026\-5543

- item: truth only \(D3B, in\-sample\)
- advisory: `GO-2026-5543` Go\-ntlmssp NTLM challenges can panic on malformed payloads in github\.com/Azure/go\-ntlmssp
- vulnerable module: `github.com/Azure/go-ntlmssp@v0.0.0-20220621081337-cb9428e4ac1e`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (1): `github.com/Azure/go-ntlmssp.ProcessChallenge`
Extra evidence only (never decide): `github.com/Azure/go-ntlmssp.varField.ReadFrom`, `github.com/Azure/go-ntlmssp.varField.ReadStringFrom`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 4, \('NOT\_REACHABLE', True\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
