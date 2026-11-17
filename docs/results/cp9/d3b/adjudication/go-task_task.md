# CP9 adjudication (D3b, held-out): github\.com/go\-task/task

- application: `github.com/go-task/task` at tag `v3.46.4`, commit `179bde1f37561b0d5e96e99688de735ce9eef05c`
- cases to adjudicate: 2 (every case REACHABLE in either run)

How to adjudicate (the same text for every case; the CP7b method):

- Judge **reachability**, not exploitability. Every case below was REACHABLE without the filter.
- `adjudication_off`: path A (the verified path without the filter): `CORRECT` if every step is a real call that can
  run in the application; `INFEASIBLE_PATH` if the calls exist but the path cannot run as a whole; `WRONG` if a step
  does not exist or does not call the next function; `CANNOT_JUDGE` otherwise.
- `adjudication_on`: only if the case is still REACHABLE with the filter: the same judgement for path B (the path that
  passed the filter). `SAME_AS_OFF` is pre-filled by code when path B is path A.
- `steps_correct`: only if the filter downgraded the case: are the reported infeasible steps really impossible for the
  stated reason? `YES`, `NO`, `PARTLY` or `CANNOT_JUDGE`.
- `truth`: is the target (any listed reachable target) reachable from a `main` package by **some** path, reading the
  code? `REACHABLE`, `NOT_REACHABLE` or `UNKNOWN`. For a downgraded case, `REACHABLE` means the filter hid a real path
  (a miss).
- `by`: who adjudicated; `note`: one or two sentences. Set `filled` to true when the case is done.
- Fill `adjudication.json`; the Markdown files are for reading.

## task\_\_GO\-2026\-6348

- advisory: `GO-2026-6348` Heap Memory Exhaustion \(OOM\) via HTTP/2 DATA Frame Fragmentation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.56.3`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 4\}

### Path A (without the filter): `google.golang.org/grpc/internal/transport.http2Client.newStream` from `github.com/go-task/task/v3/cmd/task`

1. `github.com/go-task/task/v3/cmd/task.main` calls `github.com/go-task/task/v3/cmd/task.run` (STATIC) at `cmd/task/task.go:24` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L24)

```go
23  func main() {
24> 	if err := run(); err != nil {
25  		l := &logger.Logger{
```

2. `github.com/go-task/task/v3/cmd/task.run` calls `github.com/go-task/task/v3.Executor.Status` (STATIC) at `cmd/task/task.go:199` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L199)

```go
198  	if flags.Status {
199> 		return e.Status(ctx, calls...)
200  	}
```

3. `github.com/go-task/task/v3.Executor.Status` calls `github.com/go-task/task/v3/internal/fingerprint.IsTaskUpToDate` (STATIC) at `status.go:28` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/status.go#L28)

```go
27  		// Check if the task is up-to-date
28> 		isUpToDate, err := fingerprint.IsTaskUpToDate(ctx, t,
29  			fingerprint.WithMethod(method),
```

4. `github.com/go-task/task/v3/internal/fingerprint.IsTaskUpToDate` calls `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.IsUpToDate` (DYNAMIC) at `internal/fingerprint/task.go:108` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/task.go#L108)

```go
107  	if sourcesIsSet {
108> 		sourcesUpToDate, err = config.sourcesChecker.IsUpToDate(t)
109  		if err != nil {
```

5. `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.IsUpToDate` calls `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.checksum` (STATIC) at `internal/fingerprint/sources_checksum.go:41` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/sources_checksum.go#L41)

```go
40  
41> 	newHash, err := checker.checksum(t)
42  	if err != nil {
```

6. `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.checksum` calls `io.CopyBuffer` (STATIC) at `internal/fingerprint/sources_checksum.go:100` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/sources_checksum.go#L100)

```go
 99  		// also sum the filename, so checksum changes for renaming a file
100> 		if _, err := io.CopyBuffer(h, strings.NewReader(filepath.Base(f)), buf); err != nil {
101  			return "", err
```

7. `io.CopyBuffer` calls `io.copyBuffer` (STATIC) at `$GOROOT/src/io/io.go:402` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L402)

```go
401  	}
402> 	return copyBuffer(dst, src, buf)
403  }
```

8. `io.copyBuffer` calls `cloud.google.com/go/storage.Reader.Read` (DYNAMIC) at `$GOROOT/src/io/io.go:429` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L429)

```go
428  	for {
429> 		nr, er := src.Read(buf)
430  		if nr > 0 {
```

9. `cloud.google.com/go/storage.Reader.Read` calls `cloud.google.com/go/storage.gRPCReader.Read` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/reader.go:207`

```go
206  func (r *Reader) Read(p []byte) (int, error) {
207> 	n, err := r.reader.Read(p)
208  	if r.remain != -1 {
```

10. `cloud.google.com/go/storage.gRPCReader.Read` calls `cloud.google.com/go/storage.gRPCReader.recv` (STATIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/grpc_client.go:1365`

```go
1364  	// Attempt to Recv the next message on the stream.
1365> 	msg, err := r.recv()
1366  	if err != nil {
```

11. `cloud.google.com/go/storage.gRPCReader.recv` calls `cloud.google.com/go/storage/internal/apiv2/stubs.storageReadObjectClient.Recv` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/grpc_client.go:1411`

```go
1410  func (r *gRPCReader) recv() (*storagepb.ReadObjectResponse, error) {
1411> 	msg, err := r.stream.Recv()
1412  	var shouldRetry = ShouldRetry
```

12. `cloud.google.com/go/storage/internal/apiv2/stubs.storageReadObjectClient.Recv` calls `google.golang.org/grpc.clientStream.RecvMsg` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/internal/apiv2/stubs/storage.pb.go:9681`

```go
9680  	m := new(ReadObjectResponse)
9681> 	if err := x.ClientStream.RecvMsg(m); err != nil {
9682  		return nil, err
```

13. `google.golang.org/grpc.clientStream.RecvMsg` calls `google.golang.org/grpc.clientStream.withRetry` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:916`

```go
915  	}
916> 	err := cs.withRetry(func(a *csAttempt) error {
917  		return a.recvMsg(m, recvInfo)
```

14. `google.golang.org/grpc.clientStream.withRetry` calls `google.golang.org/grpc.newClientStreamWithParams$2` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:752`

```go
751  			// already be status errors.
752> 			return toRPCErr(op(cs.attempt))
753  		}
```

15. `google.golang.org/grpc.newClientStreamWithParams$2` calls `google.golang.org/grpc.csAttempt.newStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:344`

```go
343  		}
344> 		if err := a.newStream(); err != nil {
345  			return err
```

16. `google.golang.org/grpc.csAttempt.newStream` calls `google.golang.org/grpc/internal/transport.http2Client.NewStream` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:494`

```go
493  
494> 	s, err := a.t.NewStream(a.ctx, cs.callHdr)
495  	if err != nil {
```

17. `google.golang.org/grpc/internal/transport.http2Client.NewStream` calls `google.golang.org/grpc/internal/transport.http2Client.newStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:721`

```go
720  	}
721> 	s := t.newStream(ctx, callHdr)
722  	cleanup := func(err error) {
```


### Path B (the path that passed the filter): `google.golang.org/grpc/internal/transport.http2Client.newStream`

1. `github.com/go-task/task/v3/cmd/task.main` calls `github.com/go-task/task/v3/cmd/task.run` (STATIC) at `cmd/task/task.go:24` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L24)

```go
23  func main() {
24> 	if err := run(); err != nil {
25  		l := &logger.Logger{
```

2. `github.com/go-task/task/v3/cmd/task.run` calls `github.com/go-task/task/v3.Executor.Status` (STATIC) at `cmd/task/task.go:199` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L199)

```go
198  	if flags.Status {
199> 		return e.Status(ctx, calls...)
200  	}
```

3. `github.com/go-task/task/v3.Executor.Status` calls `github.com/go-task/task/v3/internal/fingerprint.IsTaskUpToDate` (STATIC) at `status.go:28` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/status.go#L28)

```go
27  		// Check if the task is up-to-date
28> 		isUpToDate, err := fingerprint.IsTaskUpToDate(ctx, t,
29  			fingerprint.WithMethod(method),
```

4. `github.com/go-task/task/v3/internal/fingerprint.IsTaskUpToDate` calls `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.IsUpToDate` (DYNAMIC) at `internal/fingerprint/task.go:108` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/task.go#L108)

```go
107  	if sourcesIsSet {
108> 		sourcesUpToDate, err = config.sourcesChecker.IsUpToDate(t)
109  		if err != nil {
```

5. `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.IsUpToDate` calls `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.checksum` (STATIC) at `internal/fingerprint/sources_checksum.go:41` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/sources_checksum.go#L41)

```go
40  
41> 	newHash, err := checker.checksum(t)
42  	if err != nil {
```

6. `github.com/go-task/task/v3/internal/fingerprint.ChecksumChecker.checksum` calls `io.CopyBuffer` (STATIC) at `internal/fingerprint/sources_checksum.go:100` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/fingerprint/sources_checksum.go#L100)

```go
 99  		// also sum the filename, so checksum changes for renaming a file
100> 		if _, err := io.CopyBuffer(h, strings.NewReader(filepath.Base(f)), buf); err != nil {
101  			return "", err
```

7. `io.CopyBuffer` calls `io.copyBuffer` (STATIC) at `$GOROOT/src/io/io.go:402` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L402)

```go
401  	}
402> 	return copyBuffer(dst, src, buf)
403  }
```

8. `io.copyBuffer` calls `bufio.Reader.WriteTo` (DYNAMIC) at `$GOROOT/src/io/io.go:411` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L411)

```go
410  	if wt, ok := src.(WriterTo); ok {
411> 		return wt.WriteTo(dst)
412  	}
```

9. `bufio.Reader.WriteTo` calls `bufio.Writer.ReadFrom` (DYNAMIC) at `$GOROOT/src/bufio/bufio.go:533` [source](https://github.com/golang/go/blob/go1.26.10/src/bufio/bufio.go#L533)

```go
532  	if w, ok := w.(io.ReaderFrom); ok {
533> 		m, err := w.ReadFrom(b.rd)
534  		n += m
```

10. `bufio.Writer.ReadFrom` calls `cloud.google.com/go/storage.Reader.Read` (DYNAMIC) at `$GOROOT/src/bufio/bufio.go:804` [source](https://github.com/golang/go/blob/go1.26.10/src/bufio/bufio.go#L804)

```go
803  		for nr < maxConsecutiveEmptyReads {
804> 			m, err = r.Read(b.buf[b.n:])
805  			if m != 0 || err != nil {
```

11. `cloud.google.com/go/storage.Reader.Read` calls `cloud.google.com/go/storage.gRPCReader.Read` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/reader.go:207`

```go
206  func (r *Reader) Read(p []byte) (int, error) {
207> 	n, err := r.reader.Read(p)
208  	if r.remain != -1 {
```

12. `cloud.google.com/go/storage.gRPCReader.Read` calls `cloud.google.com/go/storage.gRPCReader.recv` (STATIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/grpc_client.go:1365`

```go
1364  	// Attempt to Recv the next message on the stream.
1365> 	msg, err := r.recv()
1366  	if err != nil {
```

13. `cloud.google.com/go/storage.gRPCReader.recv` calls `cloud.google.com/go/storage/internal/apiv2/stubs.storageReadObjectClient.Recv` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/grpc_client.go:1411`

```go
1410  func (r *gRPCReader) recv() (*storagepb.ReadObjectResponse, error) {
1411> 	msg, err := r.stream.Recv()
1412  	var shouldRetry = ShouldRetry
```

14. `cloud.google.com/go/storage/internal/apiv2/stubs.storageReadObjectClient.Recv` calls `google.golang.org/grpc.clientStream.RecvMsg` (DYNAMIC) at `$GOMODCACHE/cloud.google.com/go/storage@v1.29.0/internal/apiv2/stubs/storage.pb.go:9681`

```go
9680  	m := new(ReadObjectResponse)
9681> 	if err := x.ClientStream.RecvMsg(m); err != nil {
9682  		return nil, err
```

15. `google.golang.org/grpc.clientStream.RecvMsg` calls `google.golang.org/grpc.clientStream.withRetry` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:916`

```go
915  	}
916> 	err := cs.withRetry(func(a *csAttempt) error {
917  		return a.recvMsg(m, recvInfo)
```

16. `google.golang.org/grpc.clientStream.withRetry` calls `google.golang.org/grpc.clientStream.retryLocked` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:782`

```go
781  		}
782> 		if err := cs.retryLocked(a, err); err != nil {
783  			cs.mu.Unlock()
```

17. `google.golang.org/grpc.clientStream.retryLocked` calls `google.golang.org/grpc.clientStream.replayBufferLocked` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:727`

```go
726  		// if it is able to pick a transport and create a stream.
727> 		if lastErr = cs.replayBufferLocked(attempt); lastErr == nil {
728  			return nil
```

18. `google.golang.org/grpc.clientStream.replayBufferLocked` calls `google.golang.org/grpc.newClientStreamWithParams$2` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:843`

```go
842  	for _, f := range cs.buffer {
843> 		if err := f(attempt); err != nil {
844  			return err
```

19. `google.golang.org/grpc.newClientStreamWithParams$2` calls `google.golang.org/grpc.csAttempt.newStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:344`

```go
343  		}
344> 		if err := a.newStream(); err != nil {
345  			return err
```

20. `google.golang.org/grpc.csAttempt.newStream` calls `google.golang.org/grpc/internal/transport.http2Client.NewStream` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/stream.go:494`

```go
493  
494> 	s, err := a.t.NewStream(a.ctx, cs.callHdr)
495  	if err != nil {
```

21. `google.golang.org/grpc/internal/transport.http2Client.NewStream` calls `google.golang.org/grpc/internal/transport.http2Client.newStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:721`

```go
720  	}
721> 	s := t.newStream(ctx, callHdr)
722  	cleanup := func(err error) {
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |

## task\_\_GO\-2026\-6061

- advisory: `GO-2026-6061` Vulnerabilities in the xDS RBAC authorization engine and the HTTP/2 transport server implementation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.56.3`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 20\}

### Path A (without the filter): `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame` from `github.com/go-task/task/v3/cmd/task`

1. `github.com/go-task/task/v3/cmd/task.main` calls `github.com/go-task/task/v3/cmd/task.emitCIErrorAnnotation` (STATIC) at `cmd/task/task.go:32` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L32)

```go
31  		if err, ok := err.(*errors.TaskRunError); ok && flags.ExitCode {
32> 			emitCIErrorAnnotation(err)
33  			l.Errf(logger.Red, "%v\n", err)
```

2. `github.com/go-task/task/v3/cmd/task.emitCIErrorAnnotation` calls `fmt.Fprintf` (STATIC) at `cmd/task/task.go:54` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L54)

```go
53  	if e, ok := err.(*errors.TaskRunError); ok {
54> 		fmt.Fprintf(os.Stdout, "::error title=Task '%s' failed::%v\n", e.TaskName, e.Err)
55  		return
```

3. `fmt.Fprintf` calls `crypto/tls.Conn.Write` (DYNAMIC) at `$GOROOT/src/fmt/print.go:225` [source](https://github.com/golang/go/blob/go1.26.10/src/fmt/print.go#L225)

```go
224  	p.doPrintf(format, a)
225> 	n, err = w.Write(p.buf)
226  	p.free()
```

4. `crypto/tls.Conn.Write` calls `crypto/tls.Conn.writeRecordLocked` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:1246` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L1246)

```go
1245  		if _, ok := c.out.cipher.(cipher.BlockMode); ok {
1246> 			n, err := c.writeRecordLocked(recordTypeApplicationData, b[:1])
1247  			if err != nil {
```

5. `crypto/tls.Conn.writeRecordLocked` calls `crypto/tls.halfConn.encrypt` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:1031` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L1031)

```go
1030  		var err error
1031> 		outBuf, err = c.out.encrypt(outBuf, data[:m], c.config.rand())
1032  		if err != nil {
```

6. `crypto/tls.halfConn.encrypt` calls `io.ReadFull` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:499` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L499)

```go
498  		} else {
499> 			if _, err := io.ReadFull(rand, explicitNonce); err != nil {
500  				return nil, err
```

7. `io.ReadFull` calls `io.ReadAtLeast` (STATIC) at `$GOROOT/src/io/io.go:354` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L354)

```go
353  func ReadFull(r Reader, buf []byte) (n int, err error) {
354> 	return ReadAtLeast(r, buf, len(buf))
355  }
```

8. `io.ReadAtLeast` calls `google.golang.org/grpc/internal/transport.transportReader.Read` (DYNAMIC) at `$GOROOT/src/io/io.go:335` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L335)

```go
334  		var nn int
335> 		nn, err = r.Read(buf[n:])
336  		n += nn
```

9. `google.golang.org/grpc/internal/transport.transportReader.Read` calls `google.golang.org/grpc/internal/transport.http2Client.newStream$3` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/transport.go:519`

```go
518  	}
519> 	t.windowHandler(n)
520  	return
```

10. `google.golang.org/grpc/internal/transport.http2Client.newStream$3` calls `google.golang.org/grpc/internal/transport.http2Client.updateWindow` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:488`

```go
487  		windowHandler: func(n int) {
488> 			t.updateWindow(s, uint32(n))
489  		},
```

11. `google.golang.org/grpc/internal/transport.http2Client.updateWindow` calls `google.golang.org/grpc/internal/transport.controlBuffer.put` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:1075`

```go
1074  	if w := s.fc.onRead(n); w > 0 {
1075> 		t.controlBuf.put(&outgoingWindowUpdate{streamID: s.id, increment: w})
1076  	}
```

12. `google.golang.org/grpc/internal/transport.controlBuffer.put` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/controlbuf.go:335`

```go
334  func (c *controlBuffer) put(it cbItem) error {
335> 	_, err := c.executeAndPut(nil, it)
336  	return err
```

13. `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` calls `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/controlbuf.go:357`

```go
356  	c.list.enqueue(it)
357> 	if it.isTransportResponseFrame() {
358  		c.transportResponseFrames++
```


### Path B (the path that passed the filter): `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame`

1. `github.com/go-task/task/v3/cmd/task.main` calls `github.com/go-task/task/v3/internal/logger.Logger.Errf` (STATIC) at `cmd/task/task.go:33` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/cmd/task/task.go#L33)

```go
32  			emitCIErrorAnnotation(err)
33> 			l.Errf(logger.Red, "%v\n", err)
34  			os.Exit(err.TaskExitCode())
```

2. `github.com/go-task/task/v3/internal/logger.Logger.Errf` calls `github.com/fatih/color.Color.FprintfFunc$1` (DYNAMIC) at `internal/logger/logger.go:169` [source](https://github.com/go-task/task/blob/179bde1f37561b0d5e96e99688de735ce9eef05c/internal/logger/logger.go#L169)

```go
168  	print := color()
169> 	print(l.Stderr, s, args...)
170  }
```

3. `github.com/fatih/color.Color.FprintfFunc$1` calls `github.com/fatih/color.Color.Fprintf` (STATIC) at `$GOMODCACHE/github.com/fatih/color@v1.18.0/color.go:349` [source](https://github.com/fatih/color/blob/v1.18.0/color.go#L349)

```go
348  	return func(w io.Writer, format string, a ...interface{}) {
349> 		c.Fprintf(w, format, a...)
350  	}
```

4. `github.com/fatih/color.Color.Fprintf` calls `fmt.Fprintf` (STATIC) at `$GOMODCACHE/github.com/fatih/color@v1.18.0/color.go:284` [source](https://github.com/fatih/color/blob/v1.18.0/color.go#L284)

```go
283  
284> 	return fmt.Fprintf(w, format, a...)
285  }
```

5. `fmt.Fprintf` calls `crypto/tls.Conn.Write` (DYNAMIC) at `$GOROOT/src/fmt/print.go:225` [source](https://github.com/golang/go/blob/go1.26.10/src/fmt/print.go#L225)

```go
224  	p.doPrintf(format, a)
225> 	n, err = w.Write(p.buf)
226  	p.free()
```

6. `crypto/tls.Conn.Write` calls `crypto/tls.Conn.writeRecordLocked` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:1246` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L1246)

```go
1245  		if _, ok := c.out.cipher.(cipher.BlockMode); ok {
1246> 			n, err := c.writeRecordLocked(recordTypeApplicationData, b[:1])
1247  			if err != nil {
```

7. `crypto/tls.Conn.writeRecordLocked` calls `crypto/tls.halfConn.encrypt` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:1031` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L1031)

```go
1030  		var err error
1031> 		outBuf, err = c.out.encrypt(outBuf, data[:m], c.config.rand())
1032  		if err != nil {
```

8. `crypto/tls.halfConn.encrypt` calls `io.ReadFull` (STATIC) at `$GOROOT/src/crypto/tls/conn.go:499` [source](https://github.com/golang/go/blob/go1.26.10/src/crypto/tls/conn.go#L499)

```go
498  		} else {
499> 			if _, err := io.ReadFull(rand, explicitNonce); err != nil {
500  				return nil, err
```

9. `io.ReadFull` calls `io.ReadAtLeast` (STATIC) at `$GOROOT/src/io/io.go:354` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L354)

```go
353  func ReadFull(r Reader, buf []byte) (n int, err error) {
354> 	return ReadAtLeast(r, buf, len(buf))
355  }
```

10. `io.ReadAtLeast` calls `google.golang.org/grpc/internal/transport.transportReader.Read` (DYNAMIC) at `$GOROOT/src/io/io.go:335` [source](https://github.com/golang/go/blob/go1.26.10/src/io/io.go#L335)

```go
334  		var nn int
335> 		nn, err = r.Read(buf[n:])
336  		n += nn
```

11. `google.golang.org/grpc/internal/transport.transportReader.Read` calls `google.golang.org/grpc/internal/transport.recvBufferReader.Read` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/transport.go:514`

```go
513  func (t *transportReader) Read(p []byte) (n int, err error) {
514> 	n, err = t.reader.Read(p)
515  	if err != nil {
```

12. `google.golang.org/grpc/internal/transport.recvBufferReader.Read` calls `google.golang.org/grpc/internal/transport.recvBufferReader.readClient` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/transport.go:175`

```go
174  	if r.closeStream != nil {
175> 		n, r.err = r.readClient(p)
176  	} else {
```

13. `google.golang.org/grpc/internal/transport.recvBufferReader.readClient` calls `google.golang.org/grpc/internal/transport.http2Client.newStream$2` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/transport.go:210`

```go
209  		// faster.
210> 		r.closeStream(ContextErr(r.ctx.Err()))
211  		m := <-r.recv.get()
```

14. `google.golang.org/grpc/internal/transport.http2Client.newStream$2` calls `google.golang.org/grpc/internal/transport.http2Client.CloseStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:483`

```go
482  			closeStream: func(err error) {
483> 				t.CloseStream(s, err)
484  			},
```

15. `google.golang.org/grpc/internal/transport.http2Client.CloseStream` calls `google.golang.org/grpc/internal/transport.http2Client.closeStream` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:884`

```go
883  	}
884> 	t.closeStream(s, err, rst, rstCode, status.Convert(err), nil, false)
885  }
```

16. `google.golang.org/grpc/internal/transport.http2Client.closeStream` calls `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` (STATIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/http2_client.go:940`

```go
939  	}
940> 	t.controlBuf.executeAndPut(addBackStreamQuota, cleanup)
941  	// This will unblock write.
```

17. `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut` calls `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame` (DYNAMIC) at `$GOMODCACHE/google.golang.org/grpc@v1.56.3/internal/transport/controlbuf.go:357`

```go
356  	c.list.enqueue(it)
357> 	if it.isTransportResponseFrame() {
358  		c.transportResponseFrames++
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |
