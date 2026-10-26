"""Case-level aggregation, the Mode 2 policy and the downgrade-only guard (pure functions).

Per entry (one target symbol analysed from one main package) the result comes from the rule
table in `vulntrace.verdict`. The case is REACHABLE if any deciding entry is; NOT_REACHABLE only
if every deciding entry is and coverage is complete; otherwise CANT_DETERMINE with the entries'
reason codes. LIFTED symbols are reported but never decide (CP5b finding).
"""

from typing import Any

from vulntrace.verdict import (CANT_DETERMINE, INCOMPLETE_COVERAGE, MODE2_NOT_REACHABLE_DOWNGRADED,
                               NO_TARGET_SYMBOLS, NOT_REACHABLE, REACHABLE)

MODE2_POLICY_NAME = "MODE2_NOT_REACHABLE_POLICY"
MODE2_POLICY_DOWNGRADE = "DOWNGRADE"
MODE2_POLICY_KEEP = "KEEP"
MODE2_POLICY_RULE = ("Mode 2 checks only the retriever's top-k candidates, and the candidate list misses the root "
                     "cause in a measured share of cases, so a Mode 2 NOT_REACHABLE only says that none of the "
                     "analysed candidates is reachable. It is reported as CANT_DETERMINE with "
                     "MODE2_NOT_REACHABLE_DOWNGRADED; the raw verdict is kept in pre_policy_verdict.")


def case_result(entries: list[dict[str, Any]], blocking: list[str] | tuple[str, ...] = (),
                incomplete: bool = False) -> tuple[str, list[str]]:
    """(verdict, reason codes). `blocking` codes mean nothing could be analysed (no evidence, no
    main package, ...): the case is CANT_DETERMINE with exactly those codes. `incomplete` means some
    part of the app was not analysed (for example main packages over the limit), so the case can
    be REACHABLE but never NOT_REACHABLE."""
    if blocking:
        return CANT_DETERMINE, sorted(set(blocking))
    deciding = [e for e in entries if e.get("decides_verdict", True)]
    if not deciding:
        return CANT_DETERMINE, [NO_TARGET_SYMBOLS]
    results = [e["result"] for e in deciding]
    if REACHABLE in results:
        return REACHABLE, []
    if all(r == NOT_REACHABLE for r in results):
        return (CANT_DETERMINE, [INCOMPLETE_COVERAGE]) if incomplete else (NOT_REACHABLE, [])
    codes = {e["reason_code"] for e in deciding if e["result"] == CANT_DETERMINE and e["reason_code"]}
    if incomplete:
        codes.add(INCOMPLETE_COVERAGE)
    return CANT_DETERMINE, sorted(codes)


def apply_mode2_policy(verdict: str, reasons: list[str], policy: str = MODE2_POLICY_DOWNGRADE) -> tuple[str, list[str], bool]:
    """(verdict, reasons, applied). Only a Mode 2 NOT_REACHABLE is touched, and only downwards."""
    if policy == MODE2_POLICY_DOWNGRADE and verdict == NOT_REACHABLE:
        return CANT_DETERMINE, [MODE2_NOT_REACHABLE_DOWNGRADED], True
    if policy not in (MODE2_POLICY_DOWNGRADE, MODE2_POLICY_KEEP):
        raise ValueError(f"unknown Mode 2 policy {policy!r}")
    return verdict, list(reasons), False


def not_stronger(before: str, after: str) -> bool:
    """A later stage may keep a result or weaken it to CANT_DETERMINE; nothing else."""
    return after == before or after == CANT_DETERMINE


class DowngradeViolation(AssertionError):
    pass


def _entry_key(e: dict[str, Any]) -> tuple:
    return (e["target"]["package"], e["target"]["symbol"], e.get("main_package"))


def assert_downgrade_only(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Raise DowngradeViolation unless `after` is `before` with results only weakened: the same
    entries in the same order, the same method results and paths, no entry or case result
    stronger, and a verified path only where the method returned that exact path."""
    b_entries, a_entries = before["per_symbol"], after["per_symbol"]
    if [_entry_key(e) for e in b_entries] != [_entry_key(e) for e in a_entries]:
        raise DowngradeViolation("entries were added, removed or reordered")
    for b, a in zip(b_entries, a_entries):
        if a["methods"] != b["methods"]:
            raise DowngradeViolation(f"method results changed for {_entry_key(b)}")
        if a.get("paths") != b.get("paths"):
            raise DowngradeViolation(f"paths changed for {_entry_key(b)}")
        if a.get("decides_verdict", True) != b.get("decides_verdict", True):
            raise DowngradeViolation(f"decides_verdict changed for {_entry_key(b)}")
        if not not_stronger(b["result"], a["result"]):
            raise DowngradeViolation(f"{_entry_key(b)}: {b['result']} -> {a['result']}")
        vp = a.get("verified_path")
        if vp is not None and (a["result"] != REACHABLE or vp not in (b.get("paths") or [])):
            raise DowngradeViolation(f"{_entry_key(b)}: verified path is not one of the method's paths")
    if not not_stronger(before["verdict"], after["verdict"]):
        raise DowngradeViolation(f"case verdict {before['verdict']} -> {after['verdict']}")
