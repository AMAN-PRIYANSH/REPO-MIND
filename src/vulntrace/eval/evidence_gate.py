"""Refuse to run on empty or wrong evidence (CP4 FIX-5).

The first Colab run rebuilt the D4 evidence on a broken git setup (0 of 103 expected AVAILABLE
cases), carried on, and wrote results in which every case had 0 candidates. This module is the
one place that decides whether the materialised evidence may be used. `check_evidence` is pure;
`evidence_statuses` reads the statuses from a data directory. The notebook's gate cell, `eval
retrieval` and `index build` all go through it.
"""

import json
from pathlib import Path
from typing import Any

# A handful of cases may legitimately differ from the committed list (the Claude Code session
# saw 1 of 120); the broken Colab run differed in 119.
MAX_STATUS_DIFFERENCES = 3

MISSING = "MISSING"


class EvidenceGateError(Exception):
    pass


def evidence_statuses(case_list: dict[str, Any], data_dir: Path,
                      subdir: str = "release_range") -> tuple[dict[str, str], int]:
    """({case_id: stored status or "MISSING"}, total candidate count) for every case in the list.
    `subdir` is `release_range` for D4 and `fix_evidence` for D1."""
    statuses: dict[str, str] = {}
    candidates = 0
    for entry in case_list["cases"]:
        path = Path(data_dir) / subdir / f"{entry['id']}.json"
        try:
            rr = json.loads(path.read_text(encoding="utf-8"))
            statuses[entry["id"]] = rr["status"]
            candidates += len(rr["candidates"])
        except (OSError, ValueError, KeyError):
            statuses[entry["id"]] = MISSING
    return statuses, candidates


def check_evidence(case_list: dict[str, Any], actual: dict[str, str], total_chunks: int,
                   max_differences: int = MAX_STATUS_DIFFERENCES) -> list[str]:
    """Problems that must stop a run; an empty list means the evidence may be used.
    `actual` maps case id -> status found; `total_chunks` is the chunk (or candidate) count
    over all cases."""
    problems = []
    if total_chunks <= 0:
        problems.append("the evidence holds 0 chunks (0 candidate functions in any case)")
    differing = [(e["id"], e["status"], actual.get(e["id"], MISSING)) for e in case_list["cases"]
                 if actual.get(e["id"], MISSING) != e["status"]]
    if len(differing) > max_differences:
        shown = ", ".join(f"{i} {a}->{b}" for i, a, b in differing[:5])
        problems.append(f"{len(differing)} of {len(case_list['cases'])} cases have a status different from the "
                        f"case list (allowed: {max_differences}); e.g. {shown}")
    return problems


def require_valid_evidence(case_list: dict[str, Any], actual: dict[str, str], total_chunks: int,
                           max_differences: int = MAX_STATUS_DIFFERENCES) -> None:
    problems = check_evidence(case_list, actual, total_chunks, max_differences)
    if problems:
        raise EvidenceGateError("refusing to run on invalid evidence: " + "; ".join(problems)
                                + ". Re-run `python -m vulntrace dataset materialize --set d4` and read its "
                                  "top git errors.")
