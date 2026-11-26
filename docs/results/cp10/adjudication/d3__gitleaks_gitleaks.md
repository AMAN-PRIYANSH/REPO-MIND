# CP10 adjudication: d3\_\_gitleaks\_gitleaks

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

## gitleaks\_\_GO\-2025\-4020

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2025-4020` DoS risk due to unrestricted RAR dictionary sizes in github\.com/nwaples/rardecode
- vulnerable module: `github.com/nwaples/rardecode/v2@v2.1.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** ANALYSIS\_FAILED
- VulnTrace, legacy targets: **CANT\_DETERMINE** ANALYSIS\_FAILED, METHOD\_DISAGREEMENT, PATHS\_INFEASIBLE
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (2): `github.com/nwaples/rardecode/v2.getOptions`, `github.com/nwaples/rardecode/v2.packedFileReader.newArchiveFileFrom`
Extra evidence only (never decide): `github.com/nwaples/rardecode/v2.BufferSize`, `github.com/nwaples/rardecode/v2.FileSystem`, `github.com/nwaples/rardecode/v2.OpenFSCheck`, `github.com/nwaples/rardecode/v2.osFS.Open`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 6, \('CANT\_DETERMINE', True\): 4, \('NOT\_REACHABLE', False\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
