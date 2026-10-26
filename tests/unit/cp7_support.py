"""Fakes for the CP7 pipeline and verifier tests: no Go, no git, no network, no model."""

from pathlib import Path
from typing import Any

from vulntrace.pipeline import app as app_mod, triage
from vulntrace.verifier import verify as vf

APP = Path("/fake/app")
MOD = "example.com/app"
LIB = "example.com/lib"


def path(main: str, target: dict[str, str], hops: list[tuple[str, str, int]], entry: str = "main") -> dict[str, Any]:
    """A CallPath from `main.<entry>` through `hops` [(callee, file, line)] to the target."""
    edges, caller = [], f"{main}.{entry}"
    for callee, file, line in hops:
        edges.append({"caller": caller, "callee": callee, "call_site": {"file": file, "line": line}, "kind": "STATIC"})
        caller = callee
    return {"entry": {"package": main, "symbol": entry}, "target": dict(target), "edges": edges}


def vta_result(target, main, result, paths=None, code=None, not_in_program=False):
    return {"schema_version": "1.0", "method": "CALLGRAPH_VTA", "target": dict(target), "main_package": main,
            "result": result, "error": {"code": code, "message": f"{code}: fake"} if result == "ERROR" else None,
            "details": {"paths": paths or [], "path": (paths or [None])[0], "paths_omitted": None,
                        "package_not_in_program": not_in_program, "matched_functions": [],
                        "toolchain": {"go_version": "go1.24.7", "goos": "linux", "goarch": "amd64",
                                      "x_tools_version": "v0.42.0"}, "stats": None},
            "duration_ms": 1}


def linker_result(target, main, result, code=None):
    return {"schema_version": "1.0", "method": "LINKER_PRESENCE", "target": dict(target), "main_package": main,
            "result": result, "error": {"code": code, "message": f"{code}: fake"} if result == "ERROR" else None,
            "details": {"matched_binary_symbols": [], "build_flags": ["-gcflags=all=-l"], "go_version": "go1.24.7",
                        "goos": "linux", "goarch": "amd64"}, "duration_ms": 1}


class FakeMethod:
    """table[(main, package, symbol)] -> (result, extra kwargs); default given by `default`."""

    def __init__(self, kind: str, table: dict | None = None, default=("NO_PATH", {})):
        self.kind, self.table, self.default = kind, table or {}, default
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def __call__(self, module_dir, main, targets):
        self.calls.append((main, [dict(t) for t in targets]))
        out = []
        for t in targets:
            res, kw = self.table.get((main, t["package"], t["symbol"]), self.default)
            out.append(vta_result(t, main, res, **kw) if self.kind == "vta" else linker_result(t, main, res, **kw))
        return out


def fake_inspect(mains=("example.com/app/cmd/a",), skipped=(), list_error=None, module=MOD):
    def inspect(app, mains_arg=None, max_mains=10, commit=None, **kw):
        info = app_mod.AppInfo(path=str(app), module_dir=Path(app), module=module, commit=commit or "c0ffee",
                               commit_source="EVIDENCE" if commit else "GIT_HEAD", dirty=False, git_prefix="")
        info.mains, info.mains_skipped, info.list_error = list(mains), list(skipped), list_error
        return info
    # the pipeline calls inspect(app, mains=..., max_mains=..., commit=...)
    return lambda app, mains=None, max_mains=10, commit=None: inspect(app, mains, max_mains, commit)


class FakeSource:
    def __init__(self, files: dict[str, str]):
        self.files = files
        self.description = "fake source"

    def read(self, file):
        return self.files.get(file)


def decls_from_text(text: str) -> list[dict[str, Any]]:
    """A tiny stand-in for helper `funcs`: lines `func NAME` open a declaration that ends at the
    next line `}`; `func (T) NAME` gives `T.NAME`."""
    out, cur = [], None
    for i, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if s.startswith("func "):
            rest = s[5:]
            if rest.startswith("("):
                recv = rest[1:rest.index(")")].split()[-1].lstrip("*")
                name = rest[rest.index(")") + 1:].strip().split("(")[0]
                sym = f"{recv}.{name}"
            else:
                sym = rest.split("(")[0].split("[")[0]
            cur = {"symbol": sym, "start": i, "end": i}
            out.append(cur)
            if s.endswith("}"):
                cur = None
        elif cur is not None:
            cur["end"] = i
            if s == "}":
                cur = None
    return out


def ctx(files: dict[str, str], edges: set[tuple[str, str, str, int]] | None = None,
        located: dict[str, vf.PackageLocation] | None = None, edges_error: str | None = None,
        incomplete: bool = False) -> vf.VerifyContext:
    def edges_fn(module_dir, main, queries):
        if edges_error:
            raise vf.VerifierError(edges_error)
        return [{"caller": q["caller"], "callee": q["callee"], "call_site": q["call_site"],
                 "exists": (q["caller"], q["callee"], q["call_site"]["file"], q["call_site"]["line"]) in (edges or set())}
                for q in queries]

    def locate(pkg):
        return (located or {}).get(pkg, vf.PackageLocation(vf.MISSING, reason="fake: not located"))

    return vf.VerifyContext(module_dir=APP, source=FakeSource(files), funcs_fn=lambda name, text: decls_from_text(text),
                            edges_fn=edges_fn, locate_fn=locate, incomplete=incomplete)


# A small consistent world: main.go calls lib.Parse at line 4; lib.go declares Parse.
MAIN_PKG = "example.com/app/cmd/a"
TARGET = {"package": LIB, "symbol": "Parse"}
FILES = {
    "cmd/a/main.go": "package main\n\nfunc main() {\n\tlib.Parse(\"x\")\n}\n",
    "/modcache/example.com/lib@v1.0.0/lib.go": "package lib\n\nfunc Parse(s string) string {\n\treturn s\n}\n",
}
GOOD_PATH = path(MAIN_PKG, TARGET, [(f"{LIB}.Parse", "cmd/a/main.go", 4)])
GOOD_EDGES = {(f"{MAIN_PKG}.main", f"{LIB}.Parse", "cmd/a/main.go", 4)}
LOCATED = {LIB: vf.PackageLocation(vf.FOUND, files=["/modcache/example.com/lib@v1.0.0/lib.go"])}


def good_ctx(**kw) -> vf.VerifyContext:
    kw.setdefault("located", LOCATED)
    return ctx(FILES, GOOD_EDGES, **kw)


def runners(vta: FakeMethod, linker: FakeMethod, inspect=None, verifier_ctx=None, rank=None, lift=None) -> triage.Runners:
    return triage.Runners(vta=vta, linker=linker, inspect=inspect or fake_inspect(),
                          verifier_ctx=verifier_ctx, rank=rank, lift=lift)


def fix_evidence(cands: list[tuple[str, str, str]], status: str = "AVAILABLE") -> dict[str, Any]:
    """FixEvidence with candidates [(package_dir, symbol, side)], each with one hunk changing its first line."""
    cs, hs = [], []
    for i, (d, sym, side) in enumerate(cands, start=1):
        rng = {"file": f"{d}/f{i}.go".lstrip("/"), "start": 10, "end": 20}
        cs.append({"candidate_id": f"c{i}", "package_dir": d, "symbol": sym, "side": side,
                   "old_range": rng if side != "NEW" else None, "new_range": rng if side != "OLD" else None,
                   "hunk_ids": [f"h{i}"]})
        hs.append({"hunk_id": f"h{i}", "file": rng["file"], "old_start": 9, "old_lines": 3, "new_start": 9,
                   "new_lines": 3, "text": " ctx\n-old\n+new\n ctx"})
    return {"schema_version": "1.0", "case_id": "GO-TEST-1", "status": status, "commits": [], "candidates": cs,
            "hunks": hs, "unfetchable_commits": [], "non_go_files_changed": [], "test_files_changed": 0}


def advisory(fix: bool = True, module: str = LIB) -> dict[str, Any]:
    return {"id": "GO-TEST-1", "summary": "lib: Parse mishandles input", "details": "", "module": module,
            "vulnerable_at": "1.0.0", "fixed_in": "1.0.1",
            "fix_commits": [{"host": "github.com", "owner": "example", "repo": "lib", "sha": "f" * 40}] if fix else []}


def release_range(cands: list[tuple[str, str, str]], status: str = "AVAILABLE") -> tuple[dict, dict]:
    cs, code = [], {}
    for i, (d, sym, side) in enumerate(cands, start=1):
        rng = {"file": f"{d}/r{i}.go".lstrip("/"), "start": 1, "end": 5}
        cs.append({"candidate_id": f"r{i}", "package_dir": d, "symbol": sym, "side": side,
                   "old_range": rng if side != "NEW" else None, "new_range": rng if side != "OLD" else None})
        code[f"r{i}"] = {"package_name": d.split("/")[-1] or "lib", "doc": "", "signature": f"func {sym}()",
                         "body": f"func {sym}() {{ parse input }}", "body_side": "OLD", "file": rng["file"], "missing": False}
    rr = {"schema_version": "1.0", "case_id": "GO-TEST-1", "module": LIB, "status": status,
          "from": {"version": "1.0.0", "ref": "v1.0.0", "commit": "a" * 40},
          "to": {"version": "1.0.1", "ref": "v1.0.1", "commit": "b" * 40}, "candidates": cs,
          "commits": [{"sha": "b" * 40, "subject": "fix parse", "body": "", "touches_candidates": [c["candidate_id"] for c in cs]}],
          "non_go_files_changed": [], "test_files_changed": 0}
    return rr, {"case_id": "GO-TEST-1", "candidates": code}
