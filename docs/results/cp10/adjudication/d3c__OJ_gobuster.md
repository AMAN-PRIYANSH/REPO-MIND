# CP10 adjudication: d3c\_\_OJ\_gobuster

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

## gobuster\_\_GO\-2026\-5052

- item: D3c case
- advisory: `GO-2026-5052` Vulnerability in software\.sslmate\.com/src/go\-pkcs12
- vulnerable module: `software.sslmate.com/src/go-pkcs12@v0.6.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `software.sslmate.com/src/go-pkcs12.DecodeChain`
- govulncheck trace: `github.com/OJ/gobuster/v3.main (main.go:59) -> github.com/urfave/cli/v2.App.Run (app.go:307) -> github.com/urfave/cli/v2.App.RunContext (app.go:333) -> github.com/urfave/cli/v2.Command.Run (command.go:187) -> github.com/OJ/gobuster/v3/cli/gcs.run (cli/gcs/gcs.go:36) -> github.com/OJ/gobuster/v3/cli.ParseBasicHTTPOptions (cli/options.go:80) -> software.sslmate.com/src/go-pkcs12.DecodeChain (pkcs12.go:413)`

Decision targets (4): `software.sslmate.com/src/go-pkcs12.Decode`, `software.sslmate.com/src/go-pkcs12.DecodeChain`, `software.sslmate.com/src/go-pkcs12.DecodeTrustStore`, `software.sslmate.com/src/go-pkcs12.ToPEM`
Extra evidence only (never decide): `software.sslmate.com/src/go-pkcs12.doPBMAC1`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 1, \('NOT\_REACHABLE', True\): 7, \('REACHABLE', False\): 1, \('REACHABLE', True\): 1\}

### Route shown: `software.sslmate.com/src/go-pkcs12.DecodeChain` from `github.com/OJ/gobuster/v3`

Evidence level HAS\_DYNAMIC\_STEPS, dynamic steps 1, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/OJ/gobuster/v3.main` calls `github.com/urfave/cli/v2.App.Run` (STATIC) at `main.go:59` [source](https://github.com/OJ/gobuster/blob/e8410cad6cacf08b82e2f610055f636f0be61c40/main.go#L59)

```go
58  
59> 	err := app.Run(os.Args)
60  	if err != nil {
```

2. `github.com/urfave/cli/v2.App.Run` calls `github.com/urfave/cli/v2.App.RunContext` (STATIC) at `$GOMODCACHE/github.com/urfave/cli/v2@v2.27.7/app.go:307` [source](https://github.com/urfave/cli/blob/v2.27.7/app.go#L307)

```go
306  func (a *App) Run(arguments []string) (err error) {
307> 	return a.RunContext(context.Background(), arguments)
308  }
```

3. `github.com/urfave/cli/v2.App.RunContext` calls `github.com/urfave/cli/v2.Command.Run` (STATIC) at `$GOMODCACHE/github.com/urfave/cli/v2@v2.27.7/app.go:333` [source](https://github.com/urfave/cli/blob/v2.27.7/app.go#L333)

```go
332  	}
333> 	return a.rootCommand.Run(cCtx, arguments...)
334  }
```

4. `github.com/urfave/cli/v2.Command.Run` calls `github.com/OJ/gobuster/v3/cli/gcs.run` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOMODCACHE/github.com/urfave/cli/v2@v2.27.7/command.go:187` [source](https://github.com/urfave/cli/blob/v2.27.7/command.go#L187)

```go
186  	if checkHelp(cCtx) {
187> 		return helpCommand.Action(cCtx)
188  	}
```

5. `github.com/OJ/gobuster/v3/cli/gcs.run` calls `github.com/OJ/gobuster/v3/cli.ParseBasicHTTPOptions` (STATIC) at `cli/gcs/gcs.go:36` [source](https://github.com/OJ/gobuster/blob/e8410cad6cacf08b82e2f610055f636f0be61c40/cli/gcs/gcs.go#L36)

```go
35  
36> 	httpOptions, err := internalcli.ParseBasicHTTPOptions(c)
37  	if err != nil {
```

6. `github.com/OJ/gobuster/v3/cli.ParseBasicHTTPOptions` calls `software.sslmate.com/src/go-pkcs12.DecodeChain` (STATIC) at `cli/options.go:80` [source](https://github.com/OJ/gobuster/blob/e8410cad6cacf08b82e2f610055f636f0be61c40/cli/options.go#L80)

```go
79  		}
80> 		privKey, pubKey, _, err := pkcs12.DecodeChain(p12Content, p12Pass)
81  		if err != nil {
```


| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |
