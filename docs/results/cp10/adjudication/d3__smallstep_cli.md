# CP10 adjudication: d3\_\_smallstep\_cli

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

## cli\_\_GO\-2026\-5506

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-5506` OpenTelemetry\-Go: Multi\-value baggage header extraction causes excessive allocations in go\.opentelemetry\.io/otel
- vulnerable module: `go.opentelemetry.io/otel@v1.38.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`
- govulncheck trace: `github.com/smallstep/cli/cmd/step.init (cmd/step/main.go:4) -> github.com/smallstep/certificates/ca.init (ca/ca.go:20) -> github.com/go-chi/chi/v5/middleware.init (middleware/basic_auth.go:1) -> github.com/go-chi/chi/v5/middleware.init#2 (middleware/request_id.go:56) -> strings.Replacer.Replace (src/strings/replace.go:96) -> sync.Once.Do (src/sync/once.go:69) -> sync.Once.doSlow (src/sync/once.go:78) -> cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1 (grpctransport/grpctransport.go:73) -> go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler (stats_handler.go:206) -> go.opentelemetry.io/otel.Handle (handler.go:33) -> go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle (internal/global/handler.go:26)`

Decision targets (6): `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.SetErrorHandler`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`, `go.opentelemetry.io/otel/baggage.Parse`, `go.opentelemetry.io/otel/baggage.New`, `go.opentelemetry.io/otel/propagation.Baggage.Extract`
Extra evidence only (never decide): `go.opentelemetry.io/otel/baggage.parseMember`, `go.opentelemetry.io/otel/internal/global.ErrDelegator.setDelegate`, `go.opentelemetry.io/otel/internal/global.SetMeterProvider`, `go.opentelemetry.io/otel/internal/global.defaultErrorHandler`, `go.opentelemetry.io/otel/internal/global.defaultTracerValue`, `go.opentelemetry.io/otel/propagation.extractMultiBaggage`, `go.opentelemetry.io/otel/propagation.extractSingleBaggage`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 5, \('NOT\_REACHABLE', True\): 4, \('REACHABLE', False\): 2, \('REACHABLE', True\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## cli\_\_GO\-2026\-5052

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-5052` Vulnerability in software\.sslmate\.com/src/go\-pkcs12
- vulnerable module: `software.sslmate.com/src/go-pkcs12@v0.6.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (4): `software.sslmate.com/src/go-pkcs12.Decode`, `software.sslmate.com/src/go-pkcs12.DecodeChain`, `software.sslmate.com/src/go-pkcs12.DecodeTrustStore`, `software.sslmate.com/src/go-pkcs12.ToPEM`
Extra evidence only (never decide): `software.sslmate.com/src/go-pkcs12.doPBMAC1`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 4, \('REACHABLE', False\): 1\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## cli\_\_GO\-2026\-5004

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-5004` SQL Injection via placeholder confusion with dollar quoted string literals in github\.com/jackc/pgx
- vulnerable module: `github.com/jackc/pgx/v5@v5.7.5`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL`
- govulncheck trace: `github.com/smallstep/cli/cmd/step.main (cmd/step/main.go:28) -> github.com/smallstep/cli/internal/cmd.Run (internal/cmd/root.go:47) -> github.com/smallstep/cli/internal/cmd.run (internal/cmd/root.go:62) -> github.com/urfave/cli.App.Run (app.go:286) -> github.com/urfave/cli.HandleAction (app.go:522) -> github.com/smallstep/cli/command/ca/acme/eab.listAction (command/ca/acme/eab/list.go:137) -> os/exec.Cmd.Start (src/os/exec/exec.go:756) -> os/exec.Start$2 (src/os/exec/exec.go:757) -> database/sql.driverConn.finalClose (src/database/sql/sql.go:683) -> database/sql.withLock (src/database/sql/sql.go:3572) -> database/sql.queryDC$1 (src/database/sql/sql.go:1786) -> database/sql.ctxDriverQuery (src/database/sql/ctxutil.go:48) -> github.com/jackc/pgx/v5/stdlib.Conn.QueryContext (stdlib/sql.go:494) -> github.com/jackc/pgx/v5.Conn.Query (conn.go:831) -> github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery (conn.go:1243) -> github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL (internal/sanitize/sanitize.go:433)`

Decision targets (2): `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL`, `github.com/jackc/pgx/v5/internal/sanitize.Query.Sanitize`
Extra evidence only (never decide): `github.com/jackc/pgx/v5/internal/sanitize.QuoteBytes`, `github.com/jackc/pgx/v5/internal/sanitize.escapeStringState`, `github.com/jackc/pgx/v5/internal/sanitize.placeholderState`, `github.com/jackc/pgx/v5/internal/sanitize.rawState`
Per-entry results (result, deciding): \{\('REACHABLE', False\): 4, \('REACHABLE', True\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
