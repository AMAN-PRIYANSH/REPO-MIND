# Adjudication: github\.com/XTLS/Xray\-core

- application: `github.com/XTLS/Xray-core` at tag `v25.12.8`, commit `81f8f398c7b2b845853b1e85087c6122acc6db0b`
- cases: 4; to adjudicate: 4
- sample rule: All REACHABLE cases\. Of NOT\_REACHABLE and of CANT\_DETERMINE cases: all if there are at most 5, otherwise 5 in ascending order of sha256\("20261028:" \+ case id\)\.
- main packages analysed: `github.com/xtls/xray-core/infra/vformat`, `github.com/xtls/xray-core/infra/vprotogen`, `github.com/xtls/xray-core/main`

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

## Xray\-core\_\_GO\-2026\-5676

- advisory: `GO-2026-5676` HTTP/3 QPACK Trailer Expansion Memory Exhaustion in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.57.1`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 3
- per-symbol results: \{'CANT\_DETERMINE': 3, 'NOT\_REACHABLE': 4, 'REACHABLE': 2\}
- verifier: FAILED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): REACHABLE \(finding level SYMBOL\) via `github.com/xtls/xray-core/main.main (main/main.go:22) -> github.com/xtls/xray-core/main/commands/base.Execute (main/commands/base/execute.go:64) -> github.com/xtls/xray-core/main/commands/all/api.executeRemoveInbounds (main/commands/all/api/inbounds_remove.go:44) -> github.com/xtls/xray-core/main/commands/all/api.loadArg (main/commands/all/api/shared.go:59) -> github.com/xtls/xray-core/main/commands/all/api.fetchHTTPContent (main/commands/all/api/shared.go:97) -> github.com/quic-go/quic-go/http3.gzipReader.Close (http3/gzip_reader.go:37)`

Reachable targets (2): `github.com/quic-go/quic-go/http3.parseHeaders`, `github.com/quic-go/quic-go/http3.parseTrailers`

### Path 1: `github.com/quic-go/quic-go/http3.parseHeaders` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `github.com/xtls/xray-core/main.executeRun` (DYNAMIC) at `main/commands/base/execute.go:64` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L64)

```go
63  			buildCommandText(cmd)
64> 			cmd.Run(cmd, args)
65  			Exit()
```

3. `github.com/xtls/xray-core/main.executeRun` calls `github.com/xtls/xray-core/core.Instance.Start` (DYNAMIC) at `main/run.go:90` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/run.go#L90)

```go
89  
90> 	if err := server.Start(); err != nil {
91  		fmt.Println("Failed to start:", err)
```

4. `github.com/xtls/xray-core/core.Instance.Start` calls `github.com/xtls/xray-core/app/proxyman/inbound.Manager.Start` (DYNAMIC) at `core/xray.go:390` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/core/xray.go#L390)

```go
389  	for _, f := range s.features {
390> 		if err := f.Start(); err != nil {
391  			return err
```

5. `github.com/xtls/xray-core/app/proxyman/inbound.Manager.Start` calls `github.com/xtls/xray-core/app/proxyman/inbound.AlwaysOnInboundHandler.Start` (DYNAMIC) at `app/proxyman/inbound/inbound.go:115` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/app/proxyman/inbound/inbound.go#L115)

```go
114  	for _, handler := range m.taggedHandlers {
115> 		if err := handler.Start(); err != nil {
116  			return err
```

6. `github.com/xtls/xray-core/app/proxyman/inbound.AlwaysOnInboundHandler.Start` calls `github.com/xtls/xray-core/app/proxyman/inbound.dsWorker.Start` (DYNAMIC) at `app/proxyman/inbound/always.go:160` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/app/proxyman/inbound/always.go#L160)

```go
159  	for _, worker := range h.workers {
160> 		if err := worker.Start(); err != nil {
161  			return err
```

7. `github.com/xtls/xray-core/app/proxyman/inbound.dsWorker.Start` calls `github.com/xtls/xray-core/transport/internet.ListenUnix` (STATIC) at `app/proxyman/inbound/worker.go:540` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/app/proxyman/inbound/worker.go#L540)

```go
539  	ctx := context.Background()
540> 	hub, err := internet.ListenUnix(ctx, w.address, w.stream, func(conn stat.Connection) {
541  		go w.callback(conn)
```

8. `github.com/xtls/xray-core/transport/internet.ListenUnix` calls `github.com/xtls/xray-core/transport/internet/splithttp.ListenXH` (DYNAMIC) at `transport/internet/tcp_hub.go:45` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/transport/internet/tcp_hub.go#L45)

```go
44  	}
45> 	listener, err := listenFunc(ctx, address, net.Port(0), settings, handler)
46  	if err != nil {
```

9. `github.com/xtls/xray-core/transport/internet/splithttp.ListenXH` calls `github.com/xtls/xray-core/transport/internet/splithttp.ListenXH$1` (STATIC) at `transport/internet/splithttp/hub.go:410` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/transport/internet/splithttp/hub.go#L410)

```go
409  		}
410> 		go func() {
411  			if err := l.h3server.ServeListener(l.h3listener); err != nil {
```

10. `github.com/xtls/xray-core/transport/internet/splithttp.ListenXH$1` calls `github.com/quic-go/quic-go/http3.Server.ServeListener` (STATIC) at `transport/internet/splithttp/hub.go:411` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/transport/internet/splithttp/hub.go#L411)

```go
410  		go func() {
411> 			if err := l.h3server.ServeListener(l.h3listener); err != nil {
412  				errors.LogErrorInner(ctx, err, "failed to serve HTTP/3 for XHTTP/3")
```

11. `github.com/quic-go/quic-go/http3.Server.ServeListener` calls `github.com/quic-go/quic-go/http3.Server.serveListener` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:288` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L288)

```go
287  
288> 	return s.serveListener(ln)
289  }
```

12. `github.com/quic-go/quic-go/http3.Server.serveListener` calls `github.com/quic-go/quic-go/http3.Server.serveListener$1` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:302` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L302)

```go
301  		s.connCount.Add(1)
302> 		go func() {
303  			defer s.decreaseConnCount()
```

13. `github.com/quic-go/quic-go/http3.Server.serveListener$1` calls `github.com/quic-go/quic-go/http3.Server.handleConn` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:304` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L304)

```go
303  			defer s.decreaseConnCount()
304> 			if err := s.handleConn(conn); err != nil {
305  				if s.Logger != nil {
```

14. `github.com/quic-go/quic-go/http3.Server.handleConn` calls `github.com/quic-go/quic-go/http3.Server.handleConn$2` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:564` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L564)

```go
563  		wg.Add(1)
564> 		go func() {
565  			// handleRequest will return once the request has been handled,
```

15. `github.com/quic-go/quic-go/http3.Server.handleConn$2` calls `github.com/quic-go/quic-go/http3.Server.handleRequest` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:568` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L568)

```go
567  			defer wg.Done()
568> 			s.handleRequest(hconn, str, hconn.decoder, qlogger)
569  		}()
```

16. `github.com/quic-go/quic-go/http3.Server.handleRequest` calls `github.com/quic-go/quic-go/http3.requestFromHeaders` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/server.go:633` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/server.go#L633)

```go
632  	}
633> 	req, err := requestFromHeaders(decodeFn, s.maxHeaderBytes(), &hfs)
634  	if qlogger != nil {
```

17. `github.com/quic-go/quic-go/http3.requestFromHeaders` calls `github.com/quic-go/quic-go/http3.parseHeaders` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/headers.go:180` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/headers.go#L180)

```go
179  func requestFromHeaders(decodeFn qpack.DecodeFunc, sizeLimit int, headerFields *[]qpack.HeaderField) (*http.Request, error) {
180> 	hdr, err := parseHeaders(decodeFn, true, sizeLimit, headerFields)
181  	if err != nil {
```


### Path 2: `github.com/quic-go/quic-go/http3.parseTrailers` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `github.com/xtls/xray-core/main/commands/all/convert.executeTypedMessageToJson` (DYNAMIC) at `main/commands/base/execute.go:64` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L64)

```go
63  			buildCommandText(cmd)
64> 			cmd.Run(cmd, args)
65  			Exit()
```

3. `github.com/xtls/xray-core/main/commands/all/convert.executeTypedMessageToJson` calls `io.ReadAll` (STATIC) at `main/commands/all/convert/json.go:56` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/convert/json.go#L56)

```go
55  
56> 	b, err := io.ReadAll(reader)
57  	if err != nil {
```

4. `io.ReadAll` calls `github.com/quic-go/quic-go/http3.hijackableBody.Read` (DYNAMIC) at `$GOROOT/src/io/io.go:722` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L722)

```go
721  	for {
722> 		n, err := r.Read(b[len(b):cap(b)])
723  		b = b[:len(b)+n]
```

5. `github.com/quic-go/quic-go/http3.hijackableBody.Read` calls `github.com/quic-go/quic-go/http3.body.Read` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/body.go:113` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/body.go#L113)

```go
112  func (r *hijackableBody) Read(b []byte) (int, error) {
113> 	n, err := r.body.Read(b)
114  	if err != nil {
```

6. `github.com/quic-go/quic-go/http3.body.Read` calls `github.com/quic-go/quic-go/http3.Stream.Read` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/body.go:62` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/body.go#L62)

```go
61  	}
62> 	n, err := r.str.Read(b)
63  	r.remainingContentLength -= int64(n)
```

7. `github.com/quic-go/quic-go/http3.Stream.Read` calls `github.com/quic-go/quic-go/http3.Conn.openRequestStream$2` (DYNAMIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/stream.go:97` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/stream.go#L97)

```go
96  				s.parsedTrailer = true
97> 				return 0, s.parseTrailer(s.datagramStream, f)
98  			default:
```

8. `github.com/quic-go/quic-go/http3.Conn.openRequestStream$2` calls `github.com/quic-go/quic-go/http3.Conn.decodeTrailers` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/conn.go:180` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/conn.go#L180)

```go
179  		newStream(hstr, c, trace, func(r io.Reader, hf *headersFrame) error {
180> 			hdr, err := c.decodeTrailers(r, str.StreamID(), hf, maxHeaderBytes)
181  			if err != nil {
```

9. `github.com/quic-go/quic-go/http3.Conn.decodeTrailers` calls `github.com/quic-go/quic-go/http3.parseTrailers` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.57.1/http3/conn.go:211` [source](https://github.com/quic-go/quic-go/blob/v0.57.1/http3/conn.go#L211)

```go
210  	}
211> 	trailers, err := parseTrailers(decodeFn, &fields)
212  	if err != nil {
```


| field | value |
|---|---|
| adjudication | |
| by | |
| note | |

## Xray\-core\_\_GO\-2026\-4512

- advisory: `GO-2026-4512` Fingerprint vulnerability in uTLS from missing padding extension for Chrome 120 in github\.com/refraction\-networking/utls
- vulnerable module: `github.com/refraction-networking/utls@v1.8.1`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'NOT\_REACHABLE': 2, 'REACHABLE': 1\}
- verifier: PASSED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): REACHABLE \(finding level SYMBOL\) via `github.com/xtls/xray-core/main.main (main/main.go:22) -> github.com/xtls/xray-core/main/commands/base.Execute (main/commands/base/execute.go:64) -> github.com/xtls/xray-core/main/commands/all/convert.executeTypedMessageToJson (main/commands/all/convert/json.go:56) -> io.ReadAll (src/io/io.go:722) -> github.com/gorilla/websocket.flateReadWrapper.Read (compression.go:130) -> github.com/refraction-networking/utls.UConn.Read (u_conn.go:861)`

Reachable targets (1): `github.com/refraction-networking/utls.utlsIdToSpec`

### Path 1: `github.com/refraction-networking/utls.utlsIdToSpec` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `fmt.Fprintf` (STATIC) at `main/commands/base/execute.go:72` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L72)

```go
71  		}
72> 		fmt.Fprintf(os.Stderr, "%s %s: unknown command\nRun '%s help%s' for usage.\n", CommandEnv.Exec, cmdName, CommandEnv.Exec, helpArg)
73  		SetExitStatus(2)
```

3. `fmt.Fprintf` calls `github.com/refraction-networking/utls.UConn.Write$wrapper` (DYNAMIC) at `$GOROOT/src/fmt/print.go:225` [source](https://github.com/golang/go/blob/go1.26.10/src/fmt/print.go#L225)

```go
224  	p.doPrintf(format, a)
225> 	n, err = w.Write(p.buf)
226  	p.free()
```

4. `github.com/refraction-networking/utls.UConn.Write$wrapper` calls `github.com/refraction-networking/utls.UConn.Write` (STATIC) (synthetic edge, no call site)
5. `github.com/refraction-networking/utls.UConn.Write` calls `github.com/refraction-networking/utls.UConn.Handshake` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:440` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L440)

```go
439  
440> 	if err := c.Handshake(); err != nil {
441  		return 0, err
```

6. `github.com/refraction-networking/utls.UConn.Handshake` calls `github.com/refraction-networking/utls.UConn.HandshakeContext` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:301` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L301)

```go
300  func (c *UConn) Handshake() error {
301> 	return c.HandshakeContext(context.Background())
302  }
```

7. `github.com/refraction-networking/utls.UConn.HandshakeContext` calls `github.com/refraction-networking/utls.UConn.handshakeContext` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:314` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L314)

```go
313  	// without confusing documented signature.
314> 	return c.handshakeContext(ctx)
315  }
```

8. `github.com/refraction-networking/utls.UConn.handshakeContext` calls `github.com/refraction-networking/utls.UConn.BuildHandshakeState` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:376` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L376)

```go
375  	if c.isClient {
376> 		err := c.BuildHandshakeState()
377  		if err != nil {
```

9. `github.com/refraction-networking/utls.UConn.BuildHandshakeState` calls `github.com/refraction-networking/utls.UConn.buildHandshakeState` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:97` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L97)

```go
96  func (uconn *UConn) BuildHandshakeState() error {
97> 	return uconn.buildHandshakeState(true)
98  }
```

10. `github.com/refraction-networking/utls.UConn.buildHandshakeState` calls `github.com/refraction-networking/utls.UConn.applyPresetByID` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_conn.go:129` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_conn.go#L129)

```go
128  		if uconn.clientHelloBuildStatus == NotBuilt {
129> 			err := uconn.applyPresetByID(uconn.ClientHelloID)
130  			if err != nil {
```

11. `github.com/refraction-networking/utls.UConn.applyPresetByID` calls `github.com/refraction-networking/utls.UTLSIdToSpec` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_parrots.go:2751` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_parrots.go#L2751)

```go
2750  		default:
2751> 			spec, err = UTLSIdToSpec(id)
2752  			if err != nil {
```

12. `github.com/refraction-networking/utls.UTLSIdToSpec` calls `github.com/refraction-networking/utls.utlsIdToSpec` (STATIC) at `$GOMODCACHE/github.com/refraction-networking/utls@v1.8.1/u_parrots.go:30` [source](https://github.com/refraction-networking/utls/blob/v1.8.1/u_parrots.go#L30)

```go
29  func UTLSIdToSpec(id ClientHelloID) (ClientHelloSpec, error) {
30> 	return utlsIdToSpec(id)
31  }
```


| field | value |
|---|---|
| adjudication | |
| by | |
| note | |

## Xray\-core\_\_GO\-2026\-5841

- advisory: `GO-2026-5841` OOB read in github\.com/klauspost/compress/s2
- vulnerable module: `github.com/klauspost/compress@v1.17.4`
- verdict: **NOT\_REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'NOT\_REACHABLE': 3\}
- verifier: PASSED
- adjudicate: all 4 NOT\_REACHABLE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level MODULE\)

Targets analysed (1): `github.com/klauspost/compress/s2.NewDict`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 3 |

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |

## Xray\-core\_\_GO\-2026\-6061

- advisory: `GO-2026-6061` Vulnerabilities in the xDS RBAC authorization engine and the HTTP/2 transport server implementation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.77.0`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 37
- per-symbol results: \{'CANT\_DETERMINE': 7, 'NOT\_REACHABLE': 76, 'REACHABLE': 28\}
- verifier: FAILED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): REACHABLE \(finding level SYMBOL\) via `github.com/xtls/xray-core/main.main (main/main.go:22) -> github.com/xtls/xray-core/main/commands/base.Execute (main/commands/base/execute.go:64) -> github.com/xtls/xray-core/main/commands/all/api.executeRestartLogger (main/commands/all/api/logger_restart.go:39) -> github.com/xtls/xray-core/app/log/command.loggerServiceClient.RestartLogger (app/log/command/config_grpc.pb.go:43) -> google.golang.org/grpc.ClientConn.Invoke (call.go:37) -> google.golang.org/grpc.invoke (call.go:73) -> google.golang.org/grpc.clientStream.RecvMsg (stream.go:999) -> google.golang.org/grpc.clientStream.finish (stream.go:1050) -> google.golang.org/grpc.csAttempt.finish (stream.go:1203) -> google.golang.org/grpc/internal/transport.ClientStream.Close (internal/transport/client_stream.go:65)`

Reachable targets (28): `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut`, `google.golang.org/grpc/internal/transport.controlBuffer.finish`, `google.golang.org/grpc/internal/transport.controlBuffer.getOnceLocked`, `google.golang.org/grpc/internal/transport.dataFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.earlyAbortStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.goAway.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.headerFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.incomingGoAway.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.incomingSettings.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.incomingWindowUpdate.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.loopyWriter.handle`, `google.golang.org/grpc/internal/transport.loopyWriter.headerHandler`, `google.golang.org/grpc/internal/transport.loopyWriter.originateStream`, `google.golang.org/grpc/internal/transport.outgoingSettings.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.outgoingWindowUpdate.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.ping.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.registerStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.http2Client.NewStream`, `google.golang.org/grpc/internal/transport.http2Server.finishStream`, `google.golang.org/grpc/internal/transport.http2Server.handleData`, `google.golang.org/grpc/internal/transport.http2Server.writeHeaderLocked`, `google.golang.org/grpc/internal/transport.http2Server.writeStatus`, `google.golang.org/grpc/internal/envconfig.boolFromEnv` (context only), `google.golang.org/grpc/internal/transport.itemList.isEmpty` (context only), `google.golang.org/grpc/internal/transport.loopyWriter.registerStreamHandler` (context only), `google.golang.org/grpc/internal/transport.http2Server.deleteStream` (context only)

### Path 1: `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` (DYNAMIC) at `main/commands/base/execute.go:64` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L64)

```go
63  			buildCommandText(cmd)
64> 			cmd.Run(cmd, args)
65  			Exit()
```

3. `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` calls `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` (DYNAMIC) at `main/commands/all/api/inbound_user_add.go:48` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/inbound_user_add.go#L48)

```go
47  	conn, ctx, close := dialAPIServer()
48> 	defer close()
49  	client := handlerService.NewHandlerServiceClient(conn)
```

4. `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` calls `google.golang.org/grpc.ClientConn.Close` (STATIC) at `main/commands/all/api/shared.go:49` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/shared.go#L49)

```go
48  		cancel()
49> 		conn.Close()
50  	}
```

5. `google.golang.org/grpc.ClientConn.Close` calls `google.golang.org/grpc.ClientConn.Close$2` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1173`

```go
1172  		wg.Add(1)
1173> 		go func(ac *addrConn) {
1174  			defer wg.Done()
```

6. `google.golang.org/grpc.ClientConn.Close$2` calls `google.golang.org/grpc.addrConn.tearDown` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1175`

```go
1174  			defer wg.Done()
1175> 			ac.tearDown(ErrClientConnClosing)
1176  		}(ac)
```

7. `google.golang.org/grpc.addrConn.tearDown` calls `google.golang.org/grpc/internal/transport.http2Client.Close` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1589`

```go
1588  			// unconditionally here.
1589> 			curTr.Close(err)
1590  		}
```

8. `google.golang.org/grpc/internal/transport.http2Client.Close` calls `google.golang.org/grpc/internal/transport.controlBuffer.put` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/http2_client.go:1030`

```go
1029  	// just stuck.
1030> 	t.controlBuf.put(&goAway{code: http2.ErrCodeNo, debugData: []byte("client transport shutdown"), closeConn: err})
1031  	timer := time.NewTimer(goAwayLoopyWriterTimeout)
```

9. `google.golang.org/grpc/internal/transport.controlBuffer.put` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/controlbuf.go:354`

```go
353  func (c *controlBuffer) put(it cbItem) error {
354> 	_, err := c.executeAndPut(nil, it)
355  	return err
```

10. `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` calls `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/controlbuf.go:387`

```go
386  	c.list.enqueue(it)
387> 	if it.isTransportResponseFrame() {
388  		c.transportResponseFrames++
```


### Path 2: `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` (DYNAMIC) at `main/commands/base/execute.go:64` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L64)

```go
63  			buildCommandText(cmd)
64> 			cmd.Run(cmd, args)
65  			Exit()
```

3. `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` calls `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` (DYNAMIC) at `main/commands/all/api/inbound_user_add.go:48` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/inbound_user_add.go#L48)

```go
47  	conn, ctx, close := dialAPIServer()
48> 	defer close()
49  	client := handlerService.NewHandlerServiceClient(conn)
```

4. `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` calls `google.golang.org/grpc.ClientConn.Close` (STATIC) at `main/commands/all/api/shared.go:49` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/shared.go#L49)

```go
48  		cancel()
49> 		conn.Close()
50  	}
```

5. `google.golang.org/grpc.ClientConn.Close` calls `google.golang.org/grpc.ClientConn.Close$2` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1173`

```go
1172  		wg.Add(1)
1173> 		go func(ac *addrConn) {
1174  			defer wg.Done()
```

6. `google.golang.org/grpc.ClientConn.Close$2` calls `google.golang.org/grpc.addrConn.tearDown` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1175`

```go
1174  			defer wg.Done()
1175> 			ac.tearDown(ErrClientConnClosing)
1176  		}(ac)
```

7. `google.golang.org/grpc.addrConn.tearDown` calls `google.golang.org/grpc/internal/transport.http2Client.Close` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1589`

```go
1588  			// unconditionally here.
1589> 			curTr.Close(err)
1590  		}
```

8. `google.golang.org/grpc/internal/transport.http2Client.Close` calls `google.golang.org/grpc/internal/transport.controlBuffer.put` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/http2_client.go:1030`

```go
1029  	// just stuck.
1030> 	t.controlBuf.put(&goAway{code: http2.ErrCodeNo, debugData: []byte("client transport shutdown"), closeConn: err})
1031  	timer := time.NewTimer(goAwayLoopyWriterTimeout)
```

9. `google.golang.org/grpc/internal/transport.controlBuffer.put` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/controlbuf.go:354`

```go
353  func (c *controlBuffer) put(it cbItem) error {
354> 	_, err := c.executeAndPut(nil, it)
355  	return err
```

10. `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` calls `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/controlbuf.go:387`

```go
386  	c.list.enqueue(it)
387> 	if it.isTransportResponseFrame() {
388  		c.transportResponseFrames++
```


### Path 3: `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` from `github.com/xtls/xray-core/main`

Target context only (no line of it changed in the fix, it touched diff context): False

1. `github.com/xtls/xray-core/main.main` calls `github.com/xtls/xray-core/main/commands/base.Execute` (STATIC) at `main/main.go:22` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/main.go#L22)

```go
21  	)
22> 	base.Execute()
23  }
```

2. `github.com/xtls/xray-core/main/commands/base.Execute` calls `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` (DYNAMIC) at `main/commands/base/execute.go:64` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/base/execute.go#L64)

```go
63  			buildCommandText(cmd)
64> 			cmd.Run(cmd, args)
65  			Exit()
```

3. `github.com/xtls/xray-core/main/commands/all/api.executeAddInboundUsers` calls `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` (DYNAMIC) at `main/commands/all/api/inbound_user_add.go:48` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/inbound_user_add.go#L48)

```go
47  	conn, ctx, close := dialAPIServer()
48> 	defer close()
49  	client := handlerService.NewHandlerServiceClient(conn)
```

4. `github.com/xtls/xray-core/main/commands/all/api.dialAPIServer$1` calls `google.golang.org/grpc.ClientConn.Close` (STATIC) at `main/commands/all/api/shared.go:49` [source](https://github.com/XTLS/Xray-core/blob/81f8f398c7b2b845853b1e85087c6122acc6db0b/main/commands/all/api/shared.go#L49)

```go
48  		cancel()
49> 		conn.Close()
50  	}
```

5. `google.golang.org/grpc.ClientConn.Close` calls `google.golang.org/grpc.ClientConn.Close$2` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1173`

```go
1172  		wg.Add(1)
1173> 		go func(ac *addrConn) {
1174  			defer wg.Done()
```

6. `google.golang.org/grpc.ClientConn.Close$2` calls `google.golang.org/grpc.addrConn.tearDown` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1175`

```go
1174  			defer wg.Done()
1175> 			ac.tearDown(ErrClientConnClosing)
1176  		}(ac)
```

7. `google.golang.org/grpc.addrConn.tearDown` calls `google.golang.org/grpc/internal/transport.http2Client.Close` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/clientconn.go:1589`

```go
1588  			// unconditionally here.
1589> 			curTr.Close(err)
1590  		}
```

8. `google.golang.org/grpc/internal/transport.http2Client.Close` calls `google.golang.org/grpc/internal/transport.controlBuffer.put` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/http2_client.go:1030`

```go
1029  	// just stuck.
1030> 	t.controlBuf.put(&goAway{code: http2.ErrCodeNo, debugData: []byte("client transport shutdown"), closeConn: err})
1031  	timer := time.NewTimer(goAwayLoopyWriterTimeout)
```

9. `google.golang.org/grpc/internal/transport.controlBuffer.put` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.77.0/internal/transport/controlbuf.go:354`

```go
353  func (c *controlBuffer) put(it cbItem) error {
354> 	_, err := c.executeAndPut(nil, it)
355  	return err
```


25 more reachable target(s); see the verdict file.

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
