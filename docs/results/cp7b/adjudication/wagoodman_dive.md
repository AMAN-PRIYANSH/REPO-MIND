# Adjudication: github\.com/wagoodman/dive

- application: `github.com/wagoodman/dive` at tag `v0.13.1`, commit `fe98c8a2eb08c443a36e3cc7568078909e298433`
- cases: 3; to adjudicate: 3
- sample rule: All REACHABLE cases\. Of NOT\_REACHABLE and of CANT\_DETERMINE cases: all if there are at most 5, otherwise 5 in ascending order of sha256\("20261028:" \+ case id\)\.
- main packages analysed: `github.com/wagoodman/dive`

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

## dive\_\_GO\-2026\-4610

- advisory: `GO-2026-4610` Docker CLI Plugins: Uncontrolled Search Path Element Leads to Local Privilege Escalation on Windows in github\.com/docker/cli
- vulnerable module: `github.com/docker/cli@v28.0.2+incompatible`
- verdict: **CANT\_DETERMINE**
- reason codes: VERIFIER\_REJECTED
- mode: RELEASE
- evidence level: CANDIDATE\_LEVEL
- symbols analysed: 5
- per-symbol results: \{'CANT\_DETERMINE': 1, 'NOT\_REACHABLE': 4\}
- verifier: FAILED
- adjudicate: all 3 CANT\_DETERMINE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level MODULE\)

Targets analysed (5): `github.com/docker/cli/cli/command/container.cidFile.Close`, `github.com/docker/cli/cli/command/container.cidFile.Write`, `github.com/docker/cli/cli/command/container.copyDockerConfigIntoContainer`, `github.com/docker/cli/cli/command/container.createContainer`, `github.com/docker/cli/cli/command/container.parseSecurityOpts`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| CANT\_DETERMINE | VERIFIER\_REJECTED | NO\_PATH | ABSENT | 1 |
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 4 |

Not covered: `joinElements` (ADDED\_BY\_FIX)

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |

## dive\_\_GO\-2026\-5841

- advisory: `GO-2026-5841` OOB read in github\.com/klauspost/compress/s2
- vulnerable module: `github.com/klauspost/compress@v1.18.0`
- verdict: **NOT\_REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'NOT\_REACHABLE': 1\}
- verifier: PASSED
- adjudicate: all 4 NOT\_REACHABLE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level MODULE\)

Targets analysed (1): `github.com/klauspost/compress/s2.NewDict`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 1 |

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |

## dive\_\_GO\-2025\-3900

- advisory: `GO-2025-3900` Go\-viper's mapstructure May Leak Sensitive Information in Logs in github\.com/go\-viper/mapstructure
- vulnerable module: `github.com/go-viper/mapstructure/v2@v2.2.1`
- verdict: **CANT\_DETERMINE**
- reason codes: ANALYSIS\_FAILED
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 29
- per-symbol results: \{'CANT\_DETERMINE': 3, 'NOT\_REACHABLE': 26\}
- verifier: PASSED
- adjudicate: all 3 CANT\_DETERMINE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Targets analysed (29): `github.com/go-viper/mapstructure/v2.Decoder.decodeBool`, `github.com/go-viper/mapstructure/v2.Decoder.decodeFloat`, `github.com/go-viper/mapstructure/v2.Decoder.decodeInt`, `github.com/go-viper/mapstructure/v2.Decoder.decodeUint`, `github.com/go-viper/mapstructure/v2.StringToBoolHookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex128HookFunc`, `github.com/go-viper/mapstructure/v2.StringToComplex64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToFloat32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToFloat64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPHookFunc`, `github.com/go-viper/mapstructure/v2.StringToIPNetHookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt16HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt32HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt64HookFunc`, `github.com/go-viper/mapstructure/v2.StringToInt8HookFunc`, `github.com/go-viper/mapstructure/v2.StringToIntHookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrHookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPAddrPortHookFunc`, `github.com/go-viper/mapstructure/v2.StringToNetIPPrefixHookFunc`, `github.com/go-viper/mapstructure/v2.StringToTimeDurationHookFunc`
and 9 more (see the verdict file).

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| CANT\_DETERMINE | ANALYSIS\_FAILED | ERROR | ABSENT | 3 |
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 26 |

Not covered: `netParseError.Error` (ADDED\_BY\_FIX), `netParseError.Unwrap` (ADDED\_BY\_FIX), `strconvNumError.Error` (ADDED\_BY\_FIX), `strconvNumError.Unwrap` (ADDED\_BY\_FIX), `timeParseError.Error` (ADDED\_BY\_FIX), `timeParseError.Unwrap` (ADDED\_BY\_FIX), `urlError.Error` (ADDED\_BY\_FIX), `urlError.Unwrap` (ADDED\_BY\_FIX), `wrapNetIPParseAddrError` (ADDED\_BY\_FIX), `wrapNetIPParseAddrPortError` (ADDED\_BY\_FIX)

First error: `symbol StringToNetIPPrefixHookFunc not found in package github.com/go-viper/mapstructure/v2`

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |
