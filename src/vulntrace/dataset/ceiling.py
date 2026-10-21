"""Ceiling investigation (CP3 deliverable 7, open question Q8): for a D4 case where a core
symbol is not among the release range's candidates, classify why.

Feasibility trial 5 found 10/42 sampled cases had at least one core symbol outside the
release diff and left the reason open; this is that investigation. Classification is by a
cheap `git grep` existence check (not a full parse of every file in the tree, which would
be the accurate but expensive way to check "does this symbol exist, unchanged, anywhere"),
so it is a reasonable, documented approximation suited to an exploratory question, not a
validated, precise classifier.
"""

import subprocess
from pathlib import Path
from typing import Any

from vulntrace.dataset import git_fetch

REASON_EXISTS_UNCHANGED = "EXISTS_UNCHANGED"
REASON_NOT_FOUND_EITHER_VERSION = "NOT_FOUND_EITHER_VERSION"
REASON_MATCHING_PROBLEM = "MATCHING_PROBLEM"
REASON_OTHER = "OTHER"


def _grep_symbol_name(repo_dir: Path, ref: str, name: str, runner=subprocess.run) -> bool | None:
    """Whether `name` (the bare func/method name, no receiver) appears in any .go file at
    `ref`. None if `git grep` itself failed, including timing out (ambiguous, not "not
    found")."""
    p = git_fetch.run_git(runner, ["git", "grep", "-q", "-w", "-I", "--", name, ref, "--", "*.go"], repo_dir,
                         timeout=60)
    if p.returncode == 0:
        return True
    if p.returncode == 1:
        return False
    return None


def classify_missing_symbol(repo_dir: Path, from_sha: str, to_sha: str, symbol: str,
                            runner=subprocess.run) -> str:
    """One of the four reasons CP3 deliverable 7 asks for, for one symbol missing from a
    case's candidates."""
    name = symbol.rsplit(".", 1)[-1]
    in_old = _grep_symbol_name(repo_dir, from_sha, name, runner)
    in_new = _grep_symbol_name(repo_dir, to_sha, name, runner)
    if in_old is None or in_new is None:
        return REASON_OTHER
    if in_old and in_new:
        return REASON_EXISTS_UNCHANGED
    if not in_old and not in_new:
        return REASON_NOT_FOUND_EITHER_VERSION
    return REASON_MATCHING_PROBLEM  # present at exactly one end but missing from candidates


def missing_core_symbols(case: dict[str, Any], rr: dict[str, Any]) -> set[str]:
    from vulntrace.dataset.baselines import core_symbols

    candidate_symbols = {c["symbol"] for c in rr["candidates"]}
    return core_symbols(case) - candidate_symbols


def investigate_case(case: dict[str, Any], rr: dict[str, Any], repo_dir: Path, runner=subprocess.run) -> dict[str, Any]:
    """{symbol: reason} for every core symbol of `case` missing from `rr`'s candidates."""
    missing = missing_core_symbols(case, rr)
    if not missing:
        return {}
    from_sha, to_sha = rr["from"]["commit"], rr["to"]["commit"]
    if from_sha is None or to_sha is None:
        return {s: REASON_OTHER for s in missing}
    return {s: classify_missing_symbol(repo_dir, from_sha, to_sha, s, runner) for s in sorted(missing)}


def run_investigation(cases_by_id: dict[str, dict[str, Any]], release_ranges_by_id: dict[str, dict[str, Any]],
                      cache_root: Path | None = None, runner=subprocess.run,
                      max_examples: int = 3) -> dict[str, Any]:
    """Across every D4 case with a resolved release range, classify why each missing core
    symbol is missing (open question Q8). Returns counts per reason plus up to
    `max_examples` worked examples (case id, symbol, reason)."""
    counts = {REASON_EXISTS_UNCHANGED: 0, REASON_NOT_FOUND_EITHER_VERSION: 0, REASON_MATCHING_PROBLEM: 0,
             REASON_OTHER: 0}
    examples: list[dict[str, str]] = []
    cases_with_missing = 0
    cases_checked = 0
    for case_id, rr in release_ranges_by_id.items():
        case = cases_by_id.get(case_id)
        if case is None or rr["from"]["commit"] is None or rr["to"]["commit"] is None:
            continue
        cases_checked += 1
        missing = missing_core_symbols(case, rr)
        if not missing:
            continue
        cases_with_missing += 1
        fc = case["fix_commits"][0]
        repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], cache_root)
        reasons = investigate_case(case, rr, repo_dir, runner)
        for symbol, reason in reasons.items():
            counts[reason] += 1
            if len(examples) < max_examples:
                examples.append({"case_id": case_id, "symbol": symbol, "reason": reason})
    return {
        "cases_checked": cases_checked, "cases_with_missing_core_symbol": cases_with_missing,
        "missing_symbol_counts_by_reason": counts, "examples": examples,
    }
