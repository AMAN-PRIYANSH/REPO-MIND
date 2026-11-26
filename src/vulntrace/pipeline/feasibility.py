"""CP9: the path-feasibility filter stage (downgrade-only).

The Go helper's `reach` mode, asked with a `feasibility` object, annotates every PATH_FOUND target
with the filter's answer (helper/feasible.go): FEASIBLE (with the path that passed, the evidence),
INFEASIBLE (every path has a step that cannot run, for pattern F1, F2 or F3; each examined path's
first such step is listed) or UNDECIDED (a work cap was hit). This stage runs after the rule table
(`verdict.symbol_verdict`, unchanged) and before the verifier, and changes exactly one thing:
an entry the rule table made REACHABLE whose filter answer is INFEASIBLE becomes CANT_DETERMINE
with reason PATHS_INFEASIBLE. It never makes NOT_REACHABLE (the checks are incomplete) and never
makes anything stronger; `assert_filter_downgrade_only` proves it on every verdict.
"""

import copy
from collections import Counter
from typing import Any

from vulntrace.pipeline import aggregate
from vulntrace.verdict import CANT_DETERMINE, PATHS_INFEASIBLE, REACHABLE

FEASIBLE, INFEASIBLE, UNDECIDED = "FEASIBLE", "INFEASIBLE", "UNDECIDED"
DEFAULT_MAX_EXAMINED_PATHS = 20
PATTERNS = ("F1", "F2", "F3")


def helper_settings(max_examined_paths: int = DEFAULT_MAX_EXAMINED_PATHS,
                    rank_evidence: bool = False) -> dict[str, Any]:
    """The helper request's `feasibility` object (the other limits keep the helper's defaults).
    `rank_evidence` (CP10): also rank the examined paths (`pipeline.evidence`); False is the CP9 request."""
    if max_examined_paths < 1:
        raise ValueError("max_examined_paths must be at least 1")
    out: dict[str, Any] = {"max_examined_paths": int(max_examined_paths)}
    if rank_evidence:
        out["rank_evidence"] = True
    return out


def apply_filter(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """(new entries, number downgraded). Input entries are not modified."""
    out, downgraded = [], 0
    for e in entries:
        e = copy.deepcopy(e)
        f = e.get("feasibility")
        if e["result"] == REACHABLE and f is not None:
            e["pre_feasibility_result"] = REACHABLE
            if f.get("status") == INFEASIBLE:
                e["result"], e["reason_code"] = CANT_DETERMINE, PATHS_INFEASIBLE
                e["pre_verifier_result"] = CANT_DETERMINE  # what the verifier receives
                downgraded += 1
        out.append(e)
    return out, downgraded


def status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Filter answers of the entries the rule table made REACHABLE."""
    return dict(Counter((e.get("feasibility") or {}).get("status", "NOT_RUN") for e in entries
                        if e.get("pre_feasibility_result") == REACHABLE))


def first_patterns(entry: dict[str, Any]) -> list[str]:
    """Pattern of the first infeasible step of each examined path, in path order."""
    return [ex["first_infeasible"]["pattern"] for ex in (entry.get("feasibility") or {}).get("examined") or []
            if ex.get("first_infeasible")]


def deciding_pattern(entry: dict[str, Any]) -> str | None:
    """The pattern of the shortest examined path's first infeasible step (None if none)."""
    p = first_patterns(entry)
    return p[0] if p else None


def assert_filter_downgrade_only(before: list[dict[str, Any]], after: list[dict[str, Any]],
                                 verdict_before: str, verdict_after: str) -> None:
    """The filter's own guard (the verifier's guard runs later on the filtered verdict)."""
    aggregate.assert_downgrade_only({"per_symbol": before, "verdict": verdict_before},
                                    {"per_symbol": after, "verdict": verdict_after})
    for b, a in zip(before, after):
        if a["result"] != b["result"] and not (b["result"] == REACHABLE and a["result"] == CANT_DETERMINE
                                               and a["reason_code"] == PATHS_INFEASIBLE):
            raise aggregate.DowngradeViolation(f"filter changed {b['result']} -> {a['result']}")
        if a["result"] == CANT_DETERMINE and a["reason_code"] == PATHS_INFEASIBLE and \
                (a.get("feasibility") or {}).get("status") != INFEASIBLE:
            raise aggregate.DowngradeViolation("PATHS_INFEASIBLE without an INFEASIBLE filter answer")
