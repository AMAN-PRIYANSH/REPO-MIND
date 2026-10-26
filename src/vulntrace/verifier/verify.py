"""The verifier's checks against the analysed source and call graph (contract section 6).

| Check | How | Applies to |
|---|---|---|
| TARGET_EXISTS | `go list` locates the target's package; helper `funcs` on its files declares the symbol | REACHABLE and NOT_REACHABLE entries |
| CALL_SITE | each call-site file read at the recorded version; the line exists and lies in the caller's declaration (`funcs`) | every edge of a REACHABLE entry's paths |
| EDGE_EXISTS | helper `edges` mode confirms caller -> callee at that exact call site | same |
| PATH_STRUCTURE | starts at main/init of the analysed main package, edges chain, ends at the target | same |
| REACHABLE_HAS_PATH | at least one path passes all of the above | REACHABLE entries |

A NOT_REACHABLE whose package is not in the program (CP2 exception) passes TARGET_EXISTS only if
the package cannot be in the build at all (its module is not in the app's build list); a package
that should exist but cannot be found, or a symbol its package does not declare, is rejected.
That catches import-path mapping errors that would otherwise read as NOT_REACHABLE.

Downgrade-only: every change is REACHABLE/NOT_REACHABLE -> CANT_DETERMINE (VERIFIER_REJECTED);
`aggregate.assert_downgrade_only` runs on every result before it is returned.
"""

import copy
import json
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vulntrace.env import go_env
from vulntrace.methods.helper import CONTRACT_VERSION, DEFAULT_TIMEOUT_S, HelperError, run_helper
from vulntrace.pipeline.aggregate import assert_downgrade_only, case_result
from vulntrace.verdict import CANT_DETERMINE, NOT_REACHABLE, REACHABLE, VERIFIER_REJECTED, symbol_verdict
from vulntrace.verifier import checks as ck
from vulntrace.verifier.sources import FileSource

FOUND, NOT_IN_BUILD, MISSING, UNKNOWN = "FOUND", "NOT_IN_BUILD", "MISSING", "UNKNOWN"


class VerifierError(Exception):
    pass


@dataclass
class PackageLocation:
    status: str                     # FOUND, NOT_IN_BUILD, MISSING, UNKNOWN
    files: list[str] = field(default_factory=list)   # FileSource file forms of the package's Go files
    reason: str = ""
    ignored: list[str] = field(default_factory=list)  # files of the package excluded by build constraints


FuncsFn = Callable[[str, str], list[dict[str, Any]] | None]           # (file name, text) -> decls, None if unparsable
EdgesFn = Callable[[Path, str, list[dict[str, Any]]], list[dict[str, Any]]]
LocateFn = Callable[[str], PackageLocation]


@dataclass
class VerifyContext:
    module_dir: Path
    source: FileSource
    funcs_fn: FuncsFn
    edges_fn: EdgesFn
    locate_fn: LocateFn
    incomplete: bool = False


# --- default implementations (Go helper and `go list`) ----------------------------------------------
def helper_funcs(binary=None, timeout: float = 120.0, runner=None) -> FuncsFn:
    """Helper `funcs` mode on the given text (written to a temporary file, so it is the text read
    at the recorded version, not whatever is on disk)."""
    def run(name: str, text: str) -> list[dict[str, Any]] | None:
        with tempfile.TemporaryDirectory(prefix="vt_verify_") as tmp:
            f = Path(tmp) / "f.go"
            f.write_text(text, encoding="utf-8")
            req = {"contract_version": CONTRACT_VERSION, "mode": "funcs", "module_dir": Path(tmp).as_posix(),
                   "files": ["f.go"]}
            try:
                resp = run_helper("funcs", req, binary=binary, timeout=timeout, runner=runner)
            except HelperError:
                return None
            if not resp["ok"]:
                return None
            return list(resp["results"][0]["functions"])
    return run


def helper_edges(binary=None, timeout: float = DEFAULT_TIMEOUT_S, runner=None) -> EdgesFn:
    def run(module_dir: Path, main: str, edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        req = {"contract_version": CONTRACT_VERSION, "mode": "edges", "module_dir": Path(module_dir).resolve().as_posix(),
               "main_packages": [main], "build": {"tags": [], "goos": None, "goarch": None},
               "edges": [{"caller": e["caller"], "callee": e["callee"], "call_site": e["call_site"]} for e in edges]}
        try:
            resp = run_helper("edges", req, binary=binary, timeout=timeout, runner=runner)
        except HelperError as exc:
            raise VerifierError(f"edges: {exc.code}: {exc.message.splitlines()[0][:200] if exc.message else ''}") from exc
        if not resp["ok"]:
            raise VerifierError(f"edges: {resp['error']['code']}: {resp['error']['message'][:200]}")
        return resp["results"]
    return run


def go_list_locator(module_dir: Path, runner=subprocess.run, timeout: float = 300.0) -> LocateFn:
    """Locate a package with `go list` in the app module (no code runs); classify a failure by
    whether the package's module is in the app's build list (`go list -m all`)."""
    module_dir = Path(module_dir).resolve()
    state: dict[str, Any] = {}

    def build_list() -> list[str] | None:
        if "mods" not in state:
            try:
                p = runner(["go", "list", "-m", "-e", "-f", "{{.Path}}", "all"], cwd=module_dir, capture_output=True,
                           text=True, env=go_env(), timeout=timeout)
                state["mods"] = p.stdout.split() if p.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                state["mods"] = None
        return state["mods"]

    def locate(pkg: str) -> PackageLocation:
        try:
            p = runner(["go", "list", "-e", "-json=ImportPath,Dir,GoFiles,IgnoredGoFiles,Error,Standard", pkg],
                       cwd=module_dir, capture_output=True, text=True, env=go_env(), timeout=timeout)
            info = json.loads(p.stdout) if p.stdout.strip() else {}
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            return PackageLocation(UNKNOWN, reason=f"go list failed: {exc}")
        err = (info.get("Error") or {}).get("Err")

        def forms(names):
            d, out = Path(info["Dir"]), []
            for g in names or []:
                f = d / g
                try:
                    out.append(f.relative_to(module_dir).as_posix())
                except ValueError:
                    out.append(f.as_posix())
            return out

        excluded_all = bool(err) and "build constraints exclude all Go files" in err
        if info.get("Dir") and (info.get("GoFiles") or excluded_all) and (not err or excluded_all):
            return PackageLocation(FOUND, files=forms(info.get("GoFiles")), ignored=forms(info.get("IgnoredGoFiles")),
                                   reason="every Go file is excluded by build constraints" if excluded_all else "")
        mods = build_list()
        if mods is None:
            return PackageLocation(UNKNOWN, reason="package not found and the build list could not be read: "
                                                   + (err or "no Go files").splitlines()[0][:200])
        owner = [m for m in mods if pkg == m or pkg.startswith(m + "/")]
        if owner:
            return PackageLocation(MISSING, reason=f"module {max(owner, key=len)} is in the build but package {pkg} "
                                                   f"was not found: {(err or 'no Go files').splitlines()[0][:200]}")
        return PackageLocation(NOT_IN_BUILD, reason=f"no module in the app's build list provides {pkg}")
    return locate


# --- verification -----------------------------------------------------------------------------------
class _Files:
    """Read once, parse once."""

    def __init__(self, ctx: VerifyContext):
        self.ctx = ctx
        self._decls: dict[str, tuple[int | None, list[dict[str, Any]] | None]] = {}

    def info(self, file: str) -> tuple[int | None, list[dict[str, Any]] | None]:
        if file not in self._decls:
            text = self.ctx.source.read(file)
            if text is None:
                self._decls[file] = (None, None)
            else:
                self._decls[file] = (len(text.splitlines()), self.ctx.funcs_fn(file, text))
        return self._decls[file]


def _target_check(entry: dict[str, Any], ctx: VerifyContext, files: _Files,
                  located: dict[str, PackageLocation]) -> tuple[ck.Failure | None, bool]:
    """(failure or None, skipped)."""
    pkg, sym = entry["target"]["package"], entry["target"]["symbol"]
    if pkg not in located:
        located[pkg] = ctx.locate_fn(pkg)
    loc = located[pkg]
    if loc.status == FOUND:
        decls: list[dict[str, Any]] = []
        for f in loc.files:
            _, d = files.info(f)
            if d is None:
                return ck.Failure(ck.TARGET_EXISTS, f"cannot read or parse {f} of package {pkg}"), False
            decls += d
        if ck.declares(decls, sym):
            return None, False
        # Declared only in files this build configuration excludes: no code of it is in the build, which
        # supports NOT_REACHABLE (for this configuration, as every verdict states) but never REACHABLE.
        if entry["result"] == NOT_REACHABLE and loc.ignored:
            ignored: list[dict[str, Any]] = []
            for f in loc.ignored:
                _, d = files.info(f)
                ignored += d or []
            if ck.declares(ignored, sym):
                return None, True
        return ck.Failure(ck.TARGET_EXISTS, f"package {pkg} does not declare {ck.normalise_symbol(sym)}"
                          + (f" ({loc.reason})" if loc.reason else "")), False
    if loc.status == NOT_IN_BUILD and entry["result"] == NOT_REACHABLE and entry.get("package_not_in_program"):
        return None, True
    return ck.Failure(ck.TARGET_EXISTS, f"{loc.status}: {loc.reason}"), False


def verify(verdict: dict[str, Any], ctx: VerifyContext) -> dict[str, Any]:
    """Return a verified copy of `verdict` (the input is not modified)."""
    after = copy.deepcopy(verdict)
    files = _Files(ctx)
    located: dict[str, PackageLocation] = {}
    stats = {k: {"run": 0, "failed": 0, "skipped": 0} for k in ck.CHECK_KINDS}
    failures_by_entry: dict[int, list[ck.Failure]] = {}

    def count(kind: str, failed: bool, skipped: bool = False) -> None:
        stats[kind]["run" if not skipped else "skipped"] += 1
        if failed:
            stats[kind]["failed"] += 1

    entries = after["per_symbol"]
    # 1. target symbol exists at the analysed version
    for i, e in enumerate(entries):
        if e["result"] not in (REACHABLE, NOT_REACHABLE):
            continue
        f, skipped = _target_check(e, ctx, files, located)
        count(ck.TARGET_EXISTS, f is not None, skipped)
        if f:
            failures_by_entry.setdefault(i, []).append(f)

    # 2. paths of REACHABLE entries: structure and call sites, then edges (one helper call per main)
    path_failures: dict[tuple[int, int], list[ck.Failure]] = {}
    edges_wanted: dict[str, list[tuple[int, int, int, dict[str, Any]]]] = {}
    for i, e in enumerate(entries):
        if e["result"] != REACHABLE:
            continue
        for pi, path in enumerate(e.get("paths") or []):
            fl = [ck.Failure(x.check, x.reason, pi, x.edge_index)
                  for x in ck.check_structure(path, e.get("main_package") or "", e["target"])]
            count(ck.PATH_STRUCTURE, bool(fl))
            for ei, edge in enumerate(path.get("edges") or []):
                site = edge.get("call_site") or {}
                n, decls = files.info(site["file"]) if site.get("file") else (None, None)
                f = ck.check_site(edge, ei, n, decls)
                count(ck.CALL_SITE, f is not None)
                if f:
                    fl.append(ck.Failure(f.check, f.reason, pi, ei))
                edges_wanted.setdefault(e.get("main_package") or "", []).append((i, pi, ei, edge))
            path_failures[(i, pi)] = fl
    for main, wanted in edges_wanted.items():
        uniq: list[dict[str, Any]] = []
        index: dict[str, int] = {}
        for _, _, _, edge in wanted:
            key = json.dumps([edge["caller"], edge["callee"], edge["call_site"]], sort_keys=True)
            if key not in index:
                index[key] = len(uniq)
                uniq.append(edge)
        try:
            results = ctx.edges_fn(ctx.module_dir, main, uniq)
            if len(results) != len(uniq):
                raise VerifierError("edges: result count does not match the query")
            err = None
        except VerifierError as exc:
            results, err = None, str(exc)
        for i, pi, ei, edge in wanted:
            key = json.dumps([edge["caller"], edge["callee"], edge["call_site"]], sort_keys=True)
            if results is None:
                count(ck.VERIFIER_ERROR, True)
                path_failures[(i, pi)].append(ck.Failure(ck.VERIFIER_ERROR, err or "edges failed", pi, ei))
                continue
            r = results[index[key]]
            ok = bool(r.get("exists")) and r.get("caller") == edge["caller"] and r.get("callee") == edge["callee"]
            count(ck.EDGE_EXISTS, not ok)
            if not ok:
                path_failures[(i, pi)].append(ck.Failure(
                    ck.EDGE_EXISTS, f"call graph has no edge {edge['caller']} -> {edge['callee']} at "
                                    f"{edge['call_site'].get('file')}:{edge['call_site'].get('line')}", pi, ei))

    # 3. decide per entry (only downwards)
    changed = 0
    for i, e in enumerate(entries):
        if e["result"] == REACHABLE:
            paths = e.get("paths") or []
            good = next((pi for pi in range(len(paths)) if not path_failures.get((i, pi))), None)
            count(ck.REACHABLE_HAS_PATH, good is None)
            if good is None:
                for pi in range(len(paths)):
                    failures_by_entry.setdefault(i, []).extend(path_failures.get((i, pi), []))
                why = "no call path returned" + (f" (paths_omitted={e.get('paths_omitted')})" if e.get("paths_omitted") else "") \
                    if not paths else f"none of {len(paths)} path(s) passed every check"
                failures_by_entry.setdefault(i, []).append(ck.Failure(ck.REACHABLE_HAS_PATH, why))
            elif not failures_by_entry.get(i):
                e["verified_path"] = copy.deepcopy(paths[good])
        fl = failures_by_entry.get(i)
        if fl and e["result"] in (REACHABLE, NOT_REACHABLE):
            if e["result"] == REACHABLE:
                e["result"], e["reason_code"] = symbol_verdict(e["methods"]["CALLGRAPH_VTA"],
                                                               e["methods"]["LINKER_PRESENCE"], "FAILED")
            else:
                e["result"], e["reason_code"] = CANT_DETERMINE, VERIFIER_REJECTED
            e["verified_path"] = None
            changed += 1
        if fl:
            e["verifier_failures"] = [x.to_json() for x in fl]

    all_failures = [dict(x.to_json(entries[i]["target"], entries[i].get("main_package")))
                    for i, fl in sorted(failures_by_entry.items()) for x in fl]
    if changed:
        after["verdict"], after["reason_codes"] = case_result(entries, incomplete=ctx.incomplete)
    checks_run = sum(v["run"] for v in stats.values())
    after["verification"] = {
        "status": "NOT_RUN" if checks_run == 0 else ("FAILED" if all_failures else "PASSED"),
        "checks_run": checks_run, "failures": all_failures,
        "checks_by_kind": {k: v for k, v in stats.items() if any(v.values())},
        "downgraded": changed, "file_source": ctx.source.description,
    }
    assert_downgrade_only(verdict, after)
    return after
