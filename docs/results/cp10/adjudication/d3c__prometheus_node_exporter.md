# CP10 adjudication: d3c\_\_prometheus\_node\_exporter

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

## node\_exporter\_\_GO\-2025\-4098

- item: D3c case
- advisory: `GO-2025-4098` Container escape and DDoS due to arbitrary write gadgets and procfs write redirects in github\.com/opencontainers/runc
- vulnerable module: `github.com/opencontainers/selinux@v1.12.0`
- stratum: N (no curated vulndb symbols)
- review status: REVIEWED
- VulnTrace, CP10 target hygiene: **CANT\_DETERMINE** VERIFIER\_REJECTED
- VulnTrace, legacy targets: **CANT\_DETERMINE** VERIFIER\_REJECTED
- govulncheck (reference, not truth): REACHABLE at level SYMBOL; scored as REACHABLE
- govulncheck symbols called: `github.com/opencontainers/selinux/go-selinux.DefaultEnforceMode`, `github.com/opencontainers/selinux/go-selinux.EnforceMode`, `github.com/opencontainers/selinux/go-selinux.GetEnabled`, `github.com/opencontainers/selinux/go-selinux.attrPath$1`, `github.com/opencontainers/selinux/go-selinux.getSELinuxfs$1`, `github.com/opencontainers/selinux/go-selinux.init`, `github.com/opencontainers/selinux/go-selinux.policyRoot$1`, `github.com/opencontainers/selinux/pkg/pwalkdir.init`
- govulncheck trace: `github.com/prometheus/node_exporter.init (node_exporter.go:38) -> github.com/prometheus/node_exporter/collector.init (collector/selinux_linux.go:22) -> github.com/opencontainers/selinux/go-selinux.init (go-selinux/doc.go:13)`

Decision targets (32): `github.com/opencontainers/selinux/libcontainer.mountEntry.createOpenMountpoint`, `github.com/opencontainers/selinux/libcontainer.setupUser`, `github.com/opencontainers/selinux/internal/pathrs.MkdirAllInRoot`, `github.com/opencontainers/selinux/internal/pathrs.MkdirAllInRootOpen`, `github.com/opencontainers/selinux/internal/pathrs.Reopen`, `github.com/opencontainers/selinux/libcontainer.mountCgroupV1`, `github.com/opencontainers/selinux/libcontainer.mountCgroupV2`, `github.com/opencontainers/selinux/libcontainer.mountToRootfs`, `github.com/opencontainers/selinux/libcontainer.createDeviceNode`, `github.com/opencontainers/selinux/libcontainer.createMountpoint`, `github.com/opencontainers/selinux/libcontainer/utils.IsLexicallyInRoot`, `github.com/opencontainers/selinux/libcontainer/utils.MkdirAllInRoot`, `github.com/opencontainers/selinux/libcontainer/utils.MkdirAllInRootOpen`, `github.com/opencontainers/selinux/libcontainer.writeSystemProperty`, `github.com/opencontainers/selinux/libcontainer.linuxStandardInit.Init`, `github.com/opencontainers/selinux/internal/pathrs.ProcPidOpen`, `github.com/opencontainers/selinux/internal/pathrs.ProcSelfOpen`, `github.com/opencontainers/selinux/internal/pathrs.ProcThreadSelfOpen`, `github.com/opencontainers/selinux/internal/pathrs.procOpenReopen`, `github.com/opencontainers/selinux/internal/pathrs.OpenInRoot`, `github.com/opencontainers/selinux/libcontainer/apparmor.setProcAttr`, `github.com/opencontainers/selinux/libcontainer/utils.EnsureProcHandle`, `github.com/opencontainers/selinux/libcontainer/utils.fdRangeFrom`, `github.com/opencontainers/selinux/libcontainer.Container.prepareCriuRestoreMounts`, `github.com/opencontainers/selinux/libcontainer.bindMountDeviceNode`, `github.com/opencontainers/selinux/libcontainer.doTmpfsCopyUp`, `github.com/opencontainers/selinux/libcontainer.setRecAttr`, `github.com/opencontainers/selinux/libcontainer/utils.stripRoot`, `github.com/opencontainers/selinux/libcontainer/utils.WithProcfd`, `github.com/opencontainers/selinux/libcontainer/system.Stat`
and 2 more (see the verdict file).
Extra evidence only (never decide): `github.com/opencontainers/selinux/internal/linux.GetPtyPeer`, `github.com/opencontainers/selinux/internal/linux.SetMempolicy`, `github.com/opencontainers/selinux/libcontainer.cleanupTmp`, `github.com/opencontainers/selinux/libcontainer.maskPaths`, `github.com/opencontainers/selinux/libcontainer.mountPropagate`, `github.com/opencontainers/selinux/libcontainer/utils.CleanPath`, `github.com/opencontainers/selinux/libcontainer/utils.Openat`, `github.com/opencontainers/selinux/libcontainer/utils.ProcThreadSelfFd`
Per-entry results (result, deciding): \{\('CANT\_DETERMINE', False\): 16, \('CANT\_DETERMINE', True\): 64\}

| field | value |
|---|---|
| truth | |
| confidence | |
| route | |
| by | |
| note | |
