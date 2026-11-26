# CP10 adjudication: d3c\_\_AdguardTeam\_AdGuardHome

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

## AdGuardHome\_\_GO\-2026\-6061

- item: D3c case
- advisory: `GO-2026-6061` Vulnerabilities in the xDS RBAC authorization engine and the HTTP/2 transport server implementation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.77.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): NOT\_AFFECTED at level NONE; scored as NOT\_REACHABLE

Decision targets (4): `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut`, `google.golang.org/grpc/internal/transport.controlBuffer.getOnceLocked`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPrincipals`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPermissions`
Extra evidence only (never decide): `google.golang.org/grpc/internal/envconfig.boolFromEnv`, `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.controlBuffer.finish`, `google.golang.org/grpc/internal/transport.dataFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.earlyAbortStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.goAway.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.headerFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.http2Client.NewStream`, `google.golang.org/grpc/internal/transport.http2Client.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Client.handleData`, `google.golang.org/grpc/internal/transport.http2Server.deleteStream`, `google.golang.org/grpc/internal/transport.http2Server.finishStream`, `google.golang.org/grpc/internal/transport.http2Server.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Server.handleData` and 18 more
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 4, \('NOT\_REACHABLE', False\): 128, \('NOT\_REACHABLE', True\): 16\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## AdGuardHome\_\_GO\-2026\-5676

- item: D3c case
- advisory: `GO-2026-5676` HTTP/3 QPACK Trailer Expansion Memory Exhaustion in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.57.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/quic-go/quic-go/http3.ConfigureTLSConfig`, `github.com/quic-go/quic-go/http3.Error.Error`, `github.com/quic-go/quic-go/http3.RequestStream.Write`, `github.com/quic-go/quic-go/http3.Server.Close`, `github.com/quic-go/quic-go/http3.Server.ListenAndServe`, `github.com/quic-go/quic-go/http3.Server.ServeListener`, `github.com/quic-go/quic-go/http3.Transport.Close`, `github.com/quic-go/quic-go/http3.Transport.RoundTrip`, `github.com/quic-go/quic-go/http3.Transport.RoundTripOpt`, `github.com/quic-go/quic-go/http3.body.Close`
- govulncheck trace: `github.com/AdguardTeam/AdGuardHome/scripts/translations.main (scripts/translations/main.go:97) -> github.com/AdguardTeam/AdGuardHome/scripts/translations.twoskyClient.upload (scripts/translations/upload.go:34) -> github.com/AdguardTeam/AdGuardHome/scripts/translations.prepareMultipartMsg (scripts/translations/upload.go:80) -> io.Copy (src/io/io.go:388) -> io.copyBuffer (src/io/io.go:431) -> github.com/quic-go/quic-go/http3.RequestStream.Write (http3/stream.go:222)`

Decision targets (3): `github.com/quic-go/quic-go/http3.decodeTrailers`, `github.com/quic-go/quic-go/http3.parseTrailers`, `github.com/quic-go/quic-go/http3.parseHeaders`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', True\): 4, \('NOT\_REACHABLE', True\): 6, \('REACHABLE', True\): 2\}

### Route shown: `github.com/quic-go/quic-go/http3.parseHeaders` from `github.com/AdguardTeam/AdGuardHome`

Evidence level STATIC\_PATH, dynamic steps 0, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/AdguardTeam/AdGuardHome.main` calls `github.com/AdguardTeam/AdGuardHome/internal/home.Main` (STATIC) at `main.go:23` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/main.go#L23)

```go
22  func main() {
23> 	home.Main(clientBuildFS)
24  }
```

2. `github.com/AdguardTeam/AdGuardHome/internal/home.Main` calls `github.com/AdguardTeam/AdGuardHome/internal/home.run` (STATIC) at `internal/home/home.go:144` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/home.go#L144)

```go
143  	// run the protection
144> 	run(ctx, baseLogger, opts, clientBuildFS, done, sigHdlr, workDir, confPath)
145  }
```

3. `github.com/AdguardTeam/AdGuardHome/internal/home.run` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start` (STATIC) at `internal/home/home.go:795` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/home.go#L795)

```go
794  
795> 	web.start(ctx)
796
```

4. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.tlsServerLoop` (STATIC) at `internal/home/web.go:261` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L261)

```go
260  	// for https, we have a separate goroutine loop
261> 	go web.tlsServerLoop(ctx)
262
```

5. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.tlsServerLoop` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.serveTLS` (STATIC) at `internal/home/web.go:336` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L336)

```go
335  	for {
336> 		shouldContinue := web.serveTLS(ctx)
337  		if !shouldContinue {
```

6. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.serveTLS` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.mustStartHTTP3` (STATIC) at `internal/home/web.go:383` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L383)

```go
382  	if web.conf.serveHTTP3 {
383> 		go web.mustStartHTTP3(ctx, addr)
384  	}
```

7. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.mustStartHTTP3` calls `github.com/quic-go/quic-go/http3.Server.ListenAndServe` (STATIC) at `internal/home/web.go:435` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L435)

```go
434  	web.logger.DebugContext(ctx, "starting http/3 server")
435> 	err := web.httpsServer.server3.ListenAndServe()
436  	if !errors.Is(err, http.ErrServerClosed) {
```

8. `github.com/quic-go/quic-go/http3.Server.ListenAndServe` calls `github.com/quic-go/quic-go/http3.Server.serveListener` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:204` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L204)

```go
203  
204> 	return s.serveListener(*ln)
205  }
```

9. `github.com/quic-go/quic-go/http3.Server.serveListener` calls `github.com/quic-go/quic-go/http3.Server.serveListener$1` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:302` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L302)

```go
301  		s.connCount.Add(1)
302> 		go func() {
303  			defer s.decreaseConnCount()
```

10. `github.com/quic-go/quic-go/http3.Server.serveListener$1` calls `github.com/quic-go/quic-go/http3.Server.handleConn` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:304` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L304)

```go
303  			defer s.decreaseConnCount()
304> 			if err := s.handleConn(conn); err != nil {
305  				if s.Logger != nil {
```

11. `github.com/quic-go/quic-go/http3.Server.handleConn` calls `github.com/quic-go/quic-go/http3.Server.handleConn$2` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:564` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L564)

```go
563  		wg.Add(1)
564> 		go func() {
565  			// handleRequest will return once the request has been handled,
```

12. `github.com/quic-go/quic-go/http3.Server.handleConn$2` calls `github.com/quic-go/quic-go/http3.Server.handleRequest` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:568` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L568)

```go
567  			defer wg.Done()
568> 			s.handleRequest(hconn, str, hconn.decoder, qlogger)
569  		}()
```

13. `github.com/quic-go/quic-go/http3.Server.handleRequest` calls `github.com/quic-go/quic-go/http3.requestFromHeaders` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/server.go:633` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/server.go#L633)

```go
632  	}
633> 	req, err := requestFromHeaders(decodeFn, s.maxHeaderBytes(), &hfs)
634  	if qlogger != nil {
```

14. `github.com/quic-go/quic-go/http3.requestFromHeaders` calls `github.com/quic-go/quic-go/http3.parseHeaders` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.0/http3/headers.go:180` [source](https://github.com/quic-go/quic-go/blob/v0.57.0/http3/headers.go#L180)

```go
179  func requestFromHeaders(decodeFn qpack.DecodeFunc, sizeLimit int, headerFields *[]qpack.HeaderField) (*http.Request, error) {
180> 	hdr, err := parseHeaders(decodeFn, true, sizeLimit, headerFields)
181  	if err != nil {
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |

## AdGuardHome\_\_GO\-2026\-5506

- item: D3c case
- advisory: `GO-2026-5506` OpenTelemetry\-Go: Multi\-value baggage header extraction causes excessive allocations in go\.opentelemetry\.io/otel
- vulnerable module: `go.opentelemetry.io/otel@v1.38.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_AFFECTED at level NONE; scored as NOT\_REACHABLE

Decision targets (6): `go.opentelemetry.io/otel/internal/global.ErrDelegator.Handle`, `go.opentelemetry.io/otel/internal/global.SetErrorHandler`, `go.opentelemetry.io/otel/internal/global.GetErrorHandler`, `go.opentelemetry.io/otel/baggage.Parse`, `go.opentelemetry.io/otel/baggage.New`, `go.opentelemetry.io/otel/propagation.Baggage.Extract`
Extra evidence only (never decide): `go.opentelemetry.io/otel/baggage.parseMember`, `go.opentelemetry.io/otel/internal/global.ErrDelegator.setDelegate`, `go.opentelemetry.io/otel/internal/global.SetMeterProvider`, `go.opentelemetry.io/otel/internal/global.defaultErrorHandler`, `go.opentelemetry.io/otel/internal/global.defaultTracerValue`, `go.opentelemetry.io/otel/propagation.extractMultiBaggage`, `go.opentelemetry.io/otel/propagation.extractSingleBaggage`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 28, \('NOT\_REACHABLE', True\): 24\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## AdGuardHome\_\_GO\-2026\-5756

- item: D3c case
- advisory: `GO-2026-5756` AdGuard Home: DoQ\-to\-UDP State Reduction and Source\-Port Oracle in github\.com/AdguardTeam/AdGuardHome
- vulnerable module: `github.com/AdguardTeam/dnsproxy@v0.78.2`
- stratum: N (no curated vulndb symbols)
- review status: UNREVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/AdguardTeam/dnsproxy/fastip.FastestAddr.ExchangeFastest`, `github.com/AdguardTeam/dnsproxy/fastip.New`, `github.com/AdguardTeam/dnsproxy/fastip.init`, `github.com/AdguardTeam/dnsproxy/internal/bootstrap.NewDialContext`, `github.com/AdguardTeam/dnsproxy/internal/bootstrap.NewDialContext$1`, `github.com/AdguardTeam/dnsproxy/internal/bootstrap.NewDialContext$2`, `github.com/AdguardTeam/dnsproxy/internal/bootstrap.ResolveDialContext`, `github.com/AdguardTeam/dnsproxy/internal/bootstrap.init`, `github.com/AdguardTeam/dnsproxy/internal/dnsmsg.DefaultMessageConstructor.NewMsgNOTIMPLEMENTED`, `github.com/AdguardTeam/dnsproxy/internal/dnsmsg.DefaultMessageConstructor.NewMsgNXDOMAIN`
- govulncheck trace: `github.com/AdguardTeam/AdGuardHome/scripts/translations.main (scripts/translations/main.go:89) -> github.com/AdguardTeam/AdGuardHome/scripts/translations.twoskyClient.download (scripts/translations/download.go:48) -> sync.WaitGroup.Go (src/sync/waitgroup.go:238) -> sync.Go$1 (src/sync/waitgroup.go:258) -> github.com/AdguardTeam/AdGuardHome/internal/dnsforward.check$1 (internal/dnsforward/configvalidator.go:199) -> github.com/AdguardTeam/AdGuardHome/internal/dnsforward.checkSrv (internal/dnsforward/configvalidator.go:217) -> github.com/AdguardTeam/AdGuardHome/internal/dnsforward.healthchecker.check (internal/dnsforward/configvalidator.go:422) -> github.com/AdguardTeam/dnsproxy/upstream.plainDNS.Exchange (upstream/plain.go:139)`

Decision targets (5): `github.com/AdguardTeam/dnsproxy/internal/cmd.loadServersList`, `github.com/AdguardTeam/dnsproxy/upstream.dnsOverHTTPS.supportsH3`, `github.com/AdguardTeam/dnsproxy/upstream.dnsOverQUIC.getBytesPool`, `github.com/AdguardTeam/dnsproxy/upstream.plainDNS.dialExchange`, `github.com/AdguardTeam/dnsproxy/upstream.logBegin`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 16, \('REACHABLE', True\): 4\}

### Route shown: `github.com/AdguardTeam/dnsproxy/upstream.plainDNS.dialExchange` from `github.com/AdguardTeam/AdGuardHome`

Evidence level HAS\_DYNAMIC\_STEPS, dynamic steps 2, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/AdguardTeam/AdGuardHome.main` calls `github.com/AdguardTeam/AdGuardHome/internal/home.Main` (STATIC) at `main.go:23` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/main.go#L23)

```go
22  func main() {
23> 	home.Main(clientBuildFS)
24  }
```

2. `github.com/AdguardTeam/AdGuardHome/internal/home.Main` calls `github.com/AdguardTeam/AdGuardHome/internal/home.run` (STATIC) at `internal/home/home.go:144` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/home.go#L144)

```go
143  	// run the protection
144> 	run(ctx, baseLogger, opts, clientBuildFS, done, sigHdlr, workDir, confPath)
145  }
```

3. `github.com/AdguardTeam/AdGuardHome/internal/home.run` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start` (STATIC) at `internal/home/home.go:795` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/home.go#L795)

```go
794  
795> 	web.start(ctx)
796
```

4. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start` calls `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start$1` (STATIC) at `internal/home/web.go:289` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L289)

```go
288  		}
289> 		go func() {
290  			defer slogutil.RecoverAndLog(ctx, logger)
```

5. `github.com/AdguardTeam/AdGuardHome/internal/home.webAPI.start$1` calls `net/http.Server.ListenAndServe` (STATIC) at `internal/home/web.go:294` [source](https://github.com/AdguardTeam/AdGuardHome/blob/42a2653d3245313b6247ada092c66e2e11c72468/internal/home/web.go#L294)

```go
293  
294> 			errs <- web.httpServer.ListenAndServe()
295  		}()
```

6. `net/http.Server.ListenAndServe` calls `net/http.Server.Serve` (STATIC) at `$GOROOT/src/net/http/server.go:3380` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L3380)

```go
3379  	}
3380> 	return s.Serve(ln)
3381  }
```

7. `net/http.Server.Serve` calls `net/http.conn.serve` (STATIC) at `$GOROOT/src/net/http/server.go:3484` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L3484)

```go
3483  		c.setState(c.rwc, StateNew, runHooks) // before Serve can return
3484> 		go c.serve(connCtx)
3485  	}
```

8. `net/http.conn.serve` calls `net/http.serverHandler.ServeHTTP` (STATIC) at `$GOROOT/src/net/http/server.go:2087` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L2087)

```go
2086  		inFlightResponse = w
2087> 		serverHandler{c.server}.ServeHTTP(w, w.req)
2088  		inFlightResponse = nil
```

9. `net/http.serverHandler.ServeHTTP` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.ServeHTTP` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOROOT/src/net/http/server.go:3331` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L3331)

```go
3330  
3331> 	handler.ServeHTTP(rw, req)
3332  }
```

10. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.ServeHTTP` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.handleDNSRequest` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/serverhttps.go:216` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/serverhttps.go#L216)

```go
215  
216> 	err = p.handleDNSRequest(d)
217  	if err != nil {
```

11. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.handleDNSRequest` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.Resolve` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/server.go:127` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/server.go#L127)

```go
126  		} else {
127> 			err = errors.Annotate(p.Resolve(d), "using default request handler: %w")
128  		}
```

12. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.Resolve` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.replyFromUpstream` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/proxy.go:733` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/proxy.go#L733)

```go
732  	var ok bool
733> 	ok, err = p.replyFromUpstream(dctx)
734
```

13. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.replyFromUpstream` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.exchangeUpstreams` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/proxy.go:608` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/proxy.go#L608)

```go
607  	// Perform the DNS request.
608> 	resp, u, err := p.exchangeUpstreams(req, wrapped)
609  	if dns64Ups := p.performDNS64(req, resp, wrapped); dns64Ups != nil {
```

14. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.exchangeUpstreams` calls `github.com/AdguardTeam/dnsproxy/proxy.Proxy.exchange` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/exchange.go:37` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/exchange.go#L37)

```go
36  		u = ups[0]
37> 		resp, _, err = p.exchange(u, req)
38  		if err != nil {
```

15. `github.com/AdguardTeam/dnsproxy/proxy.Proxy.exchange` calls `github.com/AdguardTeam/dnsproxy/upstream.plainDNS.Exchange` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/proxy/exchange.go:80` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/proxy/exchange.go#L80)

```go
79  	startTime := p.time.Now()
80> 	resp, err = u.Exchange(req)
81
```

16. `github.com/AdguardTeam/dnsproxy/upstream.plainDNS.Exchange` calls `github.com/AdguardTeam/dnsproxy/upstream.plainDNS.dialExchange` (STATIC) at `$GOMODCACHE/github.com/!adguard!team/dnsproxy@v0.78.2/upstream/plain.go:148` [source](https://github.com/AdguardTeam/dnsproxy/blob/v0.78.2/upstream/plain.go#L148)

```go
147  
148> 	resp, err = p.dialExchange(p.net, dial, req)
149  	if p.net != networkUDP {
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |
