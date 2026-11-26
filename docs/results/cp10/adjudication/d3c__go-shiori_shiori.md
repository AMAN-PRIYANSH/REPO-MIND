# CP10 adjudication: d3c\_\_go\-shiori\_shiori

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

## shiori\_\_GO\-2026\-5841

- item: D3c case
- advisory: `GO-2026-5841` OOB read in github\.com/klauspost/compress/s2
- vulnerable module: `github.com/klauspost/compress@v1.18.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_AFFECTED at level NONE; scored as NOT\_REACHABLE

Decision targets (1): `github.com/klauspost/compress/s2.NewDict`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 1\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## shiori\_\_GO\-2025\-3553

- item: D3c case
- advisory: `GO-2025-3553` Excessive memory allocation during header parsing in github\.com/golang\-jwt/jwt
- vulnerable module: `github.com/golang-jwt/jwt/v5@v5.2.1`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/golang-jwt/jwt/v5.Parser.ParseUnverified`
- govulncheck trace: `github.com/go-shiori/shiori.main (main.go:26) -> github.com/spf13/cobra.Command.Execute (command.go:1071) -> github.com/spf13/cobra.Command.ExecuteC (command.go:1148) -> github.com/spf13/cobra.Command.execute (command.go:1019) -> github.com/go-shiori/shiori/internal/cmd.openHandler (internal/cmd/open.go:193) -> net/http.Serve (src/net/http/server.go:2962) -> net/http.Server.Serve (src/net/http/server.go:3484) -> net/http.conn.serve (src/net/http/server.go:2087) -> net/http.serverHandler.ServeHTTP (src/net/http/server.go:3331) -> net/http.ServeMux.ServeHTTP (src/net/http/server.go:2848) -> net/http.HandlerFunc.ServeHTTP (src/net/http/server.go:2306) -> github.com/go-shiori/shiori/internal/http.ToHTTPHandler$1 (internal/http/http.go:17) -> github.com/go-shiori/shiori/internal/http/middleware.AuthMiddleware.OnRequest (internal/http/middleware/auth.go:37) -> github.com/go-shiori/shiori/internal/domains.AuthDomain.CheckToken (internal/domains/auth.go:25) -> github.com/golang-jwt/jwt/v5.ParseWithClaims (parser.go:237) -> github.com/golang-jwt/jwt/v5.Parser.ParseWithClaims (parser.go:56) -> github.com/golang-jwt/jwt/v5.Parser.ParseUnverified (parser.go:138)`

Decision targets (1): `github.com/golang-jwt/jwt/v5.Parser.ParseUnverified`
Per-entry results (result, deciding): \{\('REACHABLE', True\): 1\}

### Route shown: `github.com/golang-jwt/jwt/v5.Parser.ParseUnverified` from `github.com/go-shiori/shiori`

Evidence level HAS\_DYNAMIC\_STEPS, dynamic steps 6, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/go-shiori/shiori.main` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `main.go:26` [source](https://github.com/go-shiori/shiori/blob/da56f82faac5bf350fc4175e5ff50726cb10d956/main.go#L26)

```go
25  func main() {
26> 	err := cmd.ShioriCmd().Execute()
27  	if err != nil {
```

2. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1071` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1071)

```go
1070  func (c *Command) Execute() error {
1071> 	_, err := c.ExecuteC()
1072  	return err
```

3. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1148` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1148)

```go
1147  
1148> 	err = cmd.execute(flags)
1149  	if err != nil {
```

4. `github.com/spf13/cobra.Command.execute` calls `github.com/go-shiori/shiori/internal/cmd.openHandler` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1019` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1019)

```go
1018  	} else {
1019> 		c.Run(c, argWoFlags)
1020  	}
```

5. `github.com/go-shiori/shiori/internal/cmd.openHandler` calls `net/http.Serve` (STATIC) at `internal/cmd/open.go:193` [source](https://github.com/go-shiori/shiori/blob/da56f82faac5bf350fc4175e5ff50726cb10d956/internal/cmd/open.go#L193)

```go
192  	// Serve archive
193> 	err = http.Serve(listener, router)
194  	if err != nil {
```

6. `net/http.Serve` calls `net/http.Server.Serve` (STATIC) at `$GOROOT/src/net/http/server.go:2962` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L2962)

```go
2961  	srv := &Server{Handler: handler}
2962> 	return srv.Serve(l)
2963  }
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

9. `net/http.serverHandler.ServeHTTP` calls `net/http.ServeMux.ServeHTTP` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOROOT/src/net/http/server.go:3331` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L3331)

```go
3330  
3331> 	handler.ServeHTTP(rw, req)
3332  }
```

10. `net/http.ServeMux.ServeHTTP` calls `net/http.HandlerFunc.ServeHTTP` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOROOT/src/net/http/server.go:2848` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L2848)

```go
2847  	}
2848> 	h.ServeHTTP(w, r)
2849  }
```

11. `net/http.HandlerFunc.ServeHTTP` calls `github.com/go-shiori/shiori/internal/http.ToHTTPHandler$1` (DYNAMIC CLOSURE\_VIA\_PARAMETER, **unconfirmed**) at `$GOROOT/src/net/http/server.go:2306` [source](https://github.com/golang/go/blob/go1.26.10/src/net/http/server.go#L2306)

```go
2305  func (f HandlerFunc) ServeHTTP(w ResponseWriter, r *Request) {
2306> 	f(w, r)
2307  }
```

12. `github.com/go-shiori/shiori/internal/http.ToHTTPHandler$1` calls `github.com/go-shiori/shiori/internal/http/middleware.AuthMiddleware.OnRequest` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `internal/http/http.go:17` [source](https://github.com/go-shiori/shiori/blob/da56f82faac5bf350fc4175e5ff50726cb10d956/internal/http/http.go#L17)

```go
16  		for _, m := range middlewares {
17> 			if err := m.OnRequest(deps, c); err != nil {
18  				// Handle middleware error
```

13. `github.com/go-shiori/shiori/internal/http/middleware.AuthMiddleware.OnRequest` calls `github.com/go-shiori/shiori/internal/domains.AuthDomain.CheckToken` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `internal/http/middleware/auth.go:37` [source](https://github.com/go-shiori/shiori/blob/da56f82faac5bf350fc4175e5ff50726cb10d956/internal/http/middleware/auth.go#L37)

```go
36  
37> 	account, err := deps.Domains().Auth().CheckToken(c.Request().Context(), token)
38  	if err != nil {
```

14. `github.com/go-shiori/shiori/internal/domains.AuthDomain.CheckToken` calls `github.com/golang-jwt/jwt/v5.ParseWithClaims` (STATIC) at `internal/domains/auth.go:25` [source](https://github.com/go-shiori/shiori/blob/da56f82faac5bf350fc4175e5ff50726cb10d956/internal/domains/auth.go#L25)

```go
24  func (d *AuthDomain) CheckToken(ctx context.Context, userJWT string) (*model.AccountDTO, error) {
25> 	token, err := jwt.ParseWithClaims(userJWT, &JWTClaim{}, func(token *jwt.Token) (interface{}, error) {
26  		// Validate algorithm
```

15. `github.com/golang-jwt/jwt/v5.ParseWithClaims` calls `github.com/golang-jwt/jwt/v5.Parser.ParseWithClaims` (STATIC) at `$GOMODCACHE/github.com/golang-jwt/jwt/v5@v5.2.1/parser.go:237` [source](https://github.com/golang-jwt/jwt/blob/v5.2.1/parser.go#L237)

```go
236  func ParseWithClaims(tokenString string, claims Claims, keyFunc Keyfunc, options ...ParserOption) (*Token, error) {
237> 	return NewParser(options...).ParseWithClaims(tokenString, claims, keyFunc)
238  }
```

16. `github.com/golang-jwt/jwt/v5.Parser.ParseWithClaims` calls `github.com/golang-jwt/jwt/v5.Parser.ParseUnverified` (STATIC) at `$GOMODCACHE/github.com/golang-jwt/jwt/v5@v5.2.1/parser.go:56` [source](https://github.com/golang-jwt/jwt/blob/v5.2.1/parser.go#L56)

```go
55  func (p *Parser) ParseWithClaims(tokenString string, claims Claims, keyFunc Keyfunc) (*Token, error) {
56> 	token, parts, err := p.ParseUnverified(tokenString, claims)
57  	if err != nil {
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |

## shiori\_\_GO\-2026\-4503

- item: D3c case
- advisory: `GO-2026-4503` Invalid result or undefined behavior in filippo\.io/edwards25519
- vulnerable module: `filippo.io/edwards25519@v1.1.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (1): `filippo.io/edwards25519.Point.MultiScalarMult`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 1\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## shiori\_\_GO\-2026\-4887

- item: D3c case
- advisory: `GO-2026-4887` Moby has AuthZ plugin bypass when provided oversized request bodies in github\.com/docker/docker
- vulnerable module: `github.com/docker/docker@v28.0.1+incompatible`
- stratum: N (no curated vulndb symbols)
- review status: UNREVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_AFFECTED at level NONE; scored as NOT\_REACHABLE

Decision targets (3): `github.com/docker/docker/pkg/authorization.Ctx.AuthZRequest`, `github.com/docker/docker/pkg/authorization.drainBody`, `github.com/docker/docker/pkg/authorization.isChunked`
Extra evidence only (never decide): `github.com/docker/docker/pkg/authorization.Ctx.AuthZResponse`, `github.com/docker/docker/pkg/authorization.isAuthEndpoint`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 2, \('NOT\_REACHABLE', True\): 3\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## shiori\_\_GO\-2026\-4883

- item: D3c case
- advisory: `GO-2026-4883` Moby has an Off\-by\-one error in its plugin privilege validation in github\.com/docker/docker
- vulnerable module: `github.com/docker/docker@v28.0.1+incompatible`
- stratum: N (no curated vulndb symbols)
- review status: UNREVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** VERIFIER\_REJECTED
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): NOT\_AFFECTED at level NONE; scored as NOT\_REACHABLE

Decision targets (3): `github.com/docker/docker/daemon/pkg/plugin.isEqual`, `github.com/docker/docker/daemon/pkg/plugin.isEqualPrivilege`, `github.com/docker/docker/daemon/pkg/plugin.validatePrivileges`
Extra evidence only (never decide): `github.com/docker/docker/daemon/pkg/plugin.makeLoggerStreams`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 1, \('CANT\_DETERMINE', True\): 3\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
