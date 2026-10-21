"""Baselines E0 (D1) and B-ID (D4) - CP3 deliverable 6, docs/evaluation/EVALUATION_PLAN.md.

Gold symbols are matched by name only, not full package path: feasibility trial 2 found
that a strict package-path matcher undercounted because of /v2, /v3 module suffixes, and
reported its numbers with name-level matching instead - this project follows that same,
already-validated convention rather than reopening the question.
"""

from typing import Any

STRATEGY_E0 = "BASELINE_E0"
STRATEGY_ID_SEARCH = "BASELINE_ID_SEARCH"


def core_symbols(case: dict[str, Any]) -> set[str]:
    return {sym for m in case["modules"] for pkg in m["packages"] for sym in pkg["core_symbols"]}


def core_and_derived_symbols(case: dict[str, Any]) -> set[str]:
    derived = {sym for m in case["modules"] for pkg in m["packages"] for sym in pkg["derived_symbols"]}
    return core_symbols(case) | derived


def e0_predict(fix_ev: dict[str, Any]) -> set[str]:
    """E0: every function the fix commit changed is predicted vulnerable."""
    return {c["symbol"] for c in fix_ev["candidates"]}


def advisory_identifiers(case: dict[str, Any]) -> set[str]:
    """The case's own id plus every alias (CVE/GHSA), upper-cased for a case-insensitive
    search."""
    return {i.upper() for i in {case["id"], *case["aliases"]}}


def bid_predict(case: dict[str, Any], rr: dict[str, Any]) -> set[str]:
    """B-ID: search each commit in the release range (subject and body) for one of the
    advisory's own identifiers; predict every candidate symbol a matching commit touches.
    No commit matches -> predict nothing (an abstention, not a guess)."""
    ids = advisory_identifiers(case)
    symbol_by_id = {c["candidate_id"]: c["symbol"] for c in rr["candidates"]}
    matched: set[str] = set()
    for commit in rr["commits"]:
        text = f"{commit['subject']}\n{commit['body']}".upper()
        if any(ident in text for ident in ids):
            matched.update(commit["touches_candidates"])
    return {symbol_by_id[cid] for cid in matched if cid in symbol_by_id}
