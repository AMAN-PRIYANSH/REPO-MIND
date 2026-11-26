# CP10 adjudication: d3\_\_XTLS\_Xray\-core

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

## Xray\-core\_\_GO\-2026\-5676

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-5676` HTTP/3 QPACK Trailer Expansion Memory Exhaustion in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.57.1`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/quic-go/quic-go/http3.ConfigureTLSConfig`, `github.com/quic-go/quic-go/http3.Error.Error`, `github.com/quic-go/quic-go/http3.RequestStream.Close`, `github.com/quic-go/quic-go/http3.RequestStream.Write`, `github.com/quic-go/quic-go/http3.Server.Close`, `github.com/quic-go/quic-go/http3.Server.ServeListener`, `github.com/quic-go/quic-go/http3.Transport.Close`, `github.com/quic-go/quic-go/http3.Transport.CloseIdleConnections`, `github.com/quic-go/quic-go/http3.Transport.RoundTrip`, `github.com/quic-go/quic-go/http3.body.Close`
- govulncheck trace: `github.com/xtls/xray-core/main.main (main/main.go:22) -> github.com/xtls/xray-core/main/commands/base.Execute (main/commands/base/execute.go:64) -> github.com/xtls/xray-core/main/commands/all/convert.executeTypedMessageToJson (main/commands/all/convert/json.go:56) -> io.ReadAll (src/io/io.go:722) -> github.com/quic-go/quic-go/http3.gzipReader.Read (http3/gzip_reader.go:23)`

Decision targets (3): `github.com/quic-go/quic-go/http3.decodeTrailers`, `github.com/quic-go/quic-go/http3.parseTrailers`, `github.com/quic-go/quic-go/http3.parseHeaders`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', True\): 3, \('NOT\_REACHABLE', True\): 4, \('REACHABLE', True\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## Xray\-core\_\_GO\-2026\-4512

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-4512` Fingerprint vulnerability in uTLS from missing padding extension for Chrome 120 in github\.com/refraction\-networking/utls
- vulnerable module: `github.com/refraction-networking/utls@v1.8.1`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/refraction-networking/utls.UConn.BuildHandshakeState`, `github.com/refraction-networking/utls.UConn.Handshake`, `github.com/refraction-networking/utls.UConn.HandshakeContext`, `github.com/refraction-networking/utls.UConn.Read`, `github.com/refraction-networking/utls.UConn.Write`
- govulncheck trace: `github.com/xtls/xray-core/infra/vprotogen.main (infra/vprotogen/main.go:199) -> fmt.Printf (src/fmt/print.go:233) -> fmt.Fprintf (src/fmt/print.go:225) -> github.com/xtls/xray-core/transport/internet/websocket.delayDialConn.Write (transport/internet/websocket/dialer.go:152) -> github.com/xtls/xray-core/transport/internet/websocket.dialWebSocket (transport/internet/websocket/dialer.go:120) -> github.com/gorilla/websocket.Dialer.DialContext (client.go:321) -> github.com/gorilla/websocket.DialContext$2 (client.go:263) -> github.com/xtls/xray-core/transport/internet/websocket.dialWebSocket$2 (transport/internet/websocket/dialer.go:76) -> github.com/xtls/xray-core/transport/internet/tls.UConn.WebsocketHandshakeContext (transport/internet/tls/tls.go:116) -> github.com/refraction-networking/utls.UConn.HandshakeContext (u_conn.go:311)`

Decision targets (1): `github.com/refraction-networking/utls.utlsIdToSpec`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 2, \('REACHABLE', True\): 1\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## Xray\-core\_\_GO\-2026\-6061

- item: truth only \(D3, in\-sample\)
- advisory: `GO-2026-6061` Vulnerabilities in the xDS RBAC authorization engine and the HTTP/2 transport server implementation in google\.golang\.org/grpc
- vulnerable module: `google.golang.org/grpc@v1.77.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **REACHABLE** 
- VulnTrace, legacy targets: **REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `google.golang.org/grpc/internal/transport.ClientStream.Close`, `google.golang.org/grpc/internal/transport.ClientStream.Header`, `google.golang.org/grpc/internal/transport.ClientStream.Read`, `google.golang.org/grpc/internal/transport.ClientStream.RecvCompress`, `google.golang.org/grpc/internal/transport.ClientStream.TrailersOnly`, `google.golang.org/grpc/internal/transport.ClientStream.Write`, `google.golang.org/grpc/internal/transport.NewHTTP2Client`, `google.golang.org/grpc/internal/transport.NewServerTransport`, `google.golang.org/grpc/internal/transport.ServerStream.Read`, `google.golang.org/grpc/internal/transport.ServerStream.Write`
- govulncheck trace: `github.com/xtls/xray-core/infra/vprotogen.main (infra/vprotogen/main.go:199) -> fmt.Printf (src/fmt/print.go:233) -> fmt.Fprintf (src/fmt/print.go:225) -> github.com/xtls/xray-core/common/buf.BufferedWriter.Write (common/buf/writer.go:109) -> github.com/xtls/xray-core/transport/internet/grpc/encoding.HunkReaderWriter.Write (transport/internet/grpc/encoding/hunkconn.go:137) -> google.golang.org/grpc.GenericServerStream[github.com/xtls/xray-core/transport/internet/grpc/encoding.Hunk, github.com/xtls/xray-core/transport/internet/grpc/encoding.Hunk].Send (stream_interfaces.go:219) -> google.golang.org/grpc.serverStream.SendMsg (stream.go:1676) -> google.golang.org/grpc.SendMsg$1 (stream.go:1691) -> google.golang.org/grpc/internal/transport.ServerStream.WriteStatus (internal/transport/server_stream.go:76)`

Decision targets (4): `google.golang.org/grpc/internal/transport.controlBuffer.executeAndPut`, `google.golang.org/grpc/internal/transport.controlBuffer.getOnceLocked`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPrincipals`, `google.golang.org/grpc/internal/xds/rbac.matchersFromPermissions`
Extra evidence only (never decide): `google.golang.org/grpc/internal/envconfig.boolFromEnv`, `google.golang.org/grpc/internal/transport.cleanupStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.closeConnection.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.controlBuffer.finish`, `google.golang.org/grpc/internal/transport.dataFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.earlyAbortStream.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.goAway.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.headerFrame.isTransportResponseFrame`, `google.golang.org/grpc/internal/transport.http2Client.NewStream`, `google.golang.org/grpc/internal/transport.http2Client.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Client.handleData`, `google.golang.org/grpc/internal/transport.http2Server.deleteStream`, `google.golang.org/grpc/internal/transport.http2Server.finishStream`, `google.golang.org/grpc/internal/transport.http2Server.getOutFlowWindow`, `google.golang.org/grpc/internal/transport.http2Server.handleData` and 18 more
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 7, \('NOT\_REACHABLE', False\): 66, \('NOT\_REACHABLE', True\): 10, \('REACHABLE', False\): 26, \('REACHABLE', True\): 2\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
