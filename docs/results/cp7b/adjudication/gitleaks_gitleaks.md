# Adjudication: github\.com/gitleaks/gitleaks

- application: `github.com/gitleaks/gitleaks` at tag `v8.30.0`, commit `6eaad039603a4de39fddd1cf5f727391efe9974e`
- cases: 2; to adjudicate: 2
- sample rule: All REACHABLE cases\. Of NOT\_REACHABLE and of CANT\_DETERMINE cases: all if there are at most 5, otherwise 5 in ascending order of sha256\("20261028:" \+ case id\)\.
- main packages analysed: `github.com/zricethezav/gitleaks/v8`, `github.com/zricethezav/gitleaks/v8/cmd/generate/config`

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

## gitleaks\_\_GO\-2026\-5841

- advisory: `GO-2026-5841` OOB read in github\.com/klauspost/compress/s2
- vulnerable module: `github.com/klauspost/compress@v1.17.11`
- verdict: **NOT\_REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 1
- per-symbol results: \{'NOT\_REACHABLE': 2\}
- verifier: PASSED
- adjudicate: all 4 NOT\_REACHABLE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Targets analysed (1): `github.com/klauspost/compress/s2.NewDict`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 2 |

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |

## gitleaks\_\_GO\-2025\-4020

- advisory: `GO-2025-4020` DoS risk due to unrestricted RAR dictionary sizes in github\.com/nwaples/rardecode
- vulnerable module: `github.com/nwaples/rardecode/v2@v2.1.0`
- verdict: **REACHABLE**
- reason codes: none
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 6
- per-symbol results: \{'CANT\_DETERMINE': 9, 'NOT\_REACHABLE': 2, 'REACHABLE': 1\}
- verifier: PASSED
- adjudicate: every REACHABLE case
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Reachable targets (1): `github.com/nwaples/rardecode/v2.FileSystem` (context only)

### Path 1: `github.com/nwaples/rardecode/v2.FileSystem` from `github.com/zricethezav/gitleaks/v8`

Target context only (no line of it changed in the fix, it touched diff context): True

1. `github.com/zricethezav/gitleaks/v8.main` calls `github.com/zricethezav/gitleaks/v8/cmd.Execute` (STATIC) at `main.go:18` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/main.go#L18)

```go
17  
18> 	cmd.Execute()
19  }
```

2. `github.com/zricethezav/gitleaks/v8/cmd.Execute` calls `github.com/spf13/cobra.Command.Execute` (STATIC) at `cmd/root.go:225` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/cmd/root.go#L225)

```go
224  func Execute() {
225> 	if err := rootCmd.Execute(); err != nil {
226  		if strings.Contains(err.Error(), "unknown flag") {
```

3. `github.com/spf13/cobra.Command.Execute` calls `github.com/spf13/cobra.Command.ExecuteC` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1071` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1071)

```go
1070  func (c *Command) Execute() error {
1071> 	_, err := c.ExecuteC()
1072  	return err
```

4. `github.com/spf13/cobra.Command.ExecuteC` calls `github.com/spf13/cobra.Command.execute` (STATIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1148` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1148)

```go
1147  
1148> 	err = cmd.execute(flags)
1149  	if err != nil {
```

5. `github.com/spf13/cobra.Command.execute` calls `github.com/zricethezav/gitleaks/v8/cmd.runDetect` (DYNAMIC) at `$GOMODCACHE/github.com/spf13/cobra@v1.9.1/command.go:1019` [source](https://github.com/spf13/cobra/blob/v1.9.1/command.go#L1019)

```go
1018  	} else {
1019> 		c.Run(c, argWoFlags)
1020  	}
```

6. `github.com/zricethezav/gitleaks/v8/cmd.runDetect` calls `github.com/zricethezav/gitleaks/v8/detect.Detector.DetectSource` (STATIC) at `cmd/detect.go:76` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/cmd/detect.go#L76)

```go
75  	if noGit {
76> 		findings, err = detector.DetectSource(
77  			cmd.Context(), &sources.Files{
```

7. `github.com/zricethezav/gitleaks/v8/detect.Detector.DetectSource` calls `github.com/zricethezav/gitleaks/v8/sources.File.Fragments` (DYNAMIC) at `detect/detect.go:209` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/detect/detect.go#L209)

```go
208  func (d *Detector) DetectSource(ctx context.Context, source sources.Source) ([]report.Finding, error) {
209> 	err := source.Fragments(ctx, func(fragment sources.Fragment, err error) error {
210  		logContext := logging.With()
```

8. `github.com/zricethezav/gitleaks/v8/sources.File.Fragments` calls `github.com/zricethezav/gitleaks/v8/sources.File.extractorFragments` (STATIC) at `sources/file.go:78` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/sources/file.go#L78)

```go
77  		if extractor, ok := format.(archives.Extractor); ok {
78> 			return s.extractorFragments(ctx, extractor, s.Content, yield)
79  		}
```

9. `github.com/zricethezav/gitleaks/v8/sources.File.extractorFragments` calls `github.com/mholt/archives.Rar.Extract` (DYNAMIC) at `sources/file.go:114` [source](https://github.com/gitleaks/gitleaks/blob/6eaad039603a4de39fddd1cf5f727391efe9974e/sources/file.go#L114)

```go
113  
114> 	return extractor.Extract(ctx, reader, func(_ context.Context, d archives.FileInfo) error {
115  		if d.IsDir() {
```

10. `github.com/mholt/archives.Rar.Extract` calls `github.com/nwaples/rardecode/v2.FileSystem` (STATIC) at `$GOMODCACHE/github.com/mholt/archives@v0.1.2/rar.go:92` [source](https://github.com/mholt/archives/blob/v0.1.2/rar.go#L92)

```go
91  	if r.FS != nil {
92> 		options = append(options, rardecode.FileSystem(r.FS))
93  	}
```


| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
