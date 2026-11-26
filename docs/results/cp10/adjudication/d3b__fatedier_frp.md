# CP10 adjudication: d3b\_\_fatedier\_frp

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

## frp\_\_GO\-2026\-5676

- item: truth only \(D3B, in\-sample\)
- advisory: `GO-2026-5676` HTTP/3 QPACK Trailer Expansion Memory Exhaustion in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.53.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** VERIFIER\_REJECTED
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): NOT\_REACHABLE at level MODULE; scored as NOT\_REACHABLE

Decision targets (3): `github.com/quic-go/quic-go/http3.decodeTrailers`, `github.com/quic-go/quic-go/http3.parseTrailers`, `github.com/quic-go/quic-go/http3.parseHeaders`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', True\): 2, \('NOT\_REACHABLE', True\): 4\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## frp\_\_GO\-2025\-4233

- item: truth only \(D3B, in\-sample\)
- advisory: `GO-2025-4233` HTTP/3 QPACK Header Expansion DoS in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.53.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): NOT\_REACHABLE at level MODULE; scored as NOT\_REACHABLE

Decision targets (7): `github.com/quic-go/quic-go/http3.Server.handleRequest`, `github.com/quic-go/quic-go/http3.requestFromHeaders`, `github.com/quic-go/quic-go/http3.parseHeaders`, `github.com/quic-go/quic-go/http3.Server.maxHeaderBytes`, `github.com/quic-go/quic-go/http3.Conn.decodeTrailers`, `github.com/quic-go/quic-go/http3.updateResponseFromHeaders`, `github.com/quic-go/quic-go/http3.RequestStream.ReadResponse`
Extra evidence only (never decide): `github.com/quic-go/quic-go/http3.Server.handleConn`, `github.com/quic-go/quic-go/http3.parseTrailers`, `github.com/quic-go/quic-go/http3.qpackError.Error`, `github.com/quic-go/quic-go/http3.qpackError.Unwrap`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 4, \('NOT\_REACHABLE', False\): 4, \('NOT\_REACHABLE', True\): 14\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
