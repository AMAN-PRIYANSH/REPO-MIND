# Adjudication: github\.com/smallstep/cli

- application: `github.com/smallstep/cli` at tag `v0.29.0`, commit `1d193897bb723c1c621c30d6803ed4d7561c94a2`
- cases: 4; to adjudicate: 4
- sample rule: All REACHABLE cases\. Of NOT\_REACHABLE and of CANT\_DETERMINE cases: all if there are at most 5, otherwise 5 in ascending order of sha256\("20261028:" \+ case id\)\.
- main packages analysed: `github.com/smallstep/cli/cmd/step`

How to adjudicate (the same text for every case):

- Judge the **reachability claim**, not exploitability. `REACHABLE` means a call path from a `main` package to the
  target function exists in the call graph.
- `adjudication` is one of `CORRECT`, `INFEASIBLE_PATH`, `WRONG`, `CANNOT_JUDGE`.
  - `REACHABLE`: `CORRECT` if every step of the path below is a real call that can run in the application;
    `INFEASIBLE_PATH` if the calls exist but the path cannot run (for example a dynamic call that never takes this
    target, or code behind a condition that is never true); `WRONG` if a step does not exist or does not call the next
    function; `CANNOT_JUDGE` otherwise. If the case has more than one reachable target, judge the first path shown.
  - `NOT_REACHABLE`: `CORRECT` if, reading the code, none of the listed targets can be called from the application's
    `main` packages; `WRONG` if one can (a false NOT_REACHABLE: please say which in `note`).
  - `CANT_DETERMINE`: `CORRECT` if abstaining is reasonable (the answer is not clear from the code either); `WRONG`
    if reading the code gives a clear answer.
- `truth` (optional, NOT_REACHABLE and CANT_DETERMINE only): `REACHABLE`, `NOT_REACHABLE` or `UNKNOWN`, what reading
  the code says.
- `by`: who adjudicated (for example `owner` or `supervisor`). `note`: one or two sentences.
- Fill `adjudication.json`; the Markdown files are for reading. govulncheck is shown as a reference, not as truth.

## cli\_\_GO\-2026\-5506

- advisory: `GO-2026-5506` OpenTelemetry\-Go: Multi\-value baggage header extraction causes excessive allocations in go\.opentelemetry\.io/otel
- vulnerable module: `go.opentelemetry.io/otel@v1.38.0`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 12
- per-symbol results: \{'NOT\_REACHABLE': 8, 'REACHABLE': 4\}
- verifier: PASSED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): REACHABLE \(finding level SYMBOL\) via `github.com/smallstep/cli/cmd/step.init (cmd/step/main.go:4) -> github.com/smallstep/certificates/ca.init (ca/ca.go:20) -> github.com/go-chi/chi/v5/middleware.init (middleware/basic_auth.go:1) -> github.com/go-chi/chi/v5/middleware.init#2 (middleware/request_id.go:56) -> strings.Replacer.Replace (src/strings/replace.go:96) -> sync.Once.Do (src/sync/once.go:69) -> sync.Once.doSlow (src/sync/once.go:78) -> cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1 (grpctransport/grpctransport.go:73) -> go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler (stats_handler.go:206) -> go.opentelemetry.io/otel.Handle (handler.go:33) -> go.opentelemetry.io/otel/internal/global.GetErrorHandler (internal/global/state.go:55)`

Reachable targets (4): `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`, `go.opentelemetry.io/otel/internal/global.defaultErrorHandler`, `go.opentelemetry.io/otel/internal/global.defaultTracerValue` (context only)

### Path 1: `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.init` calls `github.com/smallstep/certificates/ca.init` (STATIC) (synthetic edge, no call site)
2. `github.com/smallstep/certificates/ca.init` calls `crypto/tls.init` (STATIC) (synthetic edge, no call site)
3. `crypto/tls.init` calls `crypto/fips140.init` (STATIC) (synthetic edge, no call site)
4. `crypto/fips140.init` calls `internal/godebug.Setting.Value` (STATIC) at `$GOROOT/src/crypto/fips140/enforcement.go:31` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/fips140/enforcement.go#L31)

```go
30  
31> var enabled = godebug.New("fips140").Value() == "only"
32
```

5. `internal/godebug.Setting.Value` calls `sync.Once.Do` (STATIC) at `$GOROOT/src/internal/godebug/godebug.go:158` [source](https://github.com/golang/go/blob/go1.26.10/src/internal/godebug/godebug.go#L158)

```go
157  func (s *Setting) Value() string {
158> 	s.once.Do(func() {
159  		s.setting = lookup(s.Name())
```

6. `sync.Once.Do` calls `sync.Once.doSlow` (STATIC) at `$GOROOT/src/sync/once.go:69` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L69)

```go
68  		// Outlined slow-path to allow inlining of the fast-path.
69> 		o.doSlow(f)
70  	}
```

7. `sync.Once.doSlow` calls `cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1` (DYNAMIC) at `$GOROOT/src/sync/once.go:78` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L78)

```go
77  		defer o.done.Store(true)
78> 		f()
79  	}
```

8. `cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1` calls `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler` (STATIC) at `$GOMODCACHE/cloud.google.com/go/auth@v0.17.0/grpctransport/grpctransport.go:73`

```go
72  	initOtelStatsHandlerOnce.Do(func() {
73> 		otelStatsHandler = otelgrpc.NewClientHandler()
74  	})
```

9. `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler` calls `go.opentelemetry.io/otel.Handle` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc@v0.61.0/stats_handler.go:206`

```go
205  	if err != nil {
206> 		otel.Handle(err)
207  		if h.duration == nil {
```

10. `go.opentelemetry.io/otel.Handle` calls `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle` (DYNAMIC) at `$GOMODCACHE/go.opentelemetry.io/otel@v1.38.0/handler.go:33`

```go
32  // Handle is a convenience function for GetErrorHandler().Handle(err).
33> func Handle(err error) { global.GetErrorHandler().Handle(err) }
```


### Path 2: `go.opentelemetry.io/otel/internal/global.GetErrorHandler` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.init` calls `github.com/smallstep/certificates/ca.init` (STATIC) (synthetic edge, no call site)
2. `github.com/smallstep/certificates/ca.init` calls `crypto/tls.init` (STATIC) (synthetic edge, no call site)
3. `crypto/tls.init` calls `crypto/fips140.init` (STATIC) (synthetic edge, no call site)
4. `crypto/fips140.init` calls `internal/godebug.Setting.Value` (STATIC) at `$GOROOT/src/crypto/fips140/enforcement.go:31` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/fips140/enforcement.go#L31)

```go
30  
31> var enabled = godebug.New("fips140").Value() == "only"
32
```

5. `internal/godebug.Setting.Value` calls `sync.Once.Do` (STATIC) at `$GOROOT/src/internal/godebug/godebug.go:158` [source](https://github.com/golang/go/blob/go1.26.10/src/internal/godebug/godebug.go#L158)

```go
157  func (s *Setting) Value() string {
158> 	s.once.Do(func() {
159  		s.setting = lookup(s.Name())
```

6. `sync.Once.Do` calls `sync.Once.doSlow` (STATIC) at `$GOROOT/src/sync/once.go:69` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L69)

```go
68  		// Outlined slow-path to allow inlining of the fast-path.
69> 		o.doSlow(f)
70  	}
```

7. `sync.Once.doSlow` calls `cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1` (DYNAMIC) at `$GOROOT/src/sync/once.go:78` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L78)

```go
77  		defer o.done.Store(true)
78> 		f()
79  	}
```

8. `cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1` calls `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler` (STATIC) at `$GOMODCACHE/cloud.google.com/go/auth@v0.17.0/grpctransport/grpctransport.go:73`

```go
72  	initOtelStatsHandlerOnce.Do(func() {
73> 		otelStatsHandler = otelgrpc.NewClientHandler()
74  	})
```

9. `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler` calls `go.opentelemetry.io/otel.Handle` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc@v0.61.0/stats_handler.go:206`

```go
205  	if err != nil {
206> 		otel.Handle(err)
207  		if h.duration == nil {
```

10. `go.opentelemetry.io/otel.Handle` calls `go.opentelemetry.io/otel/internal/global.GetErrorHandler` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/otel@v1.38.0/handler.go:33`

```go
32  // Handle is a convenience function for GetErrorHandler().Handle(err).
33> func Handle(err error) { global.GetErrorHandler().Handle(err) }
```


### Path 3: `go.opentelemetry.io/otel/internal/global.defaultErrorHandler` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.init` calls `github.com/smallstep/cli/internal/cmd.init` (STATIC) (synthetic edge, no call site)
2. `github.com/smallstep/cli/internal/cmd.init` calls `github.com/smallstep/certificates/cas/cloudcas.init` (STATIC) (synthetic edge, no call site)
3. `github.com/smallstep/certificates/cas/cloudcas.init` calls `cloud.google.com/go/security/privateca/apiv1.init` (STATIC) (synthetic edge, no call site)
4. `cloud.google.com/go/security/privateca/apiv1.init` calls `google.golang.org/api/transport/grpc.init` (STATIC) (synthetic edge, no call site)
5. `google.golang.org/api/transport/grpc.init` calls `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.init` (STATIC) (synthetic edge, no call site)
6. `go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.init` calls `go.opentelemetry.io/otel.init` (STATIC) (synthetic edge, no call site)
7. `go.opentelemetry.io/otel.init` calls `go.opentelemetry.io/otel/internal/global.init` (STATIC) (synthetic edge, no call site)
8. `go.opentelemetry.io/otel/internal/global.init` calls `go.opentelemetry.io/otel/internal/global.defaultErrorHandler` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/otel@v1.38.0/internal/global/state.go:35`

```go
34  var (
35> 	globalErrorHandler  = defaultErrorHandler()
36  	globalTracer        = defaultTracerValue()
```


1 more reachable target(s); see the verdict file.

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |

## cli\_\_GO\-2026\-5052

- advisory: `GO-2026-5052` Vulnerability in software\.sslmate\.com/src/go\-pkcs12
- vulnerable module: `software.sslmate.com/src/go-pkcs12@v0.6.0`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'REACHABLE': 1\}
- verifier: PASSED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Reachable targets (1): `software.sslmate.com/src/go-pkcs12.doPBMAC1`

### Path 1: `software.sslmate.com/src/go-pkcs12.doPBMAC1` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.main` calls `github.com/smallstep/cli/internal/cmd.Run` (STATIC) at `cmd/step/main.go:28` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/cmd/step/main.go#L28)

```go
27  func main() {
28> 	cmd.Run()
29  }
```

2. `github.com/smallstep/cli/internal/cmd.Run` calls `github.com/smallstep/cli/internal/cmd.run` (STATIC) at `internal/cmd/root.go:47` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L47)

```go
46  func Run() {
47> 	os.Exit(run())
48  }
```

3. `github.com/smallstep/cli/internal/cmd.run` calls `github.com/urfave/cli.App.Run` (STATIC) at `internal/cmd/root.go:62` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L62)

```go
61  
62> 	if err := app.Run(os.Args); err != nil {
63  		var messenger interface {
```

4. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

5. `github.com/urfave/cli.HandleAction` calls `github.com/smallstep/cli-utils/command.ActionFunc$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

6. `github.com/smallstep/cli-utils/command.ActionFunc$1` calls `github.com/smallstep/cli/command/certificate.p12Action` (DYNAMIC) at `$GOMODCACHE/github.com/smallstep/cli-utils@v0.12.2/command/command.go:38` [source](https://github.com/smallstep/cli-utils/blob/v0.12.2/command/command.go#L38)

```go
37  		currentContext = ctx
38> 		return fn(ctx)
39  	}
```

7. `github.com/smallstep/cli/command/certificate.p12Action` calls `software.sslmate.com/src/go-pkcs12.Encoder.Encode` (STATIC) at `command/certificate/p12.go:173` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/command/certificate/p12.go#L173)

```go
172  
173> 		pkcs12Data, err = encoder.Encode(key, x509Cert, x509CAs, password)
174  		if err != nil {
```

8. `software.sslmate.com/src/go-pkcs12.Encoder.Encode` calls `software.sslmate.com/src/go-pkcs12.computeMac` (STATIC) at `$GOMODCACHE/software.sslmate.com/src/go-pkcs12@v0.6.0/pkcs12.go:709`

```go
708  		pfx.MacData.Iterations = enc.macIterations
709> 		if err = computeMac(&pfx.MacData, authenticatedSafeBytes, encodedPassword); err != nil {
710  			return nil, err
```

9. `software.sslmate.com/src/go-pkcs12.computeMac` calls `software.sslmate.com/src/go-pkcs12.doMac` (STATIC) at `$GOMODCACHE/software.sslmate.com/src/go-pkcs12@v0.6.0/mac.go:163`

```go
162  func computeMac(macData *macData, message, password []byte) error {
163> 	digest, err := doMac(macData, message, password)
164  	if err != nil {
```

10. `software.sslmate.com/src/go-pkcs12.doMac` calls `software.sslmate.com/src/go-pkcs12.doPBMAC1` (STATIC) at `$GOMODCACHE/software.sslmate.com/src/go-pkcs12@v0.6.0/mac.go:127`

```go
126  		utf8Password := []byte(originalPassword)
127> 		return doPBMAC1(macData.Mac.Algorithm, message, utf8Password)
128  	}
```


| field | value |
|---|---|
| adjudication | |
| by | |
| note | |

## cli\_\_GO\-2026\-4503

- advisory: `GO-2026-4503` Invalid result or undefined behavior in filippo\.io/edwards25519
- vulnerable module: `filippo.io/edwards25519@v1.1.0`
- verdict: **NOT\_REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'NOT\_REACHABLE': 1\}
- verifier: PASSED
- adjudicate: all 4 NOT\_REACHABLE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Targets analysed (1): `filippo.io/edwards25519.Point.MultiScalarMult`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 1 |

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |

## cli\_\_GO\-2026\-5004

- advisory: `GO-2026-5004` SQL Injection via placeholder confusion with dollar quoted string literals in github\.com/jackc/pgx
- vulnerable module: `github.com/jackc/pgx/v5@v5.7.5`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 4
- per-symbol results: \{'REACHABLE': 4\}
- verifier: PASSED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): REACHABLE \(finding level SYMBOL\) via `github.com/smallstep/cli/cmd/step.main (cmd/step/main.go:28) -> github.com/smallstep/cli/internal/cmd.Run (internal/cmd/root.go:47) -> github.com/smallstep/cli/internal/cmd.run (internal/cmd/root.go:62) -> github.com/urfave/cli.App.Run (app.go:286) -> github.com/urfave/cli.HandleAction (app.go:522) -> github.com/smallstep/cli/command/ca/acme/eab.listAction (command/ca/acme/eab/list.go:137) -> os/exec.Cmd.Start (src/os/exec/exec.go:756) -> os/exec.Start$2 (src/os/exec/exec.go:757) -> database/sql.driverConn.finalClose (src/database/sql/sql.go:683) -> database/sql.withLock (src/database/sql/sql.go:3572) -> database/sql.queryDC$1 (src/database/sql/sql.go:1786) -> database/sql.ctxDriverQuery (src/database/sql/ctxutil.go:48) -> github.com/jackc/pgx/v5/stdlib.Conn.QueryContext (stdlib/sql.go:494) -> github.com/jackc/pgx/v5.Conn.Query (conn.go:831) -> github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery (conn.go:1243) -> github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL (internal/sanitize/sanitize.go:433)`

Reachable targets (4): `github.com/jackc/pgx/v5/internal/sanitize.placeholderState`, `github.com/jackc/pgx/v5/internal/sanitize.rawState`, `github.com/jackc/pgx/v5/internal/sanitize.QuoteBytes` (context only), `github.com/jackc/pgx/v5/internal/sanitize.escapeStringState` (context only)

### Path 1: `github.com/jackc/pgx/v5/internal/sanitize.placeholderState` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.main` calls `github.com/smallstep/cli/internal/cmd.Run` (STATIC) at `cmd/step/main.go:28` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/cmd/step/main.go#L28)

```go
27  func main() {
28> 	cmd.Run()
29  }
```

2. `github.com/smallstep/cli/internal/cmd.Run` calls `github.com/smallstep/cli/internal/cmd.run` (STATIC) at `internal/cmd/root.go:47` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L47)

```go
46  func Run() {
47> 	os.Exit(run())
48  }
```

3. `github.com/smallstep/cli/internal/cmd.run` calls `github.com/urfave/cli.App.Run` (STATIC) at `internal/cmd/root.go:62` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L62)

```go
61  
62> 	if err := app.Run(os.Args); err != nil {
63  		var messenger interface {
```

4. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

5. `github.com/urfave/cli.HandleAction` calls `github.com/smallstep/cli/command/ca.initAction` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

6. `github.com/smallstep/cli/command/ca.initAction` calls `github.com/smallstep/certificates/pki.PKI.Save` (STATIC) at `command/ca/init.go:717` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/command/ca/init.go#L717)

```go
716  	}
717> 	return p.Save()
718  }
```

7. `github.com/smallstep/certificates/pki.PKI.Save` calls `github.com/smallstep/certificates/pki.PKI.GenerateConfig` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:984` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L984)

```go
983  	if !p.options.pkiOnly {
984> 		cfg, err := p.GenerateConfig(opt...)
985  		if err != nil {
```

8. `github.com/smallstep/certificates/pki.PKI.GenerateConfig` calls `github.com/smallstep/certificates/db.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:927` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L927)

```go
926  			// a single place and ensure it happens only once.
927> 			_db, err := db.New(cfg.DB)
928  			if err != nil {
```

9. `github.com/smallstep/certificates/db.New` calls `github.com/smallstep/nosql.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/db/db.go:126` [source](https://github.com/smallstep/certificates/blob/v0.29.0/db/db.go#L126)

```go
125  
126> 	db, err := nosql.New(c.Type, c.DataSource, opts...)
127  	if err != nil {
```

10. `github.com/smallstep/nosql.New` calls `github.com/smallstep/nosql/postgresql.DB.Open` (DYNAMIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/nosql.go:78` [source](https://github.com/smallstep/nosql/blob/v0.7.0/nosql.go#L78)

```go
77  	}
78> 	err = db.Open(dataSourceName, opt...)
79  	return
```

11. `github.com/smallstep/nosql/postgresql.DB.Open` calls `github.com/smallstep/nosql/postgresql.createDatabase` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:85` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L85)

```go
84  		// The database does not exist. Create it.
85> 		err = createDatabase(config)
86  		if err != nil {
```

12. `github.com/smallstep/nosql/postgresql.createDatabase` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:51` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L51)

```go
50  
51> 	_, err = conn.Exec(context.Background(), fmt.Sprintf("CREATE DATABASE %s", quoteIdentifier(db)))
52  	if err != nil {
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:466` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L466)

```go
465  
466> 	commandTag, err := c.exec(ctx, sql, arguments...)
467
```

14. `github.com/jackc/pgx/v5.Conn.exec` calls `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:547` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L547)

```go
546  	case QueryExecModeSimpleProtocol:
547> 		return c.execSimpleProtocol(ctx, sql, arguments)
548  	default:
```

15. `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` calls `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:555` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L555)

```go
554  	if len(arguments) > 0 {
555> 		sql, err = c.sanitizeForSimpleQuery(sql, arguments...)
556  		if err != nil {
```

16. `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:1243` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L1243)

```go
1242  
1243> 	return sanitize.SanitizeSQL(sql, valueArgs...)
1244  }
```

17. `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` calls `github.com/jackc/pgx/v5/internal/sanitize.Query.init` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:435` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L435)

```go
434  	query := queryPool.get()
435> 	query.init(sql)
436  	defer queryPool.put(query)
```

18. `github.com/jackc/pgx/v5/internal/sanitize.Query.init` calls `github.com/jackc/pgx/v5/internal/sanitize.placeholderState` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:141` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L141)

```go
140  	for l.stateFn != nil {
141> 		l.stateFn = l.stateFn(l)
142  	}
```


### Path 2: `github.com/jackc/pgx/v5/internal/sanitize.rawState` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/smallstep/cli/cmd/step.main` calls `github.com/smallstep/cli/internal/cmd.Run` (STATIC) at `cmd/step/main.go:28` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/cmd/step/main.go#L28)

```go
27  func main() {
28> 	cmd.Run()
29  }
```

2. `github.com/smallstep/cli/internal/cmd.Run` calls `github.com/smallstep/cli/internal/cmd.run` (STATIC) at `internal/cmd/root.go:47` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L47)

```go
46  func Run() {
47> 	os.Exit(run())
48  }
```

3. `github.com/smallstep/cli/internal/cmd.run` calls `github.com/urfave/cli.App.Run` (STATIC) at `internal/cmd/root.go:62` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L62)

```go
61  
62> 	if err := app.Run(os.Args); err != nil {
63  		var messenger interface {
```

4. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

5. `github.com/urfave/cli.HandleAction` calls `github.com/smallstep/cli/command/ca.initAction` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

6. `github.com/smallstep/cli/command/ca.initAction` calls `github.com/smallstep/certificates/pki.PKI.Save` (STATIC) at `command/ca/init.go:717` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/command/ca/init.go#L717)

```go
716  	}
717> 	return p.Save()
718  }
```

7. `github.com/smallstep/certificates/pki.PKI.Save` calls `github.com/smallstep/certificates/pki.PKI.GenerateConfig` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:984` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L984)

```go
983  	if !p.options.pkiOnly {
984> 		cfg, err := p.GenerateConfig(opt...)
985  		if err != nil {
```

8. `github.com/smallstep/certificates/pki.PKI.GenerateConfig` calls `github.com/smallstep/certificates/db.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:927` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L927)

```go
926  			// a single place and ensure it happens only once.
927> 			_db, err := db.New(cfg.DB)
928  			if err != nil {
```

9. `github.com/smallstep/certificates/db.New` calls `github.com/smallstep/nosql.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/db/db.go:126` [source](https://github.com/smallstep/certificates/blob/v0.29.0/db/db.go#L126)

```go
125  
126> 	db, err := nosql.New(c.Type, c.DataSource, opts...)
127  	if err != nil {
```

10. `github.com/smallstep/nosql.New` calls `github.com/smallstep/nosql/postgresql.DB.Open` (DYNAMIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/nosql.go:78` [source](https://github.com/smallstep/nosql/blob/v0.7.0/nosql.go#L78)

```go
77  	}
78> 	err = db.Open(dataSourceName, opt...)
79  	return
```

11. `github.com/smallstep/nosql/postgresql.DB.Open` calls `github.com/smallstep/nosql/postgresql.createDatabase` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:85` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L85)

```go
84  		// The database does not exist. Create it.
85> 		err = createDatabase(config)
86  		if err != nil {
```

12. `github.com/smallstep/nosql/postgresql.createDatabase` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:51` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L51)

```go
50  
51> 	_, err = conn.Exec(context.Background(), fmt.Sprintf("CREATE DATABASE %s", quoteIdentifier(db)))
52  	if err != nil {
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:466` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L466)

```go
465  
466> 	commandTag, err := c.exec(ctx, sql, arguments...)
467
```

14. `github.com/jackc/pgx/v5.Conn.exec` calls `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:547` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L547)

```go
546  	case QueryExecModeSimpleProtocol:
547> 		return c.execSimpleProtocol(ctx, sql, arguments)
548  	default:
```

15. `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` calls `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:555` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L555)

```go
554  	if len(arguments) > 0 {
555> 		sql, err = c.sanitizeForSimpleQuery(sql, arguments...)
556  		if err != nil {
```

16. `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:1243` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L1243)

```go
1242  
1243> 	return sanitize.SanitizeSQL(sql, valueArgs...)
1244  }
```

17. `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` calls `github.com/jackc/pgx/v5/internal/sanitize.Query.init` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:435` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L435)

```go
434  	query := queryPool.get()
435> 	query.init(sql)
436  	defer queryPool.put(query)
```

18. `github.com/jackc/pgx/v5/internal/sanitize.Query.init` calls `github.com/jackc/pgx/v5/internal/sanitize.rawState` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:141` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L141)

```go
140  	for l.stateFn != nil {
141> 		l.stateFn = l.stateFn(l)
142  	}
```


### Path 3: `github.com/jackc/pgx/v5/internal/sanitize.QuoteBytes` from `github.com/smallstep/cli/cmd/step`

Target context only (no line of it changed in the fix, it touched diff context): True

1. `github.com/smallstep/cli/cmd/step.main` calls `github.com/smallstep/cli/internal/cmd.Run` (STATIC) at `cmd/step/main.go:28` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/cmd/step/main.go#L28)

```go
27  func main() {
28> 	cmd.Run()
29  }
```

2. `github.com/smallstep/cli/internal/cmd.Run` calls `github.com/smallstep/cli/internal/cmd.run` (STATIC) at `internal/cmd/root.go:47` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L47)

```go
46  func Run() {
47> 	os.Exit(run())
48  }
```

3. `github.com/smallstep/cli/internal/cmd.run` calls `github.com/urfave/cli.App.Run` (STATIC) at `internal/cmd/root.go:62` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/internal/cmd/root.go#L62)

```go
61  
62> 	if err := app.Run(os.Args); err != nil {
63  		var messenger interface {
```

4. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

5. `github.com/urfave/cli.HandleAction` calls `github.com/smallstep/cli/command/ca.initAction` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.17/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.17/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

6. `github.com/smallstep/cli/command/ca.initAction` calls `github.com/smallstep/certificates/pki.PKI.Save` (STATIC) at `command/ca/init.go:717` [source](https://github.com/smallstep/cli/blob/1d193897bb723c1c621c30d6803ed4d7561c94a2/command/ca/init.go#L717)

```go
716  	}
717> 	return p.Save()
718  }
```

7. `github.com/smallstep/certificates/pki.PKI.Save` calls `github.com/smallstep/certificates/pki.PKI.GenerateConfig` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:984` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L984)

```go
983  	if !p.options.pkiOnly {
984> 		cfg, err := p.GenerateConfig(opt...)
985  		if err != nil {
```

8. `github.com/smallstep/certificates/pki.PKI.GenerateConfig` calls `github.com/smallstep/certificates/db.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/pki/pki.go:927` [source](https://github.com/smallstep/certificates/blob/v0.29.0/pki/pki.go#L927)

```go
926  			// a single place and ensure it happens only once.
927> 			_db, err := db.New(cfg.DB)
928  			if err != nil {
```

9. `github.com/smallstep/certificates/db.New` calls `github.com/smallstep/nosql.New` (STATIC) at `$GOMODCACHE/github.com/smallstep/certificates@v0.29.0/db/db.go:126` [source](https://github.com/smallstep/certificates/blob/v0.29.0/db/db.go#L126)

```go
125  
126> 	db, err := nosql.New(c.Type, c.DataSource, opts...)
127  	if err != nil {
```

10. `github.com/smallstep/nosql.New` calls `github.com/smallstep/nosql/postgresql.DB.Open` (DYNAMIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/nosql.go:78` [source](https://github.com/smallstep/nosql/blob/v0.7.0/nosql.go#L78)

```go
77  	}
78> 	err = db.Open(dataSourceName, opt...)
79  	return
```

11. `github.com/smallstep/nosql/postgresql.DB.Open` calls `github.com/smallstep/nosql/postgresql.createDatabase` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:85` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L85)

```go
84  		// The database does not exist. Create it.
85> 		err = createDatabase(config)
86  		if err != nil {
```

12. `github.com/smallstep/nosql/postgresql.createDatabase` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/smallstep/nosql@v0.7.0/postgresql/postgresql.go:51` [source](https://github.com/smallstep/nosql/blob/v0.7.0/postgresql/postgresql.go#L51)

```go
50  
51> 	_, err = conn.Exec(context.Background(), fmt.Sprintf("CREATE DATABASE %s", quoteIdentifier(db)))
52  	if err != nil {
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:466` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L466)

```go
465  
466> 	commandTag, err := c.exec(ctx, sql, arguments...)
467
```

14. `github.com/jackc/pgx/v5.Conn.exec` calls `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:547` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L547)

```go
546  	case QueryExecModeSimpleProtocol:
547> 		return c.execSimpleProtocol(ctx, sql, arguments)
548  	default:
```

15. `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` calls `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:555` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L555)

```go
554  	if len(arguments) > 0 {
555> 		sql, err = c.sanitizeForSimpleQuery(sql, arguments...)
556  		if err != nil {
```

16. `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/conn.go:1243` [source](https://github.com/jackc/pgx/blob/v5.7.5/conn.go#L1243)

```go
1242  
1243> 	return sanitize.SanitizeSQL(sql, valueArgs...)
1244  }
```

17. `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` calls `github.com/jackc/pgx/v5/internal/sanitize.Query.Sanitize` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:438` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L438)

```go
437  
438> 	return query.Sanitize(args...)
439  }
```

18. `github.com/jackc/pgx/v5/internal/sanitize.Query.Sanitize` calls `github.com/jackc/pgx/v5/internal/sanitize.QuoteBytes` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.7.5/internal/sanitize/sanitize.go:79` [source](https://github.com/jackc/pgx/blob/v5.7.5/internal/sanitize/sanitize.go#L79)

```go
78  			case []byte:
79> 				p = QuoteBytes(buf.AvailableBuffer(), arg)
80  			case string:
```


1 more reachable target(s); see the verdict file.

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
