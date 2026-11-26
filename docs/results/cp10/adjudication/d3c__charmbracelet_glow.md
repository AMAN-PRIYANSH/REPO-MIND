# CP10 adjudication: d3c\_\_charmbracelet\_glow

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

## glow\_\_GO\-2025\-3900

- item: D3c case
- advisory: `GO-2025-3900` Go\-viper's mapstructure May Leak Sensitive Information in Logs in github\.com/go\-viper/mapstructure
- vulnerable module: `github.com/go-viper/mapstructure/v2@v2.2.1`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** ANALYSIS\_FAILED
- VulnTrace, legacy targets: **CANT\_DETERMINE** ANALYSIS\_FAILED
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (27): `github.com/go-viper/mapstructure/v2.StringToIntHookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeFloat`, `github.com/go-viper/mapstructure/v2.StringToUintHookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeInt`, `github.com/go-viper/mapstructure/v2.StringToFloat32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint8HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPNetHookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt8HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPHookFunc`, `github.com/go-viper/mapstructure/v2.StringToBoolHookFunc`, `github.com/go-viper/mapstructure/v2.StringToTimeHookFunc`, `github.com/go-viper/mapstructure/v2.StringToURLHookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex128HookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPPrefixHookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrPortHookFunc`, `github.com/go-viper/mapstructure/v2.StringToTimeDurationHookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt16HookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeUint`, `github.com/go-viper/mapstructure/v2.StringToUint16HookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrHookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint64HookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeBool`, `github.com/go-viper/mapstructure/v2.StringToInt64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToFloat64HookFunc`
Extra evidence only (never decide): `github.com/go-viper/mapstructure/v2.UnconvertibleTypeError.Error`, `github.com/go-viper/mapstructure/v2.UnconvertibleTypeError.mapstructure`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 2, \('CANT\_DETERMINE', True\): 1, \('NOT\_REACHABLE', True\): 26\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## glow\_\_GO\-2026\-5320

- item: D3c case
- advisory: `GO-2026-5320` Cross\-site Scripting \(XSS\) in github\.com/yuin/goldmark
- vulnerable module: `github.com/yuin/goldmark@v1.7.8`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/yuin/goldmark/renderer/html.Renderer.renderAutoLink`, `github.com/yuin/goldmark/renderer/html.Renderer.renderImage`, `github.com/yuin/goldmark/renderer/html.Renderer.renderLink`
- govulncheck trace: `github.com/charmbracelet/glow/v2.main (main.go:376) -> github.com/spf13/cobra.Command.Execute (command.go:1071) -> github.com/spf13/cobra.Command.ExecuteC (command.go:1148) -> github.com/spf13/cobra.Command.execute (command.go:1015) -> github.com/charmbracelet/glow/v2.execute (main.go:229) -> github.com/charmbracelet/glow/v2.executeCLI (main.go:308) -> github.com/charmbracelet/glamour.TermRenderer.Render (glamour.go:286) -> github.com/charmbracelet/glamour.TermRenderer.RenderBytes (glamour.go:293) -> github.com/yuin/goldmark.markdown.Convert (markdown.go:118) -> github.com/yuin/goldmark/renderer.renderer.Render (renderer/renderer.go:161) -> github.com/yuin/goldmark/ast.Walk (ast/ast.go:500) -> github.com/yuin/goldmark/ast.walkHelper (ast/ast.go:505) -> github.com/yuin/goldmark/renderer.Render$2 (renderer/renderer.go:166) -> github.com/yuin/goldmark/renderer/html.Renderer.renderAutoLink (renderer/html/html.go:554)`

Decision targets (3): `github.com/yuin/goldmark/renderer/html.Renderer.renderImage`, `github.com/yuin/goldmark/renderer/html.Renderer.renderLink`, `github.com/yuin/goldmark/renderer/html.Renderer.renderAutoLink`
Per-entry results (result, deciding): \{\('REACHABLE', True\): 3\}

### Route shown: `github.com/yuin/goldmark/renderer/html.Renderer.renderImage` from `github.com/charmbracelet/glow/v2`

Evidence level HAS\_DYNAMIC\_STEPS, dynamic steps 5, passes the CP9 filter True. Route shown is an example from the call graph; steps marked unconfirmed may not run in this context.

1. `github.com/charmbracelet/glow/v2.main` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `main.go:376` [source](https://github.com/charmbracelet/glow/blob/d37e9887875a2faa4baee6a7d090eb357dd63771/main.go#L376)

```go
375  	}
376> 	if err := rootCmd.Execute(); err != nil {
377  		_ = closer()
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

4. `github.com/spf13/cobra.Command.execute` calls `github.com/charmbracelet/glow/v2.execute` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1015` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1015)

```go
1014  	if c.RunE != nil {
1015> 		if err := c.RunE(c, argWoFlags); err != nil {
1016  			return err
```

5. `github.com/charmbracelet/glow/v2.execute` calls `github.com/charmbracelet/glow/v2.executeCLI` (STATIC) at `main.go:229` [source](https://github.com/charmbracelet/glow/blob/d37e9887875a2faa4baee6a7d090eb357dd63771/main.go#L229)

```go
228  		defer src.reader.Close() //nolint:errcheck
229> 		return executeCLI(cmd, src, os.Stdout)
230  	}
```

6. `github.com/charmbracelet/glow/v2.executeCLI` calls `github.com/charmbracelet/glamour.TermRenderer.Render` (STATIC) at `main.go:308` [source](https://github.com/charmbracelet/glow/blob/d37e9887875a2faa4baee6a7d090eb357dd63771/main.go#L308)

```go
307  
308> 	out, err := r.Render(content)
309  	if err != nil {
```

7. `github.com/charmbracelet/glamour.TermRenderer.Render` calls `github.com/charmbracelet/glamour.TermRenderer.RenderBytes` (STATIC) at `$GOMODCACHE/github.com/charmbracelet/glamour@v0.10.0/glamour.go:286` [source](https://github.com/charmbracelet/glamour/blob/v0.10.0/glamour.go#L286)

```go
285  func (tr *TermRenderer) Render(in string) (string, error) {
286> 	b, err := tr.RenderBytes([]byte(in))
287  	return string(b), err
```

8. `github.com/charmbracelet/glamour.TermRenderer.RenderBytes` calls `github.com/yuin/goldmark.markdown.Convert` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOMODCACHE/github.com/charmbracelet/glamour@v0.10.0/glamour.go:293` [source](https://github.com/charmbracelet/glamour/blob/v0.10.0/glamour.go#L293)

```go
292  	var buf bytes.Buffer
293> 	err := tr.md.Convert(in, &buf)
294  	return buf.Bytes(), err
```

9. `github.com/yuin/goldmark.markdown.Convert` calls `github.com/yuin/goldmark/renderer.renderer.Render` (DYNAMIC INTERFACE\_METHOD, **unconfirmed**) at `$GOMODCACHE/github.com/yuin/goldmark@v1.7.8/markdown.go:118` [source](https://github.com/yuin/goldmark/blob/v1.7.8/markdown.go#L118)

```go
117  	doc := m.parser.Parse(reader, opts...)
118> 	return m.renderer.Render(writer, source, doc)
119  }
```

10. `github.com/yuin/goldmark/renderer.renderer.Render` calls `github.com/yuin/goldmark/ast.Walk` (STATIC) at `$GOMODCACHE/github.com/yuin/goldmark@v1.7.8/renderer/renderer.go:161` [source](https://github.com/yuin/goldmark/blob/v1.7.8/renderer/renderer.go#L161)

```go
160  	}
161> 	err := ast.Walk(n, func(n ast.Node, entering bool) (ast.WalkStatus, error) {
162  		s := ast.WalkStatus(ast.WalkContinue)
```

11. `github.com/yuin/goldmark/ast.Walk` calls `github.com/yuin/goldmark/ast.walkHelper` (STATIC) at `$GOMODCACHE/github.com/yuin/goldmark@v1.7.8/ast/ast.go:500` [source](https://github.com/yuin/goldmark/blob/v1.7.8/ast/ast.go#L500)

```go
499  func Walk(n Node, walker Walker) error {
500> 	_, err := walkHelper(n, walker)
501  	return err
```

12. `github.com/yuin/goldmark/ast.walkHelper` calls `github.com/yuin/goldmark/renderer.renderer.Render$2` (DYNAMIC CLOSURE\_VIA\_PARAMETER, **unconfirmed**) at `$GOMODCACHE/github.com/yuin/goldmark@v1.7.8/ast/ast.go:505` [source](https://github.com/yuin/goldmark/blob/v1.7.8/ast/ast.go#L505)

```go
504  func walkHelper(n Node, walker Walker) (WalkStatus, error) {
505> 	status, err := walker(n, true)
506  	if err != nil || status == WalkStop {
```

13. `github.com/yuin/goldmark/renderer.renderer.Render$2` calls `github.com/yuin/goldmark/renderer/html.Renderer.renderImage$bound` (DYNAMIC FUNCTION\_VALUE, **unconfirmed**) at `$GOMODCACHE/github.com/yuin/goldmark@v1.7.8/renderer/renderer.go:166` [source](https://github.com/yuin/goldmark/blob/v1.7.8/renderer/renderer.go#L166)

```go
165  		if f != nil {
166> 			s, err = f(writer, source, n, entering)
167  		}
```

14. `github.com/yuin/goldmark/renderer/html.Renderer.renderImage$bound` calls `github.com/yuin/goldmark/renderer/html.Renderer.renderImage` (STATIC) (synthetic edge, no call site)

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| path_judgement | |
| by | |
| note | |
