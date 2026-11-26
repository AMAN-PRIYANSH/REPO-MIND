# CP10 adjudication: d3c\_\_restic\_restic

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

## restic\_\_GO\-2026\-6061

- item: D3c case
- advisory: `GO-2026-6061` Vulnerabilities in the xDS RBAC authorization engine and the HTTP/2 transport server implementation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.74.2`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `google.golang.org/grpc/internal/transport.ClientStream.Close`, `google.golang.org/grpc/internal/transport.ClientStream.Header`, `google.golang.org/grpc/internal/transport.ClientStream.Read`, `google.golang.org/grpc/internal/transport.ClientStream.RecvCompress`, `google.golang.org/grpc/internal/transport.ClientStream.TrailersOnly`, `google.golang.org/grpc/internal/transport.ClientStream.Write`, `google.golang.org/grpc/internal/transport.NewHTTP2Client`, `google.golang.org/grpc/internal/transport.Stream.ReadMessageHeader`, `google.golang.org/grpc/internal/transport.http2Client.Close`, `google.golang.org/grpc/internal/transport.http2Client.GracefulClose`
- govulncheck trace: `github.com/restic/restic/cmd/restic.init (cmd/restic/cmd_backup.go:27) -> github.com/restic/restic/internal/restic.init (internal/restic/backend_find.go:1) -> github.com/restic/restic/internal/restic.init#1 (internal/restic/lock.go:414) -> sync.Once.Do (src/sync/once.go:69) -> sync.Once.doSlow (src/sync/once.go:78) -> sync.OnceFunc$1$1 (src/sync/oncefunc.go:33) -> google.golang.org/grpc/orca.RegisterOOBListener$1 (orca/producer.go:88) -> google.golang.org/grpc/orca.producer.unregisterListener (orca/producer.go:137) -> google.golang.org/grpc/orca.producer.updateRunLocked (orca/producer.go:167) -> google.golang.org/grpc/orca.producer.run (orca/producer.go:197) -> google.golang.org/grpc/internal/backoff.RunF (internal/backoff/backoff.go:97) -> google.golang.org/grpc/orca.run$1 (orca/producer.go:176) -> google.golang.org/grpc/orca.producer.runStream (orca/producer.go:214) -> github.com/cncf/xds/go/xds/service/orca/v3.openRcaServiceStreamCoreMetricsClient.Recv (xds/service/orca/v3/orca_grpc.pb.go:67) -> google.golang.org/grpc.addrConnStream.RecvMsg (stream.go:1476) -> google.golang.org/grpc.recv (rpc_util.go:933) -> google.golang.org/grpc.recvAndDecompress (rpc_util.go:850) -> google.golang.org/grpc.parser.recvMsg (rpc_util.go:690) -> google.golang.org/grpc/internal/transport.Stream.ReadMessageHeader (internal/transport/transport.go:353)`

Decision targets (4): `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut`, `google.golang.org/grpc/internal/transport.controlBuffer.getOnceLocked`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPrincipals`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPermissions`
Extra evidence only (never decide): `google.golang.org/grpc/internal/envconfig.boolFromEnv`, `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.controlBuffer.finish`, `google.golang.org/grpc/internal/transport.dataFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.earlyAbortStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.goAway.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.headerFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.http2Client.NewStream`, `google.golang.org/grpc/internal/transport.http2Client.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Client.handleData`, `google.golang.org/grpc/internal/transport.http2Server.deleteStream`, `google.golang.org/grpc/internal/transport.http2Server.finishStream`, `google.golang.org/grpc/internal/transport.http2Server.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Server.handleData` and 18 more
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 16, \('NOT\_REACHABLE', False\): 64, \('NOT\_REACHABLE', True\): 8, \('REACHABLE', False\): 19, \('REACHABLE', True\): 4\}

### Route shown: `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` from `github.com/restic/restic/cmd/restic`

Evidence level HAS\_DYNAMIC\_STEPS, dynamic steps 4, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/restic/restic/cmd/restic.main` calls `os.Getenv` (STATIC) at `cmd/restic/main.go:159` [source](https://github.com/restic/restic/blob/7d0aa7f2e30546fba7c8f1c0bae4d6704e3d8423/cmd/restic/main.go#L159)

```go
158  
159> 	err := feature.Flag.Apply(os.Getenv("RESTIC_FEATURES"), func(s string) {
160  		_, _ = fmt.Fprintln(os.Stderr, s)
```

2. `os.Getenv` calls `syscall.Getenv` (STATIC) at `$GOROOT/src/os/env.go:103` [source](https://github.com/golang/go/blob/go1.26.10/src/os/env.go#L103)

```go
102  	testlog.Getenv(key)
103> 	v, _ := syscall.Getenv(key)
104  	return v
```

3. `syscall.Getenv` calls `sync.OnceFunc$1` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOROOT/src/syscall/env_unix.go:67` [source](https://github.com/golang/go/blob/go1.26.10/src/syscall/env_unix.go#L67)

```go
66  func Getenv(key string) (value string, found bool) {
67> 	copyenv()
68  	if len(key) == 0 {
```

4. `sync.OnceFunc$1` calls `sync.Once.Do` (STATIC) at `$GOROOT/src/sync/oncefunc.go:22` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/oncefunc.go#L22)

```go
21  	return func() {
22> 		d.once.Do(func() {
23  			defer func() {
```

5. `sync.Once.Do` calls `sync.Once.doSlow` (STATIC) at `$GOROOT/src/sync/once.go:69` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L69)

```go
68  		// Outlined slow-path to allow inlining of the fast-path.
69> 		o.doSlow(f)
70  	}
```

6. `sync.Once.doSlow` calls `sync.OnceFunc$1$1` (DYNAMIC CLOSURE\_VIA\_PARAMETER, **unconfirmed**) at `$GOROOT/src/sync/once.go:78` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/once.go#L78)

```go
77  		defer o.done.Store(true)
78> 		f()
79  	}
```

7. `sync.OnceFunc$1$1` calls `google.golang.org/grpc/xds/internal/clients/grpctransport.Builder.cleanupFunc$1` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOROOT/src/sync/oncefunc.go:33` [source](https://github.com/golang/go/blob/go1.26.10/src/sync/oncefunc.go#L33)

```go
32  			}()
33> 			d.f()
34  			d.valid = true // Set only if f does not panic.
```

8. `google.golang.org/grpc/xds/internal/clients/grpctransport.Builder.cleanupFunc$1` calls `google.golang.org/grpc.ClientConn.Close` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/xds/internal/clients/grpctransport/grpc_transport.go:166`

```go
165  
166> 		tr.cc.Close()
167  		tr.cc = nil
```

9. `google.golang.org/grpc.ClientConn.Close` calls `google.golang.org/grpc.ClientConn.Close$2` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/clientconn.go:1177`

```go
1176  		wg.Add(1)
1177> 		go func(ac *addrConn) {
1178  			defer wg.Done()
```

10. `google.golang.org/grpc.ClientConn.Close$2` calls `google.golang.org/grpc.addrConn.tearDown` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/clientconn.go:1179`

```go
1178  			defer wg.Done()
1179> 			ac.tearDown(ErrClientConnClosing)
1180  		}(ac)
```

11. `google.golang.org/grpc.addrConn.tearDown` calls `google.golang.org/grpc/internal/transport.http2Client.Close` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/clientconn.go:1593`

```go
1592  			// unconditionally here.
1593> 			curTr.Close(err)
1594  		}
```

12. `google.golang.org/grpc/internal/transport.http2Client.Close` calls `google.golang.org/grpc/internal/transport.controlBuffer.put` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/internal/transport/http2_client.go:1025`

```go
1024  	// just stuck.
1025> 	t.controlBuf.put(&goAway{code: http2.ErrCodeNo, debugData: []byte("client transport shutdown"), closeConn: err})
1026  	timer := time.NewTimer(goAwayLoopyWriterTimeout)
```

13. `google.golang.org/grpc/internal/transport.controlBuffer.put` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.74.2/internal/transport/controlbuf.go:354`

```go
353  func (c *controlBuffer) put(it cbItem) error {
354> 	_, err := c.executeAndPut(nil, it)
355  	return err
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |

## restic\_\_GO\-2026\-5506

- item: D3c case
- advisory: `GO-2026-5506` OpenTelemetry\-Go: Multi\-value baggage header extraction causes excessive allocations in go\.opentelemetry\.io/otel
- vulnerable module: `go.opentelemetry.io/otel@v1.36.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`
- govulncheck trace: `github.com/restic/restic/cmd/restic.init (cmd/restic/cmd_backup.go:27) -> github.com/restic/restic/internal/restic.init (internal/restic/backend_find.go:1) -> github.com/restic/restic/internal/restic.init#1 (internal/restic/lock.go:414) -> sync.Once.Do (src/sync/once.go:69) -> sync.Once.doSlow (src/sync/once.go:78) -> cloud.google.com/go/auth/grpctransport.otelGRPCStatsHandler$1 (grpctransport/grpctransport.go:72) -> go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc.NewClientHandler (stats_handler.go:206) -> go.opentelemetry.io/otel.Handle (handler.go:33) -> go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle (internal/global/handler.go:26)`

Decision targets (6): `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.SetErrorHandler`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`, `go.opentelemetry.io/otel/baggage.Parse`, `go.opentelemetry.io/otel/baggage.New`, `go.opentelemetry.io/otel/propagation.Baggage.Extract`
Extra evidence only (never decide): `go.opentelemetry.io/otel/baggage.parseMember`, `go.opentelemetry.io/otel/internal/global.ErrDelegator.setDelegate`, `go.opentelemetry.io/otel/internal/global.SetMeterProvider`, `go.opentelemetry.io/otel/internal/global.defaultErrorHandler`, `go.opentelemetry.io/otel/internal/global.defaultTracerValue`, `go.opentelemetry.io/otel/propagation.extractMultiBaggage`, `go.opentelemetry.io/otel/propagation.extractSingleBaggage`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 19, \('NOT\_REACHABLE', True\): 16, \('REACHABLE', False\): 2, \('REACHABLE', True\): 2\}

### Route shown: `go.opentelemetry.io/otel/internal/global.GetErrorHandler` from `github.com/restic/restic/cmd/restic`

Evidence level STATIC\_PATH, dynamic steps 0, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/restic/restic/cmd/restic.init` calls `github.com/restic/restic/internal/backend/gs.init` (STATIC) (synthetic edge, no call site)
2. `github.com/restic/restic/internal/backend/gs.init` calls `cloud.google.com/go/storage.init` (STATIC) (synthetic edge, no call site)
3. `cloud.google.com/go/storage.init` calls `google.golang.org/api/transport/http.init` (STATIC) (synthetic edge, no call site)
4. `google.golang.org/api/transport/http.init` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.init` (STATIC) (synthetic edge, no call site)
5. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.init` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.NewTransport` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/client.go:17`

```go
16  // the global propagator, the DefaultClient might still be using the old one.
17> var DefaultClient = &http.Client{Transport: NewTransport(http.DefaultTransport)}
18
```

6. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.NewTransport` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.Transport.applyConfig` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/transport.go:63`

```go
62  	c := newConfig(append(defaultOpts, opts...)...)
63> 	t.applyConfig(c)
64
```

7. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp.Transport.applyConfig` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.NewHTTPClient` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/transport.go:75`

```go
74  	t.clientTrace = c.ClientTrace
75> 	t.semconv = semconv.NewHTTPClient(c.Meter)
76  	t.metricAttributesFn = c.MetricAttributesFn
```

8. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.NewHTTPClient` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.CurrentHTTPClient.createMeasures` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/internal/semconv/env.go:217`

```go
216  	}
217> 	client.requestBodySize, client.requestDuration = CurrentHTTPClient{}.createMeasures(meter)
218  	if duplicate {
```

9. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.CurrentHTTPClient.createMeasures` calls `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.handleErr` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/internal/semconv/httpconv.go:486`

```go
485  	)
486> 	handleErr(err)
487
```

10. `go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp/internal/semconv.handleErr` calls `go.opentelemetry.io/otel.Handle` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp@v0.61.0/internal/semconv/util.go:115`

```go
114  	if err != nil {
115> 		otel.Handle(err)
116  	}
```

11. `go.opentelemetry.io/otel.Handle` calls `go.opentelemetry.io/otel/internal/global.GetErrorHandler` (STATIC) at `$GOMODCACHE/go.opentelemetry.io/otel@v1.36.0/handler.go:33`

```go
32  // Handle is a convenience function for GetErrorHandler().Handle(err).
33> func Handle(err error) { global.GetErrorHandler().Handle(err) }
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |

## restic\_\_GO\-2026\-5841

- item: D3c case
- advisory: `GO-2026-5841` OOB read in github\.com/klauspost/compress/s2
- vulnerable module: `github.com/klauspost/compress@v1.18.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (1): `github.com/klauspost/compress/s2.NewDict`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 3\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
