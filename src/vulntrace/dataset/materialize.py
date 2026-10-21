"""Re-materialise D4 release-range evidence from the committed case list (CP4 task 0a).

CP3 committed only the D4 case list (`docs/results/datasets/D4_cases.json`); the bulky
per-case evidence lived in a gitignored `data/` directory on an earlier session's machine.
This rebuilds it for exactly the committed 120 IDs - it never re-selects cases - from the
pinned vulndb commit:

- `data/release_range/<id>.json`: the ReleaseRange, as `dataset build --mode release` wrote it
  (same code path, so the CP3 baselines and ceiling investigation read it unchanged);
- `data/candidate_code/<id>.json`: per candidate, the Go package name, doc comment, signature
  and body text the CP4 chunker needs (vulnerable-side body; fixed-side only for functions
  that exist only in the fixed version).

Resumable (a case whose two files are both complete is skipped), sequential, with a small
delay between cases that touch the network. Cases that share an identical range (same module,
versions and repository: e.g. nine rclone advisories) are computed once and copied. Every case
whose status or counts differ from the committed case list is reported, never hidden.
"""

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from vulntrace.dataset import datasets, git_fetch, release_range
from vulntrace.dataset.build import DATA_DIR

CODE_SCHEMA_VERSION = "1.0"
DEFAULT_DELAY_S = 1.0
MAX_SIGNATURE_CHARS = 400

_PACKAGE_RE = re.compile(r"^package\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def range_key_for(case: dict[str, Any]) -> str | None:
    """`module@vulnerable_at..fixed_in` of the module D4 uses for this case (CP3's
    `pick_d4_module`), or None if it has none. This is also the D4 `cluster_key`."""
    return datasets.d4_cluster_key(case)


def annotate_cluster_keys(case_list: dict[str, Any], cases_by_id: dict[str, dict]) -> dict[str, Any]:
    """A copy of the committed D4 case list with `cluster_key` added to every case (task 0b).
    Nothing else changes: the IDs, statuses and counts are CP3's."""
    out = {**case_list, "cases": []}
    for entry in case_list["cases"]:
        case = cases_by_id.get(entry["id"])
        out["cases"].append({**entry, "cluster_key": range_key_for(case) if case else None})
    out["cluster_count"] = len({c["cluster_key"] for c in out["cases"]})
    return out


def _reuse_key(case: dict[str, Any]) -> tuple | None:
    rk = range_key_for(case)
    if rk is None or not case["fix_commits"]:
        return None
    fc = case["fix_commits"][0]
    return rk, fc["host"], fc["owner"], fc["repo"]


def doc_comment_above(lines: list[str], start: int) -> str:
    """The contiguous `//` comment block directly above 1-based line `start` (a Go doc
    comment). A blank line ends it; `/* */` block comments are not recognised (rare for Go
    doc comments; a documented simplification)."""
    out = []
    i = start - 2
    while i >= 0 and lines[i].lstrip().startswith("//"):
        out.append(lines[i].strip())
        i -= 1
    return "\n".join(reversed(out))


def signature_of(body: str) -> str:
    """The declaration up to (not including) the opening brace, on one line."""
    head = body.split("{", 1)[0] if "{" in body else body.splitlines()[0] if body else ""
    sig = " ".join(head.split())
    return sig[:MAX_SIGNATURE_CHARS]


def extract_candidate_code(repo_dir: Path, rr: dict[str, Any], runner=subprocess.run) -> dict[str, Any]:
    """Code text for every candidate of one ReleaseRange. `body_side` records which version
    the body was read from: `OLD` (the vulnerable version; used for OLD and BOTH candidates)
    or `NEW` (only for functions that exist only in the fixed version)."""
    texts: dict[tuple[str, str], str | None] = {}

    def file_text(sha: str, path: str) -> str | None:
        if (sha, path) not in texts:
            texts[(sha, path)] = git_fetch.file_content_at(repo_dir, sha, path, runner)
        return texts[(sha, path)]

    out: dict[str, dict[str, Any]] = {}
    missing = 0
    for cand in rr["candidates"]:
        if cand["side"] in ("OLD", "BOTH"):
            body_side, sha, rng = "OLD", rr["from"]["commit"], cand["old_range"]
        else:
            body_side, sha, rng = "NEW", rr["to"]["commit"], cand["new_range"]
        text = file_text(sha, rng["file"])
        if text is None:
            missing += 1
            out[cand["candidate_id"]] = {"package_name": "", "doc": "", "signature": "", "body": "",
                                         "body_side": body_side, "file": rng["file"], "missing": True}
            continue
        lines = text.splitlines()
        body = "\n".join(lines[rng["start"] - 1 : rng["end"]])
        m = _PACKAGE_RE.search(text)
        out[cand["candidate_id"]] = {
            "package_name": m.group(1) if m else "", "doc": doc_comment_above(lines, rng["start"]),
            "signature": signature_of(body), "body": body, "body_side": body_side, "file": rng["file"],
            "missing": False,
        }
    return {"schema_version": CODE_SCHEMA_VERSION, "case_id": rr["case_id"], "module": rr["module"],
            "from_commit": rr["from"]["commit"], "to_commit": rr["to"]["commit"],
            "candidates": out, "missing_bodies": missing, "complete": True}


def _write_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None  # a half-written file from an interrupted run: recompute


def is_complete(case_id: str, data_dir: Path = DATA_DIR) -> bool:
    rr = _load(data_dir / "release_range" / f"{case_id}.json")
    code = _load(data_dir / "candidate_code" / f"{case_id}.json")
    return rr is not None and code is not None and code.get("complete") is True and code["case_id"] == case_id


def _compare(expected: dict[str, Any], rr: dict[str, Any]) -> list[str]:
    diffs = []
    if expected["status"] != rr["status"]:
        diffs.append(f"status {expected['status']} -> {rr['status']}")
    if expected.get("candidate_count") != len(rr["candidates"]):
        diffs.append(f"candidate_count {expected.get('candidate_count')} -> {len(rr['candidates'])}")
    if expected.get("commit_count") != len(rr["commits"]):
        diffs.append(f"commit_count {expected.get('commit_count')} -> {len(rr['commits'])}")
    return diffs


def materialize_d4(case_list: dict[str, Any], cases_by_id: dict[str, dict], binary, data_dir: Path = DATA_DIR,
                   cache_root: Path | None = None, runner=subprocess.run, delay_s: float = DEFAULT_DELAY_S,
                   build_range: Callable[..., dict] | None = None,
                   progress: Callable[[int, int, str, str], None] | None = None,
                   sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Rebuild evidence for every case in `case_list` (the committed D4_cases.json content),
    in id order. Returns a summary: per-case action (`skipped` already complete / `built` /
    `reused` from an identical range), status, counts, any differences from the case list,
    and timings. `build_range` defaults to CP3's `datasets.d4_candidate_count` (tests inject
    one pointing at a local repository)."""
    build_range = build_range or (lambda case, module: datasets.d4_candidate_count(
        case, module, binary, cache_root, runner))
    rr_dir, code_dir = data_dir / "release_range", data_dir / "candidate_code"
    started = time.monotonic()
    done_by_reuse_key: dict[tuple, str] = {}
    rows = []
    entries = sorted(case_list["cases"], key=lambda c: c["id"])
    for i, expected in enumerate(entries, start=1):
        case_id = expected["id"]
        t0 = time.monotonic()
        case = cases_by_id.get(case_id)
        if case is None:
            rows.append({"id": case_id, "action": "missing_from_vulndb", "status": None,
                         "differences": ["case id not found in the pinned vulndb snapshot"], "seconds": 0.0})
            continue
        rkey = _reuse_key(case)
        if is_complete(case_id, data_dir):
            action = "skipped"
            rr = _load(rr_dir / f"{case_id}.json")
        elif rkey is not None and rkey in done_by_reuse_key:
            action = "reused"
            src = done_by_reuse_key[rkey]
            rr = {**_load(rr_dir / f"{src}.json"), "case_id": case_id}
            code = {**_load(code_dir / f"{src}.json"), "case_id": case_id, "copied_from": src}
            _write_atomic(rr_dir / f"{case_id}.json", rr)
            _write_atomic(code_dir / f"{case_id}.json", code)
        else:
            action = "built"
            module = datasets.pick_d4_module(case)
            rr = build_range(case, module)
            _write_atomic(rr_dir / f"{case_id}.json", rr)
            if rr["candidates"]:
                fc = case["fix_commits"][0]
                repo_dir = git_fetch.repo_cache_dir(fc["host"], fc["owner"], fc["repo"], cache_root)
                code = extract_candidate_code(repo_dir, rr, runner)
            else:
                code = {"schema_version": CODE_SCHEMA_VERSION, "case_id": case_id, "module": rr["module"],
                        "from_commit": rr["from"]["commit"], "to_commit": rr["to"]["commit"],
                        "candidates": {}, "missing_bodies": 0, "complete": True}
            _write_atomic(code_dir / f"{case_id}.json", code)
        if rkey is not None and rkey not in done_by_reuse_key:
            done_by_reuse_key[rkey] = case_id
        code = _load(code_dir / f"{case_id}.json") or {}
        rows.append({"id": case_id, "action": action, "status": rr["status"],
                     "candidate_count": len(rr["candidates"]), "commit_count": len(rr["commits"]),
                     "missing_bodies": code.get("missing_bodies", 0), "cluster_key": range_key_for(case),
                     "differences": _compare(expected, rr), "seconds": round(time.monotonic() - t0, 2)})
        if progress is not None:
            progress(i, len(entries), case_id, f"{action} {rr['status']}")
        if action == "built" and delay_s > 0 and i < len(entries):
            sleep(delay_s)

    status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    for r in rows:
        status_counts[str(r["status"])] = status_counts.get(str(r["status"]), 0) + 1
        action_counts[r["action"]] = action_counts.get(r["action"], 0) + 1
    return {
        "dataset": "D4", "case_count": len(entries), "status_counts": status_counts,
        "expected_status_counts": case_list.get("status_counts"), "action_counts": action_counts,
        "differences": [{"id": r["id"], "differences": r["differences"]} for r in rows if r["differences"]],
        "wall_seconds": round(time.monotonic() - started, 1), "cases": rows,
    }
