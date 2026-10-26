"""Target symbols by mode (pure functions).

Mode 1 (FIX): every changed non-test function of the fix commit(s) - the E0 behaviour, which CP5
measured as the best recall (0.84; an LLM pick fell to 0.57). No selection, no LLM.
Mode 2 (RELEASE): the retriever's top-k candidates of the release range, with rank and score.

A function the fix (or the range) only *added* (side NEW) did not exist in the vulnerable
version, so it cannot be the vulnerable code there; it is not analysed and is listed as not
covered (`ADDED_BY_FIX`). A candidate outside the advisory's module directory is listed as not
covered (`OUTSIDE_MODULE`). Nothing is dropped silently.

CP3's FixEvidence attributes a diff hunk to every function its span overlaps, and the span
includes git's 3 context lines, so a function next to the edit can be a candidate although none
of its lines changed. Mode 1 keeps the candidates exactly as E0 measured them, and flags such a
symbol `context_only` (computed here from the hunk text) so its effect can be counted.
"""

import posixpath
from typing import Any

from vulntrace.dataset.release_range import module_subdir

FIX_CHANGED, RANKED_CANDIDATE, LIFTED, FIXTURE, USER = "FIX_CHANGED", "RANKED_CANDIDATE", "LIFTED", "FIXTURE", "USER"
NC_ADDED_BY_FIX, NC_OUTSIDE_MODULE, NC_BEYOND_TOP_K = "ADDED_BY_FIX", "OUTSIDE_MODULE", "BEYOND_TOP_K"


def module_rel_for(module: str, fix_commit: dict[str, str] | None) -> str:
    """The advisory module's directory inside the fix repository (CP3's best-effort rule: a module
    path that is not under github.com/<owner>/<repo> is assumed to be the repository root)."""
    if not fix_commit:
        return ""
    return module_subdir(module, fix_commit["owner"], fix_commit["repo"])


def import_path_for(module: str, module_rel: str, package_dir: str) -> str | None:
    """Import path of a repository-relative package directory in the module rooted at
    `module_rel`; None if the directory is outside the module."""
    rel = posixpath.relpath(package_dir or ".", module_rel or ".")
    if rel == ".":
        return module
    if rel.startswith(".."):
        return None
    return module + "/" + rel


def _symbol(c: dict[str, Any], module: str, module_rel: str, origin: str, rank: int | None = None,
            score: float | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(target symbol, None) or (None, not-covered record)."""
    base = {"symbol": c["symbol"], "candidate_id": c["candidate_id"], "side": c["side"], "rank": rank}
    if c["side"] == "NEW":
        return None, {**base, "package_dir": c["package_dir"], "reason": NC_ADDED_BY_FIX}
    pkg = import_path_for(module, module_rel, c["package_dir"])
    if pkg is None:
        return None, {**base, "package_dir": c["package_dir"], "reason": NC_OUTSIDE_MODULE}
    return {"package": pkg, "symbol": c["symbol"], "origin": origin, "rank": rank, "score": score,
            "candidate_id": c["candidate_id"], "side": c["side"], "decides_verdict": True}, None


def dedupe(symbols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """First occurrence wins (the best rank in Mode 2; candidate order in Mode 1)."""
    seen, out = set(), []
    for s in symbols:
        k = (s["package"], s["symbol"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def changed_lines(hunk: dict[str, Any]) -> tuple[set[int], set[int]]:
    """(old-side line numbers removed, new-side line numbers added) of one unified-diff hunk."""
    old_ln, new_ln = hunk["old_start"], hunk["new_start"]
    removed, added = set(), set()
    for line in (hunk.get("text") or "").split("\n"):
        if line.startswith("\\"):
            continue  # "\ No newline at end of file"
        if line.startswith("-"):
            removed.add(old_ln)
            old_ln += 1
        elif line.startswith("+"):
            added.add(new_ln)
            new_ln += 1
        else:
            old_ln += 1
            new_ln += 1
    return removed, added


def context_only(candidate: dict[str, Any], hunks_by_id: dict[str, dict[str, Any]]) -> bool | None:
    """True if no removed or added line of the candidate's hunks lies inside its own range (it is a
    candidate only because of diff context); None if its hunks are not available."""
    hunks = [hunks_by_id.get(h) for h in candidate.get("hunk_ids") or []]
    if not hunks or any(h is None for h in hunks):
        return None
    o, n = candidate.get("old_range"), candidate.get("new_range")
    for h in hunks:
        removed, added = changed_lines(h)
        if o and any(o["start"] <= ln <= o["end"] for ln in removed):
            return False
        if n and any(n["start"] <= ln <= n["end"] for ln in added):
            return False
    return True


def mode1_symbols(fix_evidence: dict[str, Any], module: str, module_rel: str) -> tuple[list[dict], list[dict]]:
    """(targets, not covered): every changed non-test function of the fix (test files are already
    excluded from FixEvidence candidates)."""
    targets, not_covered = [], []
    hunks_by_id = {h["hunk_id"]: h for h in fix_evidence.get("hunks") or []}
    for c in fix_evidence["candidates"]:
        t, nc = _symbol(c, module, module_rel, FIX_CHANGED)
        if t:
            t["context_only"] = context_only(c, hunks_by_id)
            targets.append(t)
        else:
            not_covered.append(nc)
    return dedupe(targets), not_covered


def mode2_symbols(release_range: dict[str, Any], ranked: list[tuple[str, float | None]], k: int, module: str,
                  module_rel: str) -> tuple[list[dict], list[dict]]:
    """(targets, not covered) from the ranked candidate ids (best first) and their scores. Only the
    top k are analysed; the rest are counted as not covered (`BEYOND_TOP_K`)."""
    by_id = {c["candidate_id"]: c for c in release_range["candidates"]}
    targets, not_covered = [], []
    for rank, (cid, score) in enumerate(ranked, start=1):
        c = by_id[cid]
        if rank > k:
            not_covered.append({"symbol": c["symbol"], "candidate_id": cid, "side": c["side"], "rank": rank,
                                "package_dir": c["package_dir"], "reason": NC_BEYOND_TOP_K})
            continue
        t, nc = _symbol(c, module, module_rel, RANKED_CANDIDATE, rank=rank, score=score)
        if t:
            targets.append(t)
        else:
            not_covered.append(nc)
    return dedupe(targets), not_covered


def given_symbols(targets: list[dict[str, str]], origin: str) -> list[dict[str, Any]]:
    """Symbols given directly (fixtures, curated reference runs, a user's own list)."""
    return dedupe([{"package": t["package"], "symbol": t["symbol"], "origin": origin, "rank": None, "score": None,
                    "candidate_id": None, "side": None, "decides_verdict": True} for t in targets])
