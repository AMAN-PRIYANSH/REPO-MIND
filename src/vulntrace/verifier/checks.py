"""Pure checks of the verifier: call-path structure, call-site placement and symbol forms.

Names in a CallPath edge are "<package path>.<symbol>" as the Go helper prints them (CP2): a
closure keeps SSA's "$n" suffix ("main$1"), a user-written init function is "init#n", the
package initializer is "init", generic instances keep their type arguments ("F[string]"), and
synthetic forwarders end in "$bound", "$thunk", "$wrapper" or "$instwrapper".
"""

import re
from dataclasses import dataclass
from typing import Any

TARGET_EXISTS = "TARGET_EXISTS"
CALL_SITE = "CALL_SITE"
EDGE_EXISTS = "EDGE_EXISTS"
PATH_STRUCTURE = "PATH_STRUCTURE"
REACHABLE_HAS_PATH = "REACHABLE_HAS_PATH"
VERIFIER_ERROR = "VERIFIER_ERROR"
CHECK_KINDS = (TARGET_EXISTS, CALL_SITE, EDGE_EXISTS, PATH_STRUCTURE, REACHABLE_HAS_PATH, VERIFIER_ERROR)

ENTRY_SYMBOLS = ("main", "init")
FORWARDER_SUFFIXES = ("$bound", "$thunk", "$wrapper", "$instwrapper")
_INIT_N = re.compile(r"\.init#\d+$")


@dataclass(frozen=True)
class Failure:
    check: str
    reason: str
    path_index: int | None = None
    edge_index: int | None = None

    def to_json(self, target: dict[str, str] | None = None, main: str | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {"check": self.check, "reason": self.reason, "path_index": self.path_index,
                             "edge_index": self.edge_index}
        if target is not None:
            d["target"] = {"package": target["package"], "symbol": target["symbol"]}
        if main is not None:
            d["main_package"] = main
        return d


def strip_type_args(name: str) -> str:
    """Remove every balanced [...] group (type arguments or parameters)."""
    out, depth = [], 0
    for ch in name:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def normalise_symbol(symbol: str) -> str:
    """vulndb form: `F`, `T.M` (no pointer, no type parameters); `(*T).M` and `*T.M` become `T.M`."""
    s = strip_type_args(symbol.strip())
    m = re.fullmatch(r"\(\*(\w+)\)\.(\w+)", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}"
    return s.lstrip("*")


def target_full_name(target: dict[str, str]) -> str:
    return f"{target['package']}.{normalise_symbol(target['symbol'])}"


def declared_name(node: str) -> str:
    """The source declaration a call-graph node belongs to: forwarder suffixes, closure suffixes
    ("$1", "$1$2"), init numbering ("#1") and type arguments are removed."""
    n = strip_type_args(node)
    for suf in FORWARDER_SUFFIXES:
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    if "$" in n:
        n = n[: n.index("$")]
    n = re.sub(r"#\d+$", "", n)
    return n


def is_synthetic_edge(caller: str, callee: str) -> bool:
    """Edges Go creates with no source position: a forwarder calling the method it wraps, and the
    package initializer calling another package's initializer or its own `init` functions. A
    wrapper for a method promoted through an embedded field calls the embedded type's method,
    which can be in another package (`p.Outer.M$wrapper -> q.Inner.M`, seen in quic-go and
    antlr4-go on D1), so a forwarder only has to call a method of the same name; the `edges`
    check still has to confirm the edge in the call graph."""
    c, e = strip_type_args(caller), strip_type_args(callee)
    for suf in FORWARDER_SUFFIXES:
        if c.endswith(suf):
            return "." in c and c[: -len(suf)].rsplit(".", 1)[-1] == e.rsplit(".", 1)[-1]
    if c.endswith(".init") and (e.endswith(".init") or _INIT_N.search(e)):
        return True
    return False


def check_structure(path: dict[str, Any], main_package: str, target: dict[str, str]) -> list[Failure]:
    """The path starts at `main` or `init` of the analysed main package, its edges chain, and it
    ends at the target symbol."""
    out: list[Failure] = []
    entry = path.get("entry") or {}
    edges = path.get("edges") or []
    if entry.get("package") != main_package or entry.get("symbol") not in ENTRY_SYMBOLS:
        out.append(Failure(PATH_STRUCTURE, f"entry {entry.get('package')}.{entry.get('symbol')} is not main or init "
                                           f"of {main_package}"))
    p_target = path.get("target") or {}
    if (p_target.get("package"), p_target.get("symbol")) != (target["package"], target["symbol"]):
        out.append(Failure(PATH_STRUCTURE, "path target differs from the entry's target"))
    entry_name = f"{entry.get('package')}.{entry.get('symbol')}"
    want_end = target_full_name(target)
    if not edges:
        if strip_type_args(entry_name) != want_end:
            out.append(Failure(PATH_STRUCTURE, "path has no edges and its entry is not the target"))
        return out
    if edges[0].get("caller") != entry_name:
        out.append(Failure(PATH_STRUCTURE, f"first caller {edges[0].get('caller')} is not the entry {entry_name}", edge_index=0))
    for i in range(1, len(edges)):
        if edges[i].get("caller") != edges[i - 1].get("callee"):
            out.append(Failure(PATH_STRUCTURE, f"edge {i} caller {edges[i].get('caller')} does not continue from "
                                               f"{edges[i - 1].get('callee')}", edge_index=i))
    if strip_type_args(edges[-1].get("callee", "")) != want_end:
        out.append(Failure(PATH_STRUCTURE, f"last callee {edges[-1].get('callee')} is not the target {want_end}",
                           edge_index=len(edges) - 1))
    return out


def check_site(edge: dict[str, Any], edge_index: int, line_count: int | None,
               decls: list[dict[str, Any]] | None) -> Failure | None:
    """One edge's call site. `line_count` and `decls` (funcs output: symbol, start, end) describe
    the call-site file as read at the recorded commit; None means the file could not be read.
    A site without a file and line is accepted only for a synthetic edge (`is_synthetic_edge`)."""
    site = edge.get("call_site") or {}
    file, line = site.get("file") or "", site.get("line") or 0
    caller, callee = edge.get("caller", ""), edge.get("callee", "")
    if not file and line == 0:
        if is_synthetic_edge(caller, callee):
            return None
        return Failure(CALL_SITE, f"edge {caller} -> {callee} has no call site and is not a synthetic edge",
                       edge_index=edge_index)
    if not file or line < 1:
        return Failure(CALL_SITE, f"incomplete call site {file}:{line}", edge_index=edge_index)
    if line_count is None or decls is None:
        return Failure(CALL_SITE, f"call-site file {file} cannot be read at the recorded version", edge_index=edge_index)
    if line > line_count:
        return Failure(CALL_SITE, f"{file} has {line_count} lines; call site line {line} does not exist",
                       edge_index=edge_index)
    want = declared_name(caller)
    containing = [d for d in decls if d["start"] <= line <= d["end"]]
    if any(want.endswith("." + d["symbol"]) for d in containing):
        return None
    if want.endswith(".init") and not containing:
        return None  # a package-level variable initializer: code of the package initializer outside any function
    where = ", ".join(d["symbol"] for d in containing) or "no function"
    return Failure(CALL_SITE, f"{file}:{line} lies in {where}, not in the caller {caller}", edge_index=edge_index)


def declares(decls: list[dict[str, Any]], symbol: str) -> bool:
    """Whether funcs output declares the target symbol (vulndb form)."""
    want = normalise_symbol(symbol)
    return any(d["symbol"] == want for d in decls)
