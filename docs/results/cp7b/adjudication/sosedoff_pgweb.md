# Adjudication: github\.com/sosedoff/pgweb

- application: `github.com/sosedoff/pgweb` at tag `v0.17.0`, commit `6b0b0244d1aefd6971999b03481eeeaa4ec7cf55`
- cases: 1; to adjudicate: 1
- sample rule: All REACHABLE cases\. Of NOT\_REACHABLE and of CANT\_DETERMINE cases: all if there are at most 5, otherwise 5 in ascending order of sha256\("20261028:" \+ case id\)\.
- main packages analysed: `github.com/sosedoff/pgweb`, `github.com/sosedoff/pgweb/config/examples/connect_backend_go`

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

## pgweb\_\_GO\-2025\-4188

- advisory: `GO-2025-4188` Logrus is vulnerable to DoS when using Entry\.writerScanner in github\.com/sirupsen/logrus
- vulnerable module: `github.com/sirupsen/logrus@v1.9.0`
- verdict: **CANT\_DETERMINE**
- reason codes: METHOD\_DISAGREEMENT
- mode: FIX
- evidence level: CHANGED\_FUNCTION\_LEVEL
- symbols analysed: 5
- per-symbol results: \{'CANT\_DETERMINE': 5, 'NOT\_REACHABLE': 5\}
- verifier: PASSED
- adjudicate: all 3 CANT\_DETERMINE cases
- govulncheck (reference, not truth): NOT\_REACHABLE \(finding level PACKAGE\)

Targets analysed (5): `github.com/sirupsen/logrus.Entry.Writer`, `github.com/sirupsen/logrus.Entry.WriterLevel`, `github.com/sirupsen/logrus.Entry.writerScanner`, `github.com/sirupsen/logrus.Logger.WriterLevel`, `github.com/sirupsen/logrus.writerFinalizer`

| result | reason | call graph | linker | entries |
|---|---|---|---|---|
| CANT\_DETERMINE | METHOD\_DISAGREEMENT | NO\_PATH | PRESENT | 5 |
| NOT\_REACHABLE |  | NO\_PATH | ABSENT | 5 |

| field | value |
|---|---|
| adjudication | |
| by | |
| note | |
| truth | |
