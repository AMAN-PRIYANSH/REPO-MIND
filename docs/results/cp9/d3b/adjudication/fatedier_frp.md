# CP9 adjudication (D3b, held-out): github\.com/fatedier/frp

- application: `github.com/fatedier/frp` at tag `v0.65.0`, commit `2f5e1f79457b5e9d769f2ac063443b62640185a9`
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

## frp\_\_GO\-2026\-5543

- advisory: `GO-2026-5543` Go\-ntlmssp NTLM challenges can panic on malformed payloads in github\.com/Azure/go\-ntlmssp
- vulnerable module: `github.com/Azure/go-ntlmssp@v0.0.0-20221128193559-754e69321358`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 4\}

### Path A (without the filter): `github.com/Azure/go-ntlmssp.varField.ReadFrom` from `github.com/fatedier/frp/cmd/frpc`

1. `github.com/fatedier/frp/cmd/frpc.main` calls `github.com/fatedier/frp/cmd/frpc/sub.Execute` (STATIC) at `cmd/frpc/main.go:25` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/main.go#L25)

```go
24  	system.EnableCompatibilityMode()
25> 	sub.Execute()
26  }
```

2. `github.com/fatedier/frp/cmd/frpc/sub.Execute` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `cmd/frpc/sub/root.go:102` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L102)

```go
101  	rootCmd.SetGlobalNormalizationFunc(config.WordSepNormalizeFunc)
102> 	if err := rootCmd.Execute(); err != nil {
103  		os.Exit(1)
```

3. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1039` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1039)

```go
1038  func (c *Command) Execute() error {
1039> 	_, err := c.ExecuteC()
1040  	return err
```

4. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1115` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1115)

```go
1114  
1115> 	err = cmd.execute(flags)
1116  	if err != nil {
```

5. `github.com/spf13/cobra.Command.execute` calls `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` (DYNAMIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:987` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L987)

```go
986  	} else {
987> 		c.Run(c, argWoFlags)
988  	}
```

6. `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` calls `github.com/fatedier/frp/cmd/frpc/sub.startService` (STATIC) at `cmd/frpc/sub/proxy.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/proxy.go#L91)

```go
90  			}
91> 			err := startService(clientCfg, []v1.ProxyConfigurer{c}, nil, "")
92  			if err != nil {
```

7. `github.com/fatedier/frp/cmd/frpc/sub.startService` calls `github.com/fatedier/frp/client.Service.Run` (STATIC) at `cmd/frpc/sub/root.go:167` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L167)

```go
166  	}
167> 	return svr.Run(context.Background())
168  }
```

8. `github.com/fatedier/frp/client.Service.Run` calls `github.com/fatedier/frp/client.Service.keepControllerWorking` (STATIC) at `client/service.go:219` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L219)

```go
218  
219> 	go svr.keepControllerWorking()
220
```

9. `github.com/fatedier/frp/client.Service.keepControllerWorking` calls `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` (STATIC) at `client/service.go:233` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L233)

```go
232  	// The maximum interval is 20 seconds.
233> 	wait.BackoffUntil(func() (bool, error) {
234  		// loopLoginUntilSuccess is another layer of loop that will continuously attempt to
```

10. `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` (DYNAMIC) at `pkg/util/wait/backoff.go:133` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/pkg/util/wait/backoff.go#L133)

```go
132  
133> 		if done, err := f(); done {
134  			return
```

11. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` calls `github.com/fatedier/frp/client.Service.login` (STATIC) at `client/service.go:326` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L326)

```go
325  		xl.Infof("try to connect to server...")
326> 		conn, connector, err := svr.login()
327  		if err != nil {
```

12. `github.com/fatedier/frp/client.Service.login` calls `github.com/fatedier/frp/client.defaultConnectorImpl.Connect` (DYNAMIC) at `client/service.go:273` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L273)

```go
272  
273> 	conn, err = connector.Connect()
274  	if err != nil {
```

13. `github.com/fatedier/frp/client.defaultConnectorImpl.Connect` calls `github.com/fatedier/frp/client.defaultConnectorImpl.realConnect` (STATIC) at `client/connector.go:144` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L144)

```go
143  
144> 	return c.realConnect()
145  }
```

14. `github.com/fatedier/frp/client.defaultConnectorImpl.realConnect` calls `github.com/fatedier/golib/net.DialContext` (STATIC) at `client/connector.go:209` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L209)

```go
208  	)
209> 	conn, err := libnet.DialContext(
210  		c.ctx,
```

15. `github.com/fatedier/golib/net.DialContext` calls `github.com/fatedier/golib/net.WithProxy$1$3` (DYNAMIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial.go:80` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial.go#L80)

```go
79  	for _, v := range op.afterHooks {
80> 		ctx, c, err = v.Hook(ctx, c, addr)
81  		if err != nil {
```

16. `github.com/fatedier/golib/net.WithProxy$1$3` calls `github.com/fatedier/golib/net.ntlmHTTPProxyAfterHook` (STATIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial_option.go:142` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial_option.go#L142)

```go
141  			hook = func(ctx context.Context, c net.Conn, addr string) (context.Context, net.Conn, error) {
142> 				conn, err := ntlmHTTPProxyAfterHook(ctx, c, addr)
143  				return ctx, conn, err
```

17. `github.com/fatedier/golib/net.ntlmHTTPProxyAfterHook` calls `github.com/Azure/go-ntlmssp.ProcessChallenge` (STATIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial_option.go:318` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial_option.go#L318)

```go
317  			}
318> 			authenticateMessage, err := ntlmssp.ProcessChallenge(challengeMessage, username, proxyAuth.Passwd, domainNeeded)
319  			if err != nil {
```

18. `github.com/Azure/go-ntlmssp.ProcessChallenge` calls `github.com/Azure/go-ntlmssp.challengeMessage.UnmarshalBinary` (STATIC) at `$GOMODCACHE/github.com/!azure/go-ntlmssp@v0.0.0-20221128193559-754e69321358/authenticate_message.go:91` [source](https://github.com/Azure/go-ntlmssp/blob/754e69321358/authenticate_message.go#L91)

```go
90  	var cm challengeMessage
91> 	if err := cm.UnmarshalBinary(challengeMessageData); err != nil {
92  		return nil, err
```

19. `github.com/Azure/go-ntlmssp.challengeMessage.UnmarshalBinary` calls `github.com/Azure/go-ntlmssp.varField.ReadFrom` (STATIC) at `$GOMODCACHE/github.com/!azure/go-ntlmssp@v0.0.0-20221128193559-754e69321358/challenge_message.go:47` [source](https://github.com/Azure/go-ntlmssp/blob/754e69321358/challenge_message.go#L47)

```go
46  	if m.challengeMessageFields.TargetInfo.Len > 0 {
47> 		d, err := m.challengeMessageFields.TargetInfo.ReadFrom(data)
48  		m.TargetInfoRaw = d
```


### Path B (the path that passed the filter): `github.com/Azure/go-ntlmssp.varField.ReadFrom`

1. `github.com/fatedier/frp/cmd/frpc.main` calls `github.com/fatedier/frp/cmd/frpc/sub.Execute` (STATIC) at `cmd/frpc/main.go:25` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/main.go#L25)

```go
24  	system.EnableCompatibilityMode()
25> 	sub.Execute()
26  }
```

2. `github.com/fatedier/frp/cmd/frpc/sub.Execute` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `cmd/frpc/sub/root.go:102` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L102)

```go
101  	rootCmd.SetGlobalNormalizationFunc(config.WordSepNormalizeFunc)
102> 	if err := rootCmd.Execute(); err != nil {
103  		os.Exit(1)
```

3. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1039` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1039)

```go
1038  func (c *Command) Execute() error {
1039> 	_, err := c.ExecuteC()
1040  	return err
```

4. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1115` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1115)

```go
1114  
1115> 	err = cmd.execute(flags)
1116  	if err != nil {
```

5. `github.com/spf13/cobra.Command.execute` calls `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` (DYNAMIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:987` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L987)

```go
986  	} else {
987> 		c.Run(c, argWoFlags)
988  	}
```

6. `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` calls `github.com/fatedier/frp/cmd/frpc/sub.startService` (STATIC) at `cmd/frpc/sub/proxy.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/proxy.go#L91)

```go
90  			}
91> 			err := startService(clientCfg, []v1.ProxyConfigurer{c}, nil, "")
92  			if err != nil {
```

7. `github.com/fatedier/frp/cmd/frpc/sub.startService` calls `github.com/fatedier/frp/client.Service.Run` (STATIC) at `cmd/frpc/sub/root.go:167` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L167)

```go
166  	}
167> 	return svr.Run(context.Background())
168  }
```

8. `github.com/fatedier/frp/client.Service.Run` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess` (STATIC) at `client/service.go:212` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L212)

```go
211  	// first login to frps
212> 	svr.loopLoginUntilSuccess(10*time.Second, lo.FromPtr(svr.common.LoginFailExit))
213  	if svr.ctl == nil {
```

9. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess` calls `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` (STATIC) at `client/service.go:371` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L371)

```go
370  	// try to reconnect to server until success
371> 	wait.BackoffUntil(loginFunc, wait.NewFastBackoffManager(
372  		wait.FastBackoffOptions{
```

10. `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` (DYNAMIC) at `pkg/util/wait/backoff.go:133` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/pkg/util/wait/backoff.go#L133)

```go
132  
133> 		if done, err := f(); done {
134  			return
```

11. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` calls `github.com/fatedier/frp/client.Service.login` (STATIC) at `client/service.go:326` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L326)

```go
325  		xl.Infof("try to connect to server...")
326> 		conn, connector, err := svr.login()
327  		if err != nil {
```

12. `github.com/fatedier/frp/client.Service.login` calls `github.com/fatedier/frp/client.defaultConnectorImpl.Connect` (DYNAMIC) at `client/service.go:273` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L273)

```go
272  
273> 	conn, err = connector.Connect()
274  	if err != nil {
```

13. `github.com/fatedier/frp/client.defaultConnectorImpl.Connect` calls `github.com/fatedier/frp/client.defaultConnectorImpl.realConnect` (STATIC) at `client/connector.go:144` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L144)

```go
143  
144> 	return c.realConnect()
145  }
```

14. `github.com/fatedier/frp/client.defaultConnectorImpl.realConnect` calls `github.com/fatedier/golib/net.DialContext` (STATIC) at `client/connector.go:209` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L209)

```go
208  	)
209> 	conn, err := libnet.DialContext(
210  		c.ctx,
```

15. `github.com/fatedier/golib/net.DialContext` calls `github.com/fatedier/golib/net.WithProxy$1$3` (DYNAMIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial.go:80` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial.go#L80)

```go
79  	for _, v := range op.afterHooks {
80> 		ctx, c, err = v.Hook(ctx, c, addr)
81  		if err != nil {
```

16. `github.com/fatedier/golib/net.WithProxy$1$3` calls `github.com/fatedier/golib/net.ntlmHTTPProxyAfterHook` (STATIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial_option.go:142` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial_option.go#L142)

```go
141  			hook = func(ctx context.Context, c net.Conn, addr string) (context.Context, net.Conn, error) {
142> 				conn, err := ntlmHTTPProxyAfterHook(ctx, c, addr)
143  				return ctx, conn, err
```

17. `github.com/fatedier/golib/net.ntlmHTTPProxyAfterHook` calls `github.com/Azure/go-ntlmssp.ProcessChallenge` (STATIC) at `$GOMODCACHE/github.com/fatedier/golib@v0.5.1/net/dial_option.go:318` [source](https://github.com/fatedier/golib/blob/v0.5.1/net/dial_option.go#L318)

```go
317  			}
318> 			authenticateMessage, err := ntlmssp.ProcessChallenge(challengeMessage, username, proxyAuth.Passwd, domainNeeded)
319  			if err != nil {
```

18. `github.com/Azure/go-ntlmssp.ProcessChallenge` calls `github.com/Azure/go-ntlmssp.challengeMessage.UnmarshalBinary` (STATIC) at `$GOMODCACHE/github.com/!azure/go-ntlmssp@v0.0.0-20221128193559-754e69321358/authenticate_message.go:91` [source](https://github.com/Azure/go-ntlmssp/blob/754e69321358/authenticate_message.go#L91)

```go
90  	var cm challengeMessage
91> 	if err := cm.UnmarshalBinary(challengeMessageData); err != nil {
92  		return nil, err
```

19. `github.com/Azure/go-ntlmssp.challengeMessage.UnmarshalBinary` calls `github.com/Azure/go-ntlmssp.varField.ReadFrom` (STATIC) at `$GOMODCACHE/github.com/!azure/go-ntlmssp@v0.0.0-20221128193559-754e69321358/challenge_message.go:47` [source](https://github.com/Azure/go-ntlmssp/blob/754e69321358/challenge_message.go#L47)

```go
46  	if m.challengeMessageFields.TargetInfo.Len > 0 {
47> 		d, err := m.challengeMessageFields.TargetInfo.ReadFrom(data)
48  		m.TargetInfoRaw = d
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |

## frp\_\_GO\-2025\-4017

- advisory: `GO-2025-4017` Panic occurs when queuing undecryptable packets after handshake completion in github\.com/quic\-go/quic\-go
- vulnerable module: `github.com/quic-go/quic-go@v0.53.0`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 4\}

### Path A (without the filter): `github.com/quic-go/quic-go.Conn.handleHandshakeConfirmed` from `github.com/fatedier/frp/cmd/frpc`

1. `github.com/fatedier/frp/cmd/frpc.main` calls `github.com/fatedier/frp/cmd/frpc/sub.Execute` (STATIC) at `cmd/frpc/main.go:25` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/main.go#L25)

```go
24  	system.EnableCompatibilityMode()
25> 	sub.Execute()
26  }
```

2. `github.com/fatedier/frp/cmd/frpc/sub.Execute` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `cmd/frpc/sub/root.go:102` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L102)

```go
101  	rootCmd.SetGlobalNormalizationFunc(config.WordSepNormalizeFunc)
102> 	if err := rootCmd.Execute(); err != nil {
103  		os.Exit(1)
```

3. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1039` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1039)

```go
1038  func (c *Command) Execute() error {
1039> 	_, err := c.ExecuteC()
1040  	return err
```

4. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1115` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1115)

```go
1114  
1115> 	err = cmd.execute(flags)
1116  	if err != nil {
```

5. `github.com/spf13/cobra.Command.execute` calls `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` (DYNAMIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:987` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L987)

```go
986  	} else {
987> 		c.Run(c, argWoFlags)
988  	}
```

6. `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` calls `github.com/fatedier/frp/cmd/frpc/sub.startService` (STATIC) at `cmd/frpc/sub/proxy.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/proxy.go#L91)

```go
90  			}
91> 			err := startService(clientCfg, []v1.ProxyConfigurer{c}, nil, "")
92  			if err != nil {
```

7. `github.com/fatedier/frp/cmd/frpc/sub.startService` calls `github.com/fatedier/frp/client.Service.Run` (STATIC) at `cmd/frpc/sub/root.go:167` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L167)

```go
166  	}
167> 	return svr.Run(context.Background())
168  }
```

8. `github.com/fatedier/frp/client.Service.Run` calls `github.com/fatedier/frp/client.Service.keepControllerWorking` (STATIC) at `client/service.go:219` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L219)

```go
218  
219> 	go svr.keepControllerWorking()
220
```

9. `github.com/fatedier/frp/client.Service.keepControllerWorking` calls `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` (STATIC) at `client/service.go:233` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L233)

```go
232  	// The maximum interval is 20 seconds.
233> 	wait.BackoffUntil(func() (bool, error) {
234  		// loopLoginUntilSuccess is another layer of loop that will continuously attempt to
```

10. `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` (DYNAMIC) at `pkg/util/wait/backoff.go:133` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/pkg/util/wait/backoff.go#L133)

```go
132  
133> 		if done, err := f(); done {
134  			return
```

11. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` calls `github.com/fatedier/frp/client.Service.login` (STATIC) at `client/service.go:326` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L326)

```go
325  		xl.Infof("try to connect to server...")
326> 		conn, connector, err := svr.login()
327  		if err != nil {
```

12. `github.com/fatedier/frp/client.Service.login` calls `github.com/fatedier/frp/client.defaultConnectorImpl.Open` (DYNAMIC) at `client/service.go:263` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L263)

```go
262  	connector = svr.connectorCreator(svr.ctx, svr.common)
263> 	if err = connector.Open(); err != nil {
264  		return nil, nil, err
```

13. `github.com/fatedier/frp/client.defaultConnectorImpl.Open` calls `github.com/quic-go/quic-go.DialAddr` (STATIC) at `client/connector.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L91)

```go
90  
91> 		conn, err := quic.DialAddr(
92  			c.ctx,
```

14. `github.com/quic-go/quic-go.DialAddr` calls `github.com/quic-go/quic-go.Transport.dial` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/client.go:32` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/client.go#L32)

```go
31  	}
32> 	conn, err := tr.dial(ctx, udpAddr, addr, tlsConf, conf, false)
33  	if err != nil {
```

15. `github.com/quic-go/quic-go.Transport.dial` calls `github.com/quic-go/quic-go.Transport.doDial` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:255` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L255)

```go
254  	setTLSConfigServerName(tlsConf, addr, host)
255> 	return t.doDial(ctx,
256  		newSendConn(t.conn, addr, packetInfo{}, utils.DefaultLogger),
```

16. `github.com/quic-go/quic-go.Transport.doDial` calls `github.com/quic-go/quic-go.Transport.doDial$1` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:330` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L330)

```go
329  	recreateChan := make(chan errCloseForRecreating, 1)
330> 	go func() {
331  		err := conn.run()
```

17. `github.com/quic-go/quic-go.Transport.doDial$1` calls `github.com/quic-go/quic-go.Conn.run` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:331` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L331)

```go
330  	go func() {
331> 		err := conn.run()
332  		var recreateErr *errCloseForRecreating
```

18. `github.com/quic-go/quic-go.Conn.run` calls `github.com/quic-go/quic-go.Conn.handleOnePacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:571` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L571)

```go
570  			for _, p := range queue {
571> 				processed, err := c.handleOnePacket(p)
572  				if err != nil {
```

19. `github.com/quic-go/quic-go.Conn.handleOnePacket` calls `github.com/quic-go/quic-go.Conn.handleLongHeaderPacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:968` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L968)

```go
967  
968> 			processed, err := c.handleLongHeaderPacket(p, hdr)
969  			if err != nil {
```

20. `github.com/quic-go/quic-go.Conn.handleLongHeaderPacket` calls `github.com/quic-go/quic-go.Conn.handleUnpackedLongHeaderPacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1159` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1159)

```go
1158  
1159> 	if err := c.handleUnpackedLongHeaderPacket(packet, p.ecn, p.rcvTime, p.Size()); err != nil {
1160  		return false, err
```

21. `github.com/quic-go/quic-go.Conn.handleUnpackedLongHeaderPacket` calls `github.com/quic-go/quic-go.Conn.handleFrames` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1388` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1388)

```go
1387  	}
1388> 	isAckEliciting, _, _, err := c.handleFrames(packet.data, packet.hdr.DestConnectionID, packet.encryptionLevel, log, rcvTime)
1389  	if err != nil {
```

22. `github.com/quic-go/quic-go.Conn.handleFrames` calls `github.com/quic-go/quic-go.Conn.handleHandshakeComplete` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1482` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1482)

```go
1481  	if !handshakeWasComplete && c.handshakeComplete {
1482> 		if err := c.handleHandshakeComplete(rcvTime); err != nil {
1483  			return false, false, nil, err
```

23. `github.com/quic-go/quic-go.Conn.handleHandshakeComplete` calls `github.com/quic-go/quic-go.Conn.handleHandshakeConfirmed` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:816` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L816)

```go
815  	// All these only apply to the server side.
816> 	if err := c.handleHandshakeConfirmed(now); err != nil {
817  		return err
```


### Path B (the path that passed the filter): `github.com/quic-go/quic-go.Conn.handleHandshakeConfirmed`

1. `github.com/fatedier/frp/cmd/frpc.main` calls `github.com/fatedier/frp/cmd/frpc/sub.Execute` (STATIC) at `cmd/frpc/main.go:25` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/main.go#L25)

```go
24  	system.EnableCompatibilityMode()
25> 	sub.Execute()
26  }
```

2. `github.com/fatedier/frp/cmd/frpc/sub.Execute` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `cmd/frpc/sub/root.go:102` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L102)

```go
101  	rootCmd.SetGlobalNormalizationFunc(config.WordSepNormalizeFunc)
102> 	if err := rootCmd.Execute(); err != nil {
103  		os.Exit(1)
```

3. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1039` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1039)

```go
1038  func (c *Command) Execute() error {
1039> 	_, err := c.ExecuteC()
1040  	return err
```

4. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:1115` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L1115)

```go
1114  
1115> 	err = cmd.execute(flags)
1116  	if err != nil {
```

5. `github.com/spf13/cobra.Command.execute` calls `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` (DYNAMIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.8.0/command.go:987` [source](https://github.com/spf13/cobra/blob/v1.8.0/command.go#L987)

```go
986  	} else {
987> 		c.Run(c, argWoFlags)
988  	}
```

6. `github.com/fatedier/frp/cmd/frpc/sub.NewProxyCommand$1` calls `github.com/fatedier/frp/cmd/frpc/sub.startService` (STATIC) at `cmd/frpc/sub/proxy.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/proxy.go#L91)

```go
90  			}
91> 			err := startService(clientCfg, []v1.ProxyConfigurer{c}, nil, "")
92  			if err != nil {
```

7. `github.com/fatedier/frp/cmd/frpc/sub.startService` calls `github.com/fatedier/frp/client.Service.Run` (STATIC) at `cmd/frpc/sub/root.go:167` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/cmd/frpc/sub/root.go#L167)

```go
166  	}
167> 	return svr.Run(context.Background())
168  }
```

8. `github.com/fatedier/frp/client.Service.Run` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess` (STATIC) at `client/service.go:212` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L212)

```go
211  	// first login to frps
212> 	svr.loopLoginUntilSuccess(10*time.Second, lo.FromPtr(svr.common.LoginFailExit))
213  	if svr.ctl == nil {
```

9. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess` calls `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` (STATIC) at `client/service.go:371` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L371)

```go
370  	// try to reconnect to server until success
371> 	wait.BackoffUntil(loginFunc, wait.NewFastBackoffManager(
372  		wait.FastBackoffOptions{
```

10. `github.com/fatedier/frp/pkg/util/wait.BackoffUntil` calls `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` (DYNAMIC) at `pkg/util/wait/backoff.go:133` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/pkg/util/wait/backoff.go#L133)

```go
132  
133> 		if done, err := f(); done {
134  			return
```

11. `github.com/fatedier/frp/client.Service.loopLoginUntilSuccess$1` calls `github.com/fatedier/frp/client.Service.login` (STATIC) at `client/service.go:326` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L326)

```go
325  		xl.Infof("try to connect to server...")
326> 		conn, connector, err := svr.login()
327  		if err != nil {
```

12. `github.com/fatedier/frp/client.Service.login` calls `github.com/fatedier/frp/client.defaultConnectorImpl.Open` (DYNAMIC) at `client/service.go:263` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/service.go#L263)

```go
262  	connector = svr.connectorCreator(svr.ctx, svr.common)
263> 	if err = connector.Open(); err != nil {
264  		return nil, nil, err
```

13. `github.com/fatedier/frp/client.defaultConnectorImpl.Open` calls `github.com/quic-go/quic-go.DialAddr` (STATIC) at `client/connector.go:91` [source](https://github.com/fatedier/frp/blob/2f5e1f79457b5e9d769f2ac063443b62640185a9/client/connector.go#L91)

```go
90  
91> 		conn, err := quic.DialAddr(
92  			c.ctx,
```

14. `github.com/quic-go/quic-go.DialAddr` calls `github.com/quic-go/quic-go.Transport.dial` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/client.go:32` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/client.go#L32)

```go
31  	}
32> 	conn, err := tr.dial(ctx, udpAddr, addr, tlsConf, conf, false)
33  	if err != nil {
```

15. `github.com/quic-go/quic-go.Transport.dial` calls `github.com/quic-go/quic-go.Transport.doDial` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:255` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L255)

```go
254  	setTLSConfigServerName(tlsConf, addr, host)
255> 	return t.doDial(ctx,
256  		newSendConn(t.conn, addr, packetInfo{}, utils.DefaultLogger),
```

16. `github.com/quic-go/quic-go.Transport.doDial` calls `github.com/quic-go/quic-go.Transport.doDial$1` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:330` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L330)

```go
329  	recreateChan := make(chan errCloseForRecreating, 1)
330> 	go func() {
331  		err := conn.run()
```

17. `github.com/quic-go/quic-go.Transport.doDial$1` calls `github.com/quic-go/quic-go.Conn.run` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/transport.go:331` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/transport.go#L331)

```go
330  	go func() {
331> 		err := conn.run()
332  		var recreateErr *errCloseForRecreating
```

18. `github.com/quic-go/quic-go.Conn.run` calls `github.com/quic-go/quic-go.Conn.handleOnePacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:571` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L571)

```go
570  			for _, p := range queue {
571> 				processed, err := c.handleOnePacket(p)
572  				if err != nil {
```

19. `github.com/quic-go/quic-go.Conn.handleOnePacket` calls `github.com/quic-go/quic-go.Conn.handleLongHeaderPacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:968` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L968)

```go
967  
968> 			processed, err := c.handleLongHeaderPacket(p, hdr)
969  			if err != nil {
```

20. `github.com/quic-go/quic-go.Conn.handleLongHeaderPacket` calls `github.com/quic-go/quic-go.Conn.handleUnpackedLongHeaderPacket` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1159` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1159)

```go
1158  
1159> 	if err := c.handleUnpackedLongHeaderPacket(packet, p.ecn, p.rcvTime, p.Size()); err != nil {
1160  		return false, err
```

21. `github.com/quic-go/quic-go.Conn.handleUnpackedLongHeaderPacket` calls `github.com/quic-go/quic-go.Conn.handleFrames` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1388` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1388)

```go
1387  	}
1388> 	isAckEliciting, _, _, err := c.handleFrames(packet.data, packet.hdr.DestConnectionID, packet.encryptionLevel, log, rcvTime)
1389  	if err != nil {
```

22. `github.com/quic-go/quic-go.Conn.handleFrames` calls `github.com/quic-go/quic-go.Conn.handleHandshakeComplete` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:1482` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L1482)

```go
1481  	if !handshakeWasComplete && c.handshakeComplete {
1482> 		if err := c.handleHandshakeComplete(rcvTime); err != nil {
1483  			return false, false, nil, err
```

23. `github.com/quic-go/quic-go.Conn.handleHandshakeComplete` calls `github.com/quic-go/quic-go.Conn.handleHandshakeConfirmed` (STATIC) at `$GOMODCACHE/github.com/quic-go/quic-go@v0.53.0/connection.go:816` [source](https://github.com/quic-go/quic-go/blob/v0.53.0/connection.go#L816)

```go
815  	// All these only apply to the server side.
816> 	if err := c.handleHandshakeConfirmed(now); err != nil {
817  		return err
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |
