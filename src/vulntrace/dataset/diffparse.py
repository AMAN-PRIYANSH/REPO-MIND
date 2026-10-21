"""Unified diff hunk parsing (CP3 deliverables 3 and 4). Pure Python, no git: parses the
text `git diff` prints for one file."""

import re

_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_hunks(diff_text: str) -> list[dict]:
    """One dict per hunk: old_start, old_lines, new_start, new_lines (ints; `lines` defaults
    to 1 when the header omits it, per the unified diff format), and `text` (the hunk body -
    context/added/removed lines - not including the "@@ ... @@" header line itself)."""
    hunks: list[dict] = []
    body: list[str] = []
    for line in diff_text.splitlines():
        m = _HUNK_HEADER.match(line)
        if m:
            if hunks:
                hunks[-1]["text"] = "\n".join(body)
            old_start, old_lines, new_start, new_lines = m.groups()
            hunks.append({
                "old_start": int(old_start), "old_lines": int(old_lines) if old_lines is not None else 1,
                "new_start": int(new_start), "new_lines": int(new_lines) if new_lines is not None else 1,
            })
            body = []
        elif hunks:
            body.append(line)
    if hunks:
        hunks[-1]["text"] = "\n".join(body)
    return hunks


def old_range(hunk: dict) -> tuple[int, int] | None:
    """(first, last) 1-based inclusive old-side line numbers touched by `hunk`, or None for
    a pure insertion (old_lines == 0: nothing on the old side was touched)."""
    if hunk["old_lines"] == 0:
        return None
    return hunk["old_start"], hunk["old_start"] + hunk["old_lines"] - 1


def new_range(hunk: dict) -> tuple[int, int] | None:
    """As `old_range`, for the new side (None for a pure deletion)."""
    if hunk["new_lines"] == 0:
        return None
    return hunk["new_start"], hunk["new_start"] + hunk["new_lines"] - 1


def overlaps_function(touched: tuple[int, int] | None, insertion_point: int, func_start: int, func_end: int) -> bool:
    """Whether a hunk's effect on one side touches a function spanning [func_start, func_end].

    `touched` is `old_range`/`new_range` for that side; when it is None (a pure
    insertion/deletion on this side), the hunk still has an effective position -
    `insertion_point` (the line immediately before which text was inserted, or immediately
    after which it was removed) - and counts as touching the function whose range contains
    or immediately follows that point, since that is where the inserted/removed text lives
    in the function's body.
    """
    if touched is not None:
        start, end = touched
        return start <= func_end and end >= func_start
    return func_start <= insertion_point <= func_end + 1
