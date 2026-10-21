"""Linker-presence reachability method (CP1).

Builds a main package with inlining disabled, lists the binary's symbols with
`go tool nm`, and reports whether the target symbol survived the linker's
dead-code elimination. PRESENT/ABSENT are not verdicts.
"""

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from vulntrace.env import go_env

METHOD = "LINKER_PRESENCE"
SCHEMA_VERSION = "1.0"
NO_INLINE_FLAGS = ["-gcflags=all=-l"]

E_UNSUPPORTED = "UNSUPPORTED_SYMBOL_FORM"
E_BUILD = "BUILD_FAILED"
E_NM = "NM_FAILED"
E_NO_GO = "GO_NOT_FOUND"

TEXT_SYMBOL_TYPES = frozenset("Tt")

_NM_LINE = re.compile(r"^\s*([0-9a-fA-F]+)?\s+(\S)\s+(\S.*?)\s*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnsupportedSymbolForm(ValueError):
    pass


def normalize_import_path(path: str) -> str:
    """Go import paths always use forward slashes, even when given Windows-style."""
    return path.replace("\\", "/").strip("/")


def escape_pkg_path(pkgpath: str) -> str:
    """Linker symbol form of a package path: dots in the last element become %2e."""
    pkgpath = normalize_import_path(pkgpath)
    head, sep, last = pkgpath.rpartition("/")
    return head + sep + last.replace(".", "%2e")


_GENERIC_FUNC = re.compile(r"(\w+)\[.*\]")


def symbol_patterns(package: str, symbol: str) -> list[str]:
    """Binary symbol names that mean `symbol` of `package` is in the binary.

    `Func` -> pkg.Func;  `T.M` / `*T.M` / `(*T).M` -> pkg.T.M and pkg.(*T).M.

    A bare generic function, e.g. `ParseAny[T]` -> a *prefix* pattern `pkg.ParseAny[`
    (CP3 task 0c). The compiler groups instantiations by "GC shape" (observed by
    building fixtures/reachability/cmd/generic_target with several instantiations:
    `string`, `int` and `[]byte` all produced a *different* binary symbol,
    `pkg.ParseAny[go.shape.<kind>]`, never the concrete type vulndb would name), so
    there is no reliable way to match one *specific* instantiation. There IS a
    reliable way to ask "is any instantiation of this generic function present":
    the bracket only ever starts right after the function's own name in this form
    (never after a dot), so the prefix is exact-namespaced to this package and name
    and cannot match a different, differently-named function (e.g. `pkg.Parse[`
    cannot match `pkg.ParseAny[...]`, since the character after `Parse` is `A`, not
    `[`). A generic *method*, or a method on a generic type, is different: the type
    argument is embedded inside the receiver's own brackets, e.g.
    `pkg.(*List[go.shape.string]).Push`, not after the method name, so no prefix or
    suffix rule covering that form was found here; it still raises
    UnsupportedSymbolForm.
    """
    pkg = escape_pkg_path(package)
    sym = symbol.strip()
    m = _GENERIC_FUNC.fullmatch(sym)
    if m:
        name = m.group(1)
        if not _IDENT.match(name):
            raise UnsupportedSymbolForm(f"unrecognised symbol form: {symbol!r}")
        return [f"{pkg}.{name}["]
    if "[" in symbol or "]" in symbol:
        raise UnsupportedSymbolForm(f"generic symbol form is not supported: {symbol!r}")
    m = re.fullmatch(r"\(\*(\w+)\)\.(\w+)", sym)
    if m:
        recv, meth = m.groups()
    else:
        parts = sym.lstrip("*").split(".")
        if len(parts) == 1:
            if not _IDENT.match(parts[0]):
                raise UnsupportedSymbolForm(f"unrecognised symbol form: {symbol!r}")
            return [f"{pkg}.{parts[0]}"]
        if len(parts) != 2 or not all(_IDENT.match(p) for p in parts):
            raise UnsupportedSymbolForm(f"unrecognised symbol form: {symbol!r}")
        recv, meth = parts
    return [f"{pkg}.{recv}.{meth}", f"{pkg}.(*{recv}).{meth}"]


def parse_nm(text: str) -> list[tuple[str, str]]:
    """Parse `go tool nm` output into (type_letter, name) pairs."""
    out = []
    for line in text.splitlines():
        m = _NM_LINE.match(line)
        if m:
            out.append((m.group(2), m.group(3)))
    return out


def match_symbols(nm_symbols: list[tuple[str, str]], patterns: list[str]) -> list[str]:
    """A pattern ending in `[` (from a bare generic function target) matches by prefix,
    i.e. any instantiation; every other pattern matches only exactly."""
    exact = {p for p in patterns if not p.endswith("[")}
    prefixes = tuple(p for p in patterns if p.endswith("["))
    return sorted({name for typ, name in nm_symbols
                  if typ in TEXT_SYMBOL_TYPES and (name in exact or name.startswith(prefixes))})


def binary_name(goos: str) -> str:
    return "vt_linker_bin.exe" if goos == "windows" else "vt_linker_bin"


def build_and_list(
    module_dir: Path, main_package: str, gcflags: list[str] | None, runner=subprocess.run
) -> tuple[str, str, dict[str, str]]:
    """Return (nm_text, go_version, {goos, goarch}). Raises LinkerError on failure."""
    env = go_env()
    flags = list(gcflags or [])
    ver = runner(["go", "version"], capture_output=True, text=True, env=env, cwd=module_dir)
    go_version = ver.stdout.split()[2] if ver.returncode == 0 and len(ver.stdout.split()) >= 3 else "unknown"
    genv = runner(["go", "env", "GOOS", "GOARCH"], capture_output=True, text=True, env=env, cwd=module_dir)
    goos, goarch = (genv.stdout.split() + ["unknown", "unknown"])[:2]
    with tempfile.TemporaryDirectory(prefix="vt_linker_") as tmp:
        binary = os.path.join(tmp, binary_name(goos))
        try:
            b = runner(
                ["go", "build", *flags, "-o", binary, normalize_import_path(main_package)],
                capture_output=True, text=True, env=env, cwd=module_dir,
            )
            if b.returncode != 0:
                raise LinkerError(E_BUILD, (b.stderr or b.stdout).strip()[:2000])
            nm = runner(["go", "tool", "nm", binary], capture_output=True, text=True, env=env, cwd=module_dir)
            if nm.returncode != 0:
                raise LinkerError(E_NM, (nm.stderr or nm.stdout).strip()[:2000])
            return nm.stdout, go_version, {"goos": goos, "goarch": goarch}
        finally:
            if os.path.exists(binary):
                os.remove(binary)


class LinkerError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def run_linker_method(
    module_dir: Path,
    main_package: str,
    targets: list[dict[str, str]],
    gcflags: list[str] | None = NO_INLINE_FLAGS,
    runner=subprocess.run,
) -> list[dict[str, Any]]:
    """One MethodResult per target. The package is built once."""
    started = time.monotonic()
    flags = list(gcflags or [])
    results: list[dict[str, Any]] = []

    def make(target, result, details, error):
        return {
            "schema_version": SCHEMA_VERSION,
            "method": METHOD,
            "target": {"package": target["package"], "symbol": target["symbol"]},
            "main_package": main_package,
            "result": result,
            "details": details,
            "error": error,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    patterns: dict[int, list[str]] = {}
    unsupported: dict[int, str] = {}
    for i, t in enumerate(targets):
        try:
            patterns[i] = symbol_patterns(t["package"], t["symbol"])
        except UnsupportedSymbolForm as exc:
            unsupported[i] = str(exc)

    nm_symbols: list[tuple[str, str]] = []
    info = {"go_version": "unknown", "goos": "unknown", "goarch": "unknown"}
    build_error: LinkerError | None = None
    if patterns:
        try:
            nm_text, go_version, plat = build_and_list(module_dir, main_package, flags, runner)
            nm_symbols = parse_nm(nm_text)
            info = {"go_version": go_version, **plat}
        except FileNotFoundError:
            build_error = LinkerError(E_NO_GO, "go executable not found")
        except LinkerError as exc:
            build_error = exc

    for i, t in enumerate(targets):
        details = {"matched_binary_symbols": [], "build_flags": flags, **info}
        if i in unsupported:
            results.append(make(t, "ERROR", details, {"code": E_UNSUPPORTED, "message": unsupported[i]}))
        elif build_error is not None:
            results.append(make(t, "ERROR", details, {"code": build_error.code, "message": build_error.message}))
        else:
            matched = match_symbols(nm_symbols, patterns[i])
            details["matched_binary_symbols"] = matched
            results.append(make(t, "PRESENT" if matched else "ABSENT", details, None))
    return results
