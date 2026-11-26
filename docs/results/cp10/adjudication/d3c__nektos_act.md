# CP10 adjudication: d3c\_\_nektos\_act

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

## act\_\_GO\-2025\-3900

- item: D3c case
- advisory: `GO-2025-3900` Go\-viper's mapstructure May Leak Sensitive Information in Logs in github\.com/go\-viper/mapstructure
- vulnerable module: `github.com/go-viper/mapstructure/v2@v2.3.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (27): `github.com/go-viper/mapstructure/v2.StringToIntHookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeFloat`, `github.com/go-viper/mapstructure/v2.StringToUintHookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeInt`, `github.com/go-viper/mapstructure/v2.StringToFloat32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint8HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPNetHookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt8HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPHookFunc`, `github.com/go-viper/mapstructure/v2.StringToBoolHookFunc`, `github.com/go-viper/mapstructure/v2.StringToTimeHookFunc`, `github.com/go-viper/mapstructure/v2.StringToURLHookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex128HookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPPrefixHookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrPortHookFunc`, `github.com/go-viper/mapstructure/v2.StringToTimeDurationHookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt16HookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeUint`, `github.com/go-viper/mapstructure/v2.StringToUint16HookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrHookFunc`, `github.com/go-viper/mapstructure/v2.StringToUint64HookFunc`, `github.com/go-viper/mapstructure/v2.Decoder.decodeBool`, `github.com/go-viper/mapstructure/v2.StringToInt64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToFloat64HookFunc`
Extra evidence only (never decide): `github.com/go-viper/mapstructure/v2.UnconvertibleTypeError.Error`, `github.com/go-viper/mapstructure/v2.UnconvertibleTypeError.mapstructure`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 2, \('NOT\_REACHABLE', True\): 27\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## act\_\_GO\-2026\-4610

- item: D3c case
- advisory: `GO-2026-4610` Docker CLI Plugins: Uncontrolled Search Path Element Leads to Local Privilege Escalation on Windows in github\.com/docker/cli
- vulnerable module: `github.com/docker/cli@v28.4.0+incompatible`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** MODE2\_NOT\_REACHABLE\_DOWNGRADED
- VulnTrace, legacy targets: **CANT\_DETERMINE** MODE2\_NOT\_REACHABLE\_DOWNGRADED
- govulncheck (reference, not truth): NOT\_REACHABLE at level MODULE; scored as NOT\_REACHABLE

Decision targets (1): `github.com/docker/cli/cli-plugins/manager.defaultSystemPluginDirs`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', True\): 5\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## act\_\_GO\-2026\-6686

- item: D3c case
- advisory: `GO-2026-6686` Possible DoS via unbounded parsing of user and group database files in github\.com/moby/sys/user
- vulnerable module: `github.com/moby/sys/user@v0.4.0`
- stratum: S (curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): NOT\_REACHABLE at level PACKAGE; scored as NOT\_REACHABLE

Decision targets (3): `github.com/moby/sys/user.GetExecUserPath`, `github.com/moby/sys/user.ParseGroupFileFilter`, `github.com/moby/sys/user.ParseGroupFilter`
Extra evidence only (never decide): `github.com/moby/sys/user.ParseGroup`
Per-entry results (result, deciding): \{\('NOT\_REACHABLE', False\): 1, \('NOT\_REACHABLE', True\): 3\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## act\_\_GO\-2025\-4098

- item: D3c case
- advisory: `GO-2025-4098` Container escape and DDoS due to arbitrary write gadgets and procfs write redirects in github\.com/opencontainers/runc
- vulnerable module: `github.com/opencontainers/selinux@v1.12.0`
- stratum: N (no curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** VERIFIER\_REJECTED
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/opencontainers/selinux/go-selinux.GetEnabled`, `github.com/opencontainers/selinux/go-selinux.attrPath$1`, `github.com/opencontainers/selinux/go-selinux.getSELinuxfs$1`, `github.com/opencontainers/selinux/go-selinux.init`, `github.com/opencontainers/selinux/go-selinux.policyRoot$1`, `github.com/opencontainers/selinux/pkg/pwalkdir.init`
- govulncheck trace: `github.com/nektos/act.main (main.go:18) -> github.com/nektos/act/cmd.Execute (cmd/root.go:51) -> github.com/spf13/cobra.Command.Execute (command.go:1071) -> github.com/spf13/cobra.Command.ExecuteC (command.go:1148) -> github.com/spf13/cobra.Command.execute (command.go:1015) -> github.com/nektos/act/cmd.newRunCommand$1 (cmd/root.go:708) -> github.com/nektos/act/pkg/common.Finally$1 (pkg/common/executor.go:227) -> github.com/nektos/act/pkg/runner.startContainer$1 (pkg/runner/run_context.go:671) -> github.com/nektos/act/pkg/runner.startJobContainer$1 (pkg/runner/run_context.go:286) -> github.com/nektos/act/pkg/runner.RunContext.GetBindsAndMounts (pkg/runner/run_context.go:175) -> github.com/opencontainers/selinux/go-selinux.GetEnabled (go-selinux/selinux.go:63)`

Decision targets (32): `github.com/opencontainers/selinux/libcontainer.mountEntry.createOpenMountpoint`, `github.com/opencontainers/selinux/libcontainer.setupUser`, `github.com/opencontainers/selinux/internal/pathrs.MkdirAllInRoot`, `github.com/opencontainers/selinux/internal/pathrs.MkdirAllInRootOpen`, `github.com/opencontainers/selinux/internal/pathrs.Reopen`, `github.com/opencontainers/selinux/libcontainer.mountCgroupV1`, `github.com/opencontainers/selinux/libcontainer.mountCgroupV2`, `github.com/opencontainers/selinux/libcontainer.mountToRootfs`, `github.com/opencontainers/selinux/libcontainer.createDeviceNode`, `github.com/opencontainers/selinux/libcontainer.createMountpoint`, `github.com/opencontainers/selinux/libcontainer/utils.IsLexicallyInRoot`, `github.com/opencontainers/selinux/libcontainer/utils.MkdirAllInRoot`, `github.com/opencontainers/selinux/libcontainer/utils.MkdirAllInRootOpen`, `github.com/opencontainers/selinux/libcontainer.writeSystemProperty`, `github.com/opencontainers/selinux/libcontainer.linuxStandardInit.Init`, `github.com/opencontainers/selinux/internal/pathrs.ProcPidOpen`, `github.com/opencontainers/selinux/internal/pathrs.ProcSelfOpen`, `github.com/opencontainers/selinux/internal/pathrs.ProcThreadSelfOpen`, `github.com/opencontainers/selinux/internal/pathrs.procOpenReopen`, `github.com/opencontainers/selinux/internal/pathrs.OpenInRoot`, `github.com/opencontainers/selinux/libcontainer/apparmor.setProcAttr`, `github.com/opencontainers/selinux/libcontainer/utils.EnsureProcHandle`, `github.com/opencontainers/selinux/libcontainer/utils.fdRangeFrom`, `github.com/opencontainers/selinux/libcontainer.Container.prepareCriuRestoreMounts`, `github.com/opencontainers/selinux/libcontainer.bindMountDeviceNode`, `github.com/opencontainers/selinux/libcontainer.doTmpfsCopyUp`, `github.com/opencontainers/selinux/libcontainer.setRecAttr`, `github.com/opencontainers/selinux/libcontainer/utils.stripRoot`, `github.com/opencontainers/selinux/libcontainer/utils.WithProcfd`, `github.com/opencontainers/selinux/libcontainer/system.Stat`
and 2 more (see the verdict file).
Extra evidence only (never decide): `github.com/opencontainers/selinux/internal/linux.GetPtyPeer`, `github.com/opencontainers/selinux/internal/linux.SetMempolicy`, `github.com/opencontainers/selinux/libcontainer.cleanupTmp`, `github.com/opencontainers/selinux/libcontainer.maskPaths`, `github.com/opencontainers/selinux/libcontainer.mountPropagate`, `github.com/opencontainers/selinux/libcontainer/utils.CleanPath`, `github.com/opencontainers/selinux/libcontainer/utils.Openat`, `github.com/opencontainers/selinux/libcontainer/utils.ProcThreadSelfFd`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 8, \('CANT\_DETERMINE', True\): 32\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |

## act\_\_GO\-2026\-4883

- item: D3c case
- advisory: `GO-2026-4883` Moby has an Off\-by\-one error in its plugin privilege validation in github\.com/docker/docker
- vulnerable module: `github.com/docker/docker@v28.4.0+incompatible`
- stratum: N (no curated vulndb symbols)
- review status: UNREVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** VERIFIER\_REJECTED
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/docker/docker/api.init`, `github.com/docker/docker/api/types.HijackedResponse.Close`, `github.com/docker/docker/api/types.NewHijackedResponse`, `github.com/docker/docker/api/types.init`, `github.com/docker/docker/api/types/blkiodev.ThrottleDevice.String`, `github.com/docker/docker/api/types/blkiodev.WeightDevice.String`, `github.com/docker/docker/api/types/blkiodev.init`, `github.com/docker/docker/api/types/build.init`, `github.com/docker/docker/api/types/checkpoint.init`, `github.com/docker/docker/api/types/common.init`
- govulncheck trace: `github.com/nektos/act.main (main.go:18) -> github.com/nektos/act/cmd.Execute (cmd/root.go:51) -> github.com/spf13/cobra.Command.Execute (command.go:1071) -> github.com/spf13/cobra.Command.ExecuteC (command.go:1148) -> github.com/spf13/cobra.Command.execute (command.go:1015) -> github.com/nektos/act/cmd.newRunCommand$1 (cmd/root.go:708) -> github.com/nektos/act/pkg/common.Finally$1 (pkg/common/executor.go:227) -> github.com/nektos/act/pkg/container.exec$1 (pkg/container/docker_run.go:586) -> github.com/docker/docker/client.Client.ContainerExecAttach (client/container_exec.go:61)`

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

## act\_\_GO\-2026\-4887

- item: D3c case
- advisory: `GO-2026-4887` Moby has AuthZ plugin bypass when provided oversized request bodies in github\.com/docker/docker
- vulnerable module: `github.com/docker/docker@v28.4.0+incompatible`
- stratum: N (no curated vulndb symbols)
- review status: UNREVIEWED
- VulnTrace, CP10 target hygiene: **NOT\_REACHABLE** 
- VulnTrace, legacy targets: **NOT\_REACHABLE** 
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/docker/docker/api.init`, `github.com/docker/docker/api/types.HijackedResponse.Close`, `github.com/docker/docker/api/types.NewHijackedResponse`, `github.com/docker/docker/api/types.init`, `github.com/docker/docker/api/types/blkiodev.ThrottleDevice.String`, `github.com/docker/docker/api/types/blkiodev.WeightDevice.String`, `github.com/docker/docker/api/types/blkiodev.init`, `github.com/docker/docker/api/types/build.init`, `github.com/docker/docker/api/types/checkpoint.init`, `github.com/docker/docker/api/types/common.init`
- govulncheck trace: `github.com/nektos/act.main (main.go:18) -> github.com/nektos/act/cmd.Execute (cmd/root.go:51) -> github.com/spf13/cobra.Command.Execute (command.go:1071) -> github.com/spf13/cobra.Command.ExecuteC (command.go:1148) -> github.com/spf13/cobra.Command.execute (command.go:1015) -> github.com/nektos/act/cmd.newRunCommand$1 (cmd/root.go:708) -> github.com/nektos/act/pkg/common.Finally$1 (pkg/common/executor.go:227) -> github.com/nektos/act/pkg/container.exec$1 (pkg/container/docker_run.go:592) -> github.com/docker/docker/api/types.HijackedResponse.Close (api/types/client.go:22)`

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
