# CP9 adjudication (D3b, held-out): github\.com/gogs/gogs

- application: `github.com/gogs/gogs` at tag `v0.13.3`, commit `5084b4a9b77a506f5e287e82e945e1c6882b827a`
- cases to adjudicate: 3 (every case REACHABLE in either run)

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

## gogs\_\_GO\-2024\-2606

- advisory: `GO-2024-2606` SQL injection in github\.com/jackc/pgproto3 and github\.com/jackc/pgx
- vulnerable module: `github.com/jackc/pgx/v5@v5.3.0`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 108\}

### Path A (without the filter): `github.com/jackc/pgx/v5/pgproto3.Bind.Encode` from `gogs.io/gogs`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/cmd.init$1` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/cmd.init$1` calls `gogs.io/gogs/internal/db.users.DeleteInactivated` (DYNAMIC) at `internal/cmd/admin.go:55` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L55)

```go
54  		Action: adminDashboardOperation(
55> 			func() error { return db.Users.DeleteInactivated() },
56  			"All inactivated accounts have been deleted successfully",
```

6. `gogs.io/gogs/internal/db.users.DeleteInactivated` calls `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` (DYNAMIC) at `internal/db/users.go:654` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/users.go#L654)

```go
653  	}
654> 	err = NewPublicKeysStore(db.DB).RewriteAuthorizedKeys()
655  	if err != nil {
```

7. `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` calls `database/sql.Rows.Next` (STATIC) at `internal/db/public_keys.go:70` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/public_keys.go#L70)

```go
69  
70> 	for rows.Next() {
71  		var key PublicKey
```

8. `database/sql.Rows.Next` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:3040` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3040)

```go
3039  	var doClose, ok bool
3040> 	withLock(rs.closemu.RLocker(), func() {
3041  		doClose, ok = rs.nextLocked()
```

9. `database/sql.withLock` calls `database/sql.DB.queryDC$1` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.DB.queryDC$1` calls `database/sql.ctxDriverQuery` (STATIC) at `$GOROOT/src/database/sql/sql.go:1786` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L1786)

```go
1785  			}
1786> 			rowsi, err = ctxDriverQuery(ctx, queryerCtx, queryer, query, nvdargs)
1787  		})
```

11. `database/sql.ctxDriverQuery` calls `github.com/jackc/pgx/v5/stdlib.Conn.QueryContext` (DYNAMIC) at `$GOROOT/src/database/sql/ctxutil.go:48` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/ctxutil.go#L48)

```go
47  	if queryerCtx != nil {
48> 		return queryerCtx.QueryContext(ctx, query, nvdargs)
49  	}
```

12. `github.com/jackc/pgx/v5/stdlib.Conn.QueryContext` calls `github.com/jackc/pgx/v5.Conn.Query` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:418` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L418)

```go
417  
418> 	rows, err := c.conn.Query(ctx, query, args...)
419  	if err != nil {
```

13. `github.com/jackc/pgx/v5.Conn.Query` calls `github.com/jackc/pgx/v5/pgconn.PgConn.ExecParams` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:756` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L756)

```go
755  		if !explicitPreparedStatement && mode == QueryExecModeCacheDescribe {
756> 			rows.resultReader = c.pgConn.ExecParams(ctx, sql, c.eqb.ParamValues, sd.ParamOIDs, c.eqb.ParamFormats, resultFormats)
757  		} else {
```

14. `github.com/jackc/pgx/v5/pgconn.PgConn.ExecParams` calls `github.com/jackc/pgx/v5/pgproto3.Frontend.SendBind` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/pgconn/pgconn.go:995` [source](https://github.com/jackc/pgx/blob/v5.3.0/pgconn/pgconn.go#L995)

```go
994  	pgConn.frontend.SendParse(&pgproto3.Parse{Query: sql, ParameterOIDs: paramOIDs})
995> 	pgConn.frontend.SendBind(&pgproto3.Bind{ParameterFormatCodes: paramFormats, Parameters: paramValues, ResultFormatCodes: resultFormats})
996
```

15. `github.com/jackc/pgx/v5/pgproto3.Frontend.SendBind` calls `github.com/jackc/pgx/v5/pgproto3.Bind.Encode` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/pgproto3/frontend.go:123` [source](https://github.com/jackc/pgx/blob/v5.3.0/pgproto3/frontend.go#L123)

```go
122  	prevLen := len(f.wbuf)
123> 	f.wbuf = msg.Encode(f.wbuf)
124  	if f.tracer != nil {
```


### Path B (the path that passed the filter): `github.com/jackc/pgx/v5/pgproto3.Bind.Encode`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/db.DeleteMissingRepositories` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/db.DeleteMissingRepositories` calls `gogs.io/gogs/internal/db.DeleteRepository` (STATIC) at `internal/db/repo.go:2008` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L2008)

```go
2007  		log.Trace("Deleting %d/%d...", repo.OwnerID, repo.ID)
2008> 		if err := DeleteRepository(repo.OwnerID, repo.ID); err != nil {
2009  			if err2 := CreateRepositoryNotice(fmt.Sprintf("DeleteRepository [%d]: %v", repo.ID, err)); err2 != nil {
```

6. `gogs.io/gogs/internal/db.DeleteRepository` calls `xorm.io/xorm.Session.Commit` (STATIC) at `internal/db/repo.go:1731` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L1731)

```go
1730  
1731> 	if err = sess.Commit(); err != nil {
1732  		return fmt.Errorf("Commit: %v", err)
```

7. `xorm.io/xorm.Session.Commit` calls `database/sql.Tx.Commit` (STATIC) at `$GOMODCACHE/xorm.io/xorm@v0.8.0/session_tx.go:40`

```go
39  		var err error
40> 		if err = session.tx.Commit(); err == nil {
41  			// handle processors after tx committed
```

8. `database/sql.Tx.Commit` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:2312` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2312)

```go
2311  	var err error
2312> 	withLock(tx.dc, func() {
2313  		err = tx.txi.Commit()
```

9. `database/sql.withLock` calls `database/sql.Tx.Commit$1` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.Tx.Commit$1` calls `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:2313` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2313)

```go
2312  	withLock(tx.dc, func() {
2313> 		err = tx.txi.Commit()
2314  	})
```

11. `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` calls `github.com/jackc/pgx/v5.dbTx.Commit` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:785` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L785)

```go
784  
785> func (wtx wrapTx) Commit() error { return wtx.tx.Commit(wtx.ctx) }
786
```

12. `github.com/jackc/pgx/v5.dbTx.Commit` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/tx.go:173` [source](https://github.com/jackc/pgx/blob/v5.3.0/tx.go#L173)

```go
172  
173> 	commandTag, err := tx.conn.Exec(ctx, "commit")
174  	tx.closed = true
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:416` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L416)

```go
415  
416> 	commandTag, err := c.exec(ctx, sql, arguments...)
417
```

14. `github.com/jackc/pgx/v5.Conn.exec` calls `github.com/jackc/pgx/v5.Conn.execParams` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:486` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L486)

```go
485  
486> 		return c.execParams(ctx, sd, arguments)
487  	case QueryExecModeDescribeExec:
```

15. `github.com/jackc/pgx/v5.Conn.execParams` calls `github.com/jackc/pgx/v5/pgconn.PgConn.ExecParams` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:524` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L524)

```go
523  
524> 	result := c.pgConn.ExecParams(ctx, sd.SQL, c.eqb.ParamValues, sd.ParamOIDs, c.eqb.ParamFormats, c.eqb.ResultFormats).Read()
525  	c.eqb.reset() // Allow c.eqb internal memory to be GC'ed as soon as possible.
```

16. `github.com/jackc/pgx/v5/pgconn.PgConn.ExecParams` calls `github.com/jackc/pgx/v5/pgproto3.Frontend.SendBind` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/pgconn/pgconn.go:995` [source](https://github.com/jackc/pgx/blob/v5.3.0/pgconn/pgconn.go#L995)

```go
994  	pgConn.frontend.SendParse(&pgproto3.Parse{Query: sql, ParameterOIDs: paramOIDs})
995> 	pgConn.frontend.SendBind(&pgproto3.Bind{ParameterFormatCodes: paramFormats, Parameters: paramValues, ResultFormatCodes: resultFormats})
996
```

17. `github.com/jackc/pgx/v5/pgproto3.Frontend.SendBind` calls `github.com/jackc/pgx/v5/pgproto3.Bind.Encode` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/pgproto3/frontend.go:123` [source](https://github.com/jackc/pgx/blob/v5.3.0/pgproto3/frontend.go#L123)

```go
122  	prevLen := len(f.wbuf)
123> 	f.wbuf = msg.Encode(f.wbuf)
124  	if f.tracer != nil {
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |

## gogs\_\_GO\-2024\-2567

- advisory: `GO-2024-2567` Panic in Pipeline when PgConn is busy or closed in github\.com/jackc/pgx
- vulnerable module: `github.com/jackc/pgx/v5@v5.3.0`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 2\}

### Path A (without the filter): `github.com/jackc/pgx/v5/pgconn.Pipeline.Sync` from `gogs.io/gogs`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/cmd.init$1` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/cmd.init$1` calls `gogs.io/gogs/internal/db.users.DeleteInactivated` (DYNAMIC) at `internal/cmd/admin.go:55` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L55)

```go
54  		Action: adminDashboardOperation(
55> 			func() error { return db.Users.DeleteInactivated() },
56  			"All inactivated accounts have been deleted successfully",
```

6. `gogs.io/gogs/internal/db.users.DeleteInactivated` calls `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` (DYNAMIC) at `internal/db/users.go:654` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/users.go#L654)

```go
653  	}
654> 	err = NewPublicKeysStore(db.DB).RewriteAuthorizedKeys()
655  	if err != nil {
```

7. `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` calls `database/sql.Rows.Next` (STATIC) at `internal/db/public_keys.go:70` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/public_keys.go#L70)

```go
69  
70> 	for rows.Next() {
71  		var key PublicKey
```

8. `database/sql.Rows.Next` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:3040` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3040)

```go
3039  	var doClose, ok bool
3040> 	withLock(rs.closemu.RLocker(), func() {
3041  		doClose, ok = rs.nextLocked()
```

9. `database/sql.withLock` calls `database/sql.DB.execDC$2` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.DB.execDC$2` calls `database/sql.ctxDriverExec` (STATIC) at `$GOROOT/src/database/sql/sql.go:1713` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L1713)

```go
1712  			}
1713> 			resi, err = ctxDriverExec(ctx, execerCtx, execer, query, nvdargs)
1714  		})
```

11. `database/sql.ctxDriverExec` calls `github.com/jackc/pgx/v5/stdlib.Conn.ExecContext` (DYNAMIC) at `$GOROOT/src/database/sql/ctxutil.go:31` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/ctxutil.go#L31)

```go
30  	if execerCtx != nil {
31> 		return execerCtx.ExecContext(ctx, query, nvdargs)
32  	}
```

12. `github.com/jackc/pgx/v5/stdlib.Conn.ExecContext` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:400` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L400)

```go
399  
400> 	commandTag, err := c.conn.Exec(ctx, query, args...)
401  	// if we got a network error before we had a chance to send the query, retry
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.deallocateInvalidatedCachedStatements` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:412` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L412)

```go
411  
412> 	if err := c.deallocateInvalidatedCachedStatements(ctx); err != nil {
413  		return pgconn.CommandTag{}, err
```

14. `github.com/jackc/pgx/v5.Conn.deallocateInvalidatedCachedStatements` calls `github.com/jackc/pgx/v5/pgconn.Pipeline.Sync` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:1329` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L1329)

```go
1328  
1329> 	err := pipeline.Sync()
1330  	if err != nil {
```


### Path B (the path that passed the filter): `github.com/jackc/pgx/v5/pgconn.Pipeline.Sync`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/db.DeleteMissingRepositories` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/db.DeleteMissingRepositories` calls `gogs.io/gogs/internal/db.DeleteRepository` (STATIC) at `internal/db/repo.go:2008` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L2008)

```go
2007  		log.Trace("Deleting %d/%d...", repo.OwnerID, repo.ID)
2008> 		if err := DeleteRepository(repo.OwnerID, repo.ID); err != nil {
2009  			if err2 := CreateRepositoryNotice(fmt.Sprintf("DeleteRepository [%d]: %v", repo.ID, err)); err2 != nil {
```

6. `gogs.io/gogs/internal/db.DeleteRepository` calls `xorm.io/xorm.Session.Commit` (STATIC) at `internal/db/repo.go:1731` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L1731)

```go
1730  
1731> 	if err = sess.Commit(); err != nil {
1732  		return fmt.Errorf("Commit: %v", err)
```

7. `xorm.io/xorm.Session.Commit` calls `database/sql.Tx.Commit` (STATIC) at `$GOMODCACHE/xorm.io/xorm@v0.8.0/session_tx.go:40`

```go
39  		var err error
40> 		if err = session.tx.Commit(); err == nil {
41  			// handle processors after tx committed
```

8. `database/sql.Tx.Commit` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:2312` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2312)

```go
2311  	var err error
2312> 	withLock(tx.dc, func() {
2313  		err = tx.txi.Commit()
```

9. `database/sql.withLock` calls `database/sql.Tx.Commit$1` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.Tx.Commit$1` calls `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:2313` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2313)

```go
2312  	withLock(tx.dc, func() {
2313> 		err = tx.txi.Commit()
2314  	})
```

11. `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` calls `github.com/jackc/pgx/v5.dbTx.Commit` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:785` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L785)

```go
784  
785> func (wtx wrapTx) Commit() error { return wtx.tx.Commit(wtx.ctx) }
786
```

12. `github.com/jackc/pgx/v5.dbTx.Commit` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/tx.go:173` [source](https://github.com/jackc/pgx/blob/v5.3.0/tx.go#L173)

```go
172  
173> 	commandTag, err := tx.conn.Exec(ctx, "commit")
174  	tx.closed = true
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.deallocateInvalidatedCachedStatements` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:412` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L412)

```go
411  
412> 	if err := c.deallocateInvalidatedCachedStatements(ctx); err != nil {
413  		return pgconn.CommandTag{}, err
```

14. `github.com/jackc/pgx/v5.Conn.deallocateInvalidatedCachedStatements` calls `github.com/jackc/pgx/v5/pgconn.Pipeline.Sync` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:1329` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L1329)

```go
1328  
1329> 	err := pipeline.Sync()
1330  	if err != nil {
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |

## gogs\_\_GO\-2026\-5004

- advisory: `GO-2026-5004` SQL Injection via placeholder confusion with dollar quoted string literals in github\.com/jackc/pgx
- vulnerable module: `github.com/jackc/pgx/v5@v5.3.0`
- mode: FIX
- verdict without the filter: **REACHABLE**
- verdict with the filter: **REACHABLE** (no reason codes)
- filter answers (REACHABLE entries): \{'FEASIBLE': 8\}

### Path A (without the filter): `github.com/jackc/pgx/v5/internal/sanitize.placeholderState` from `gogs.io/gogs`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/cmd.init$1` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/cmd.init$1` calls `gogs.io/gogs/internal/db.users.DeleteInactivated` (DYNAMIC) at `internal/cmd/admin.go:55` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L55)

```go
54  		Action: adminDashboardOperation(
55> 			func() error { return db.Users.DeleteInactivated() },
56  			"All inactivated accounts have been deleted successfully",
```

6. `gogs.io/gogs/internal/db.users.DeleteInactivated` calls `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` (DYNAMIC) at `internal/db/users.go:654` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/users.go#L654)

```go
653  	}
654> 	err = NewPublicKeysStore(db.DB).RewriteAuthorizedKeys()
655  	if err != nil {
```

7. `gogs.io/gogs/internal/db.publicKeys.RewriteAuthorizedKeys` calls `database/sql.Rows.Next` (STATIC) at `internal/db/public_keys.go:70` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/public_keys.go#L70)

```go
69  
70> 	for rows.Next() {
71  		var key PublicKey
```

8. `database/sql.Rows.Next` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:3040` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3040)

```go
3039  	var doClose, ok bool
3040> 	withLock(rs.closemu.RLocker(), func() {
3041  		doClose, ok = rs.nextLocked()
```

9. `database/sql.withLock` calls `database/sql.DB.queryDC$1` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.DB.queryDC$1` calls `database/sql.ctxDriverQuery` (STATIC) at `$GOROOT/src/database/sql/sql.go:1786` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L1786)

```go
1785  			}
1786> 			rowsi, err = ctxDriverQuery(ctx, queryerCtx, queryer, query, nvdargs)
1787  		})
```

11. `database/sql.ctxDriverQuery` calls `github.com/jackc/pgx/v5/stdlib.Conn.QueryContext` (DYNAMIC) at `$GOROOT/src/database/sql/ctxutil.go:48` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/ctxutil.go#L48)

```go
47  	if queryerCtx != nil {
48> 		return queryerCtx.QueryContext(ctx, query, nvdargs)
49  	}
```

12. `github.com/jackc/pgx/v5/stdlib.Conn.QueryContext` calls `github.com/jackc/pgx/v5.Conn.Query` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:418` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L418)

```go
417  
418> 	rows, err := c.conn.Query(ctx, query, args...)
419  	if err != nil {
```

13. `github.com/jackc/pgx/v5.Conn.Query` calls `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:769` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L769)

```go
768  	} else if mode == QueryExecModeSimpleProtocol {
769> 		sql, err = c.sanitizeForSimpleQuery(sql, args...)
770  		if err != nil {
```

14. `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:1161` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L1161)

```go
1160  
1161> 	return sanitize.SanitizeSQL(sql, valueArgs...)
1162  }
```

15. `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` calls `github.com/jackc/pgx/v5/internal/sanitize.NewQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/internal/sanitize/sanitize.go:317` [source](https://github.com/jackc/pgx/blob/v5.3.0/internal/sanitize/sanitize.go#L317)

```go
316  func SanitizeSQL(sql string, args ...any) (string, error) {
317> 	query, err := NewQuery(sql)
318  	if err != nil {
```

16. `github.com/jackc/pgx/v5/internal/sanitize.NewQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.placeholderState` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/internal/sanitize/sanitize.go:82` [source](https://github.com/jackc/pgx/blob/v5.3.0/internal/sanitize/sanitize.go#L82)

```go
81  	for l.stateFn != nil {
82> 		l.stateFn = l.stateFn(l)
83  	}
```


### Path B (the path that passed the filter): `github.com/jackc/pgx/v5/internal/sanitize.placeholderState`

1. `gogs.io/gogs.main` calls `github.com/urfave/cli.App.Run` (STATIC) at `gogs.go:39` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/gogs.go#L39)

```go
38  	}
39> 	if err := app.Run(os.Args); err != nil {
40  		log.Fatal("Failed to start application: %v", err)
```

2. `github.com/urfave/cli.App.Run` calls `github.com/urfave/cli.HandleAction` (STATIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:286` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L286)

```go
285  	// Run default Action
286> 	err = HandleAction(a.Action, context)
287
```

3. `github.com/urfave/cli.HandleAction` calls `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` (DYNAMIC) at `$GOMODCACHE/github.com/urfave/cli@v1.22.16/app.go:522` [source](https://github.com/urfave/cli/blob/v1.22.16/app.go#L522)

```go
521  	case ActionFunc:
522> 		return a(context)
523  	case func(*Context) error:
```

4. `gogs.io/gogs/internal/cmd.adminDashboardOperation$1` calls `gogs.io/gogs/internal/db.DeleteMissingRepositories` (DYNAMIC) at `internal/cmd/admin.go:185` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/cmd/admin.go#L185)

```go
184  
185> 		if err := operation(); err != nil {
186  			functionName := runtime.FuncForPC(reflect.ValueOf(operation).Pointer()).Name()
```

5. `gogs.io/gogs/internal/db.DeleteMissingRepositories` calls `gogs.io/gogs/internal/db.DeleteRepository` (STATIC) at `internal/db/repo.go:2008` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L2008)

```go
2007  		log.Trace("Deleting %d/%d...", repo.OwnerID, repo.ID)
2008> 		if err := DeleteRepository(repo.OwnerID, repo.ID); err != nil {
2009  			if err2 := CreateRepositoryNotice(fmt.Sprintf("DeleteRepository [%d]: %v", repo.ID, err)); err2 != nil {
```

6. `gogs.io/gogs/internal/db.DeleteRepository` calls `xorm.io/xorm.Session.Commit` (STATIC) at `internal/db/repo.go:1731` [source](https://github.com/gogs/gogs/blob/5084b4a9b77a506f5e287e82e945e1c6882b827a/internal/db/repo.go#L1731)

```go
1730  
1731> 	if err = sess.Commit(); err != nil {
1732  		return fmt.Errorf("Commit: %v", err)
```

7. `xorm.io/xorm.Session.Commit` calls `database/sql.Tx.Commit` (STATIC) at `$GOMODCACHE/xorm.io/xorm@v0.8.0/session_tx.go:40`

```go
39  		var err error
40> 		if err = session.tx.Commit(); err == nil {
41  			// handle processors after tx committed
```

8. `database/sql.Tx.Commit` calls `database/sql.withLock` (STATIC) at `$GOROOT/src/database/sql/sql.go:2312` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2312)

```go
2311  	var err error
2312> 	withLock(tx.dc, func() {
2313  		err = tx.txi.Commit()
```

9. `database/sql.withLock` calls `database/sql.Tx.Commit$1` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:3572` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L3572)

```go
3571  	defer lk.Unlock() // in case fn panics
3572> 	fn()
3573  }
```

10. `database/sql.Tx.Commit$1` calls `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` (DYNAMIC) at `$GOROOT/src/database/sql/sql.go:2313` [source](https://github.com/golang/go/blob/go1.26.10/src/database/sql/sql.go#L2313)

```go
2312  	withLock(tx.dc, func() {
2313> 		err = tx.txi.Commit()
2314  	})
```

11. `github.com/jackc/pgx/v5/stdlib.wrapTx.Commit` calls `github.com/jackc/pgx/v5.dbTx.Commit` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/stdlib/sql.go:785` [source](https://github.com/jackc/pgx/blob/v5.3.0/stdlib/sql.go#L785)

```go
784  
785> func (wtx wrapTx) Commit() error { return wtx.tx.Commit(wtx.ctx) }
786
```

12. `github.com/jackc/pgx/v5.dbTx.Commit` calls `github.com/jackc/pgx/v5.Conn.Exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/tx.go:173` [source](https://github.com/jackc/pgx/blob/v5.3.0/tx.go#L173)

```go
172  
173> 	commandTag, err := tx.conn.Exec(ctx, "commit")
174  	tx.closed = true
```

13. `github.com/jackc/pgx/v5.Conn.Exec` calls `github.com/jackc/pgx/v5.Conn.exec` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:416` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L416)

```go
415  
416> 	commandTag, err := c.exec(ctx, sql, arguments...)
417
```

14. `github.com/jackc/pgx/v5.Conn.exec` calls `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:496` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L496)

```go
495  	case QueryExecModeSimpleProtocol:
496> 		return c.execSimpleProtocol(ctx, sql, arguments)
497  	default:
```

15. `github.com/jackc/pgx/v5.Conn.execSimpleProtocol` calls `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:504` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L504)

```go
503  	if len(arguments) > 0 {
504> 		sql, err = c.sanitizeForSimpleQuery(sql, arguments...)
505  		if err != nil {
```

16. `github.com/jackc/pgx/v5.Conn.sanitizeForSimpleQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/conn.go:1161` [source](https://github.com/jackc/pgx/blob/v5.3.0/conn.go#L1161)

```go
1160  
1161> 	return sanitize.SanitizeSQL(sql, valueArgs...)
1162  }
```

17. `github.com/jackc/pgx/v5/internal/sanitize.SanitizeSQL` calls `github.com/jackc/pgx/v5/internal/sanitize.NewQuery` (STATIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/internal/sanitize/sanitize.go:317` [source](https://github.com/jackc/pgx/blob/v5.3.0/internal/sanitize/sanitize.go#L317)

```go
316  func SanitizeSQL(sql string, args ...any) (string, error) {
317> 	query, err := NewQuery(sql)
318  	if err != nil {
```

18. `github.com/jackc/pgx/v5/internal/sanitize.NewQuery` calls `github.com/jackc/pgx/v5/internal/sanitize.placeholderState` (DYNAMIC) at `$GOMODCACHE/github.com/jackc/pgx/v5@v5.3.0/internal/sanitize/sanitize.go:82` [source](https://github.com/jackc/pgx/blob/v5.3.0/internal/sanitize/sanitize.go#L82)

```go
81  	for l.stateFn != nil {
82> 		l.stateFn = l.stateFn(l)
83  	}
```


| field | value |
|---|---|
| adjudication_off | |
| adjudication_on | |
| truth | |
| by | |
| note | |
