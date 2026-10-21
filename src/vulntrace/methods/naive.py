"""Naive name-only call graph (R1 negative control) through the helper's `naive` mode.

It is deliberately unsafe: calls through function values, method values and reflection
produce no edge. It exists to show why name-only graphs must not decide NOT_REACHABLE.
"""

from pathlib import Path
from typing import Any

from vulntrace.methods.callgraph import run_callgraph

METHOD = "CALLGRAPH_NAIVE"


def run_naive_method(module_dir: Path, main_package: str, targets: list[dict[str, str]], **kwargs) -> list[dict[str, Any]]:
    """One CALLGRAPH_NAIVE MethodResult per target."""
    return run_callgraph(module_dir, main_package, targets, mode="naive", method=METHOD, **kwargs)
