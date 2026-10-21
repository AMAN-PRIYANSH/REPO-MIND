"""Re-materialise D4 (and D1) evidence from the committed case lists (CP4 task 0a).

CP3 committed only the D4 case list (`docs/results/datasets/D4_cases.json`); the bulky
per-case evidence lived in a gitignored `data/` directory on an earlier session's machine.
This rebuilds it for exactly the committed 120 IDs - it never re-selects cases - from the
pinned vulndb commit:

- `data/release_range/<id>.json`: the ReleaseRange, as `dataset build --mode release` wrote it
  (same code path, so the CP3 baselines and ceiling investigation read it unchanged);
- `data/candidate_code/<id>.json`: per candidate, the Go package name, doc comment, signature
  and body text the CP4 chunker needs (vulnerable-side body; fixed-side only for functions
  that exist only in the fixed version).

Resumable (a case is skipped only if both files are complete AND the stored result matches the
committed case list's status and counts; a failed or mismatching result is rebuilt, never reused),
sequential, with a small
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

from vulntrace.dataset import datasets, fix_evidence, git_fetch, release_range
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


def is_complete(case_id: str, data_dir: Path = DATA_DIR, expected: dict[str, Any] | None = None) -> bool:
    """Both evidence files exist and are whole. With `expected` (the case's entry in the
    committed case list) the stored result must also match its status and counts (FIX-2):
    a failed result such as TAG_NOT_FOUND where AVAILABLE is expected is not "done"."""
    rr = _load(data_dir / "release_range" / f"{case_id}.json")
    code = _load(data_dir / "candidate_code" / f"{case_id}.json")
    if rr is None or code is None or code.get("complete") is not True or code.get("case_id") != case_id:
        return False
    return expected is None or not _compare(expected, rr)


_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
_REMOTE_REF_RE = re.compile(r"(couldn't find remote ref) \S+")
_QUOTED_RE = re.compile(r"'[^']*'")


def normalise_git_error(message: str) -> str:
    """Group key for a git error line: the same failure for different tags/commits/paths
    counts once."""
    message = _SHA_RE.sub("<sha>", message)
    message = _REMOTE_REF_RE.sub(r"\1 <ref>", message)
    return _QUOTED_RE.sub("'<x>'", message)


def top_git_errors(rows: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """The `n` most common git error messages among the rows (FIX-3), as
    [{"message", "count", "example_case"}], most common first."""
    counts: dict[str, list] = {}
    for r in rows:
        msg = r.get("git_error")
        if msg:
            entry = counts.setdefault(normalise_git_error(msg), [0, r["id"]])
            entry[0] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1][0], kv[0]))[:n]
    return [{"message": m, "count": c, "example_case": ex} for m, (c, ex) in ranked]


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
        src = done_by_reuse_key.get(rkey) if rkey is not None else None
        src_rr = _load(rr_dir / f"{src}.json") if src else None
        if is_complete(case_id, data_dir, expected):
            action = "skipped"
            rr = _load(rr_dir / f"{case_id}.json")
        elif src_rr is not None and not _compare(expected, src_rr):
            # Only a result that matches the committed case list is ever copied (FIX-2).
            action = "reused"
            rr = {**src_rr, "case_id": case_id}
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
        differences = _compare(expected, rr)
        if rkey is not None and rkey not in done_by_reuse_key and not differences:
            done_by_reuse_key[rkey] = case_id
        code = _load(code_dir / f"{case_id}.json") or {}
        rows.append({"id": case_id, "action": action, "status": rr["status"],
                     "candidate_count": len(rr["candidates"]), "commit_count": len(rr["commits"]),
                     "missing_bodies": code.get("missing_bodies", 0), "cluster_key": range_key_for(case),
                     "git_error": rr.get("git_error"),
                     "differences": differences, "seconds": round(time.monotonic() - t0, 2)})
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
        "top_git_errors": top_git_errors(rows),
        "wall_seconds": round(time.monotonic() - started, 1), "cases": rows,
    }


def diagnose_case(case: dict[str, Any], binary, cache_root: Path | None = None, runner=subprocess.run,
                  print_line: Callable[[str], None] = print, build_range: Callable[..., dict] | None = None,
                  expected: dict[str, Any] | None = None, max_ok_printed: int = 12) -> dict[str, Any]:
    """FIX-1: build the ReleaseRange for ONE case and print every git command with its exit
    code and stderr, so a git problem is seen as git reported it. Writes nothing to `data/`.
    Returns {"status", "candidate_count", "git_error", "git_calls": [...]}."""
    calls: list[dict[str, Any]] = []

    def logging_runner(args, **kwargs):
        t0 = time.monotonic()
        p = runner(args, **kwargs)
        if args and args[0] == "git":
            rec = {"args": " ".join(map(str, args[1:])), "cwd": str(kwargs.get("cwd")), "returncode": p.returncode,
                   "stderr": (p.stderr or "").strip()[:2000], "seconds": round(time.monotonic() - t0, 2)}
            calls.append(rec)
            # Every failure is printed; successes only until `max_ok_printed` (a range can have
            # hundreds of per-commit `git diff` calls), the rest are counted.
            shown = sum(1 for c in calls if c["returncode"] == 0)
            if rec["returncode"] != 0 or shown <= max_ok_printed:
                print_line(f"git {rec['args']}  [cwd {rec['cwd']}]  -> exit {rec['returncode']} in {rec['seconds']}s")
                for line in rec["stderr"].splitlines()[:6]:
                    print_line(f"    stderr: {line}")
        return p

    build_range = build_range or (lambda c, m: datasets.d4_candidate_count(c, m, binary, cache_root, logging_runner))
    module = datasets.pick_d4_module(case)
    rr = build_range(case, module)
    result = {"id": case["id"], "module": module["module"], "status": rr["status"],
              "candidate_count": len(rr["candidates"]), "git_error": rr.get("git_error"), "git_calls": calls}
    if expected is not None:
        result["differences"] = _compare(expected, rr)
    ok = sum(1 for c in calls if c["returncode"] == 0)
    print_line(f"{len(calls)} git calls: {ok} exit 0 ({max(0, ok - max_ok_printed)} not printed), {len(calls) - ok} failed")
    print_line(f"{case['id']}: status {rr['status']}, {len(rr['candidates'])} candidates, "
               f"git_error={rr.get('git_error')!r}"
               + (f", differences from the case list: {result['differences'] or 'none'}" if expected else ""))
    return result


def d1_cluster_key(case: dict[str, Any]) -> str:
    """D1 cluster key: the set of fix commits. Two advisories fixed by the same commit(s)
    share identical FixEvidence, so they are one statistical unit for E0."""
    return ",".join(sorted(f"{c['owner']}/{c['repo']}@{c['sha']}" for c in case["fix_commits"])) or case["id"]


def materialize_d1(case_list: dict[str, Any], cases_by_id: dict[str, dict], binary, data_dir: Path = DATA_DIR,
                   cache_root: Path | None = None, runner=subprocess.run, delay_s: float = DEFAULT_DELAY_S,
                   build_evidence: Callable[..., dict] | None = None,
                   progress: Callable[[int, int, str, str], None] | None = None,
                   sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """D1 counterpart of `materialize_d4`, needed so CP4 task 0b can re-score E0 with cluster
    intervals: rebuilds `data/fix_evidence/<id>.json` for exactly the committed D1 IDs."""
    build_evidence = build_evidence or (lambda case: fix_evidence.build_fix_evidence(
        case["id"], case["fix_commits"], binary=binary, cache_root=cache_root, runner=runner))
    out_dir = data_dir / "fix_evidence"
    started = time.monotonic()
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
        ev = _load(out_dir / f"{case_id}.json")
        if (ev is not None and ev.get("case_id") == case_id and expected["status"] == ev["status"]
                and expected.get("candidate_count") == len(ev["candidates"])):
            action = "skipped"  # only a stored result that matches the case list counts as done (FIX-2)
        else:
            action = "built"
            ev = build_evidence(case)
            _write_atomic(out_dir / f"{case_id}.json", ev)
        diffs = []
        if expected["status"] != ev["status"]:
            diffs.append(f"status {expected['status']} -> {ev['status']}")
        if expected.get("candidate_count") != len(ev["candidates"]):
            diffs.append(f"candidate_count {expected.get('candidate_count')} -> {len(ev['candidates'])}")
        rows.append({"id": case_id, "action": action, "status": ev["status"], "candidate_count": len(ev["candidates"]),
                     "cluster_key": d1_cluster_key(case), "differences": diffs,
                     "seconds": round(time.monotonic() - t0, 2)})
        if progress is not None:
            progress(i, len(entries), case_id, f"{action} {ev['status']}")
        if action == "built" and delay_s > 0 and i < len(entries):
            sleep(delay_s)
    status_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    for r in rows:
        status_counts[str(r["status"])] = status_counts.get(str(r["status"]), 0) + 1
        action_counts[r["action"]] = action_counts.get(r["action"], 0) + 1
    return {
        "dataset": "D1", "case_count": len(entries), "status_counts": status_counts,
        "expected_status_counts": case_list.get("status_counts"), "action_counts": action_counts,
        "differences": [{"id": r["id"], "differences": r["differences"]} for r in rows if r["differences"]],
        "wall_seconds": round(time.monotonic() - started, 1), "cases": rows,
    }
