"""Mode 1 evidence: FixEvidence extraction from a GitHub fix commit (CP3 deliverable 3).

For each fix commit: a bounded fetch of the commit and its parent (git_fetch.py), the
changed non-test, non-vendor Go functions on both sides (via the helper's `funcs` mode),
and numbered hunks. An unfetchable commit is counted, never silently dropped (see
`unfetchable_commits`): the case-level status is only UNAVAILABLE when none of its fix
commits could be fetched at all.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from vulntrace.dataset import diffparse, git_fetch
from vulntrace.methods.helper import DEFAULT_TIMEOUT_S, HelperError, run_helper

SCHEMA_VERSION = "1.0"
STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_EMPTY = "EMPTY"


def is_vendor_path(path: str) -> bool:
    return path == "vendor" or path.startswith("vendor/") or "/vendor/" in path


def _funcs_for_file(path: str, text: str, binary, helper_runner, timeout: float) -> list[dict[str, Any]]:
    """FuncInfo list for one file's content, or [] if the helper cannot parse it.

    Called once per (file, side) rather than batched, so one file with unusual syntax
    (generated code, a pre-module-era snapshot, ...) degrades gracefully instead of making
    the helper's funcs mode fail its whole request and losing every other file's evidence.

    `helper_runner` is the Python-to-Go-helper Runner (methods.helper.Runner: (argv,
    timeout) -> (rc, out, err)) - distinct from the git runner used elsewhere in this
    module (subprocess.run-compatible kwargs), never the same callable.
    """
    with tempfile.TemporaryDirectory(prefix="vt_fixev_") as tmp:
        tmp_path = Path(tmp)
        p = tmp_path / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", errors="replace")
        request = {"contract_version": "1.0", "mode": "funcs", "module_dir": tmp_path.as_posix(), "files": [path]}
        try:
            response = run_helper("funcs", request, binary=binary, timeout=timeout, runner=helper_runner)
        except HelperError:
            return []
        if not response["ok"]:
            return []
        return response["results"][0]["functions"]


def _classify_changed_files(files: list[tuple[str, str]]) -> tuple[list[str], list[str], list[str]]:
    """(go_files, test_files, non_go_files) from git's (status, path) pairs. Vendored Go
    files are dropped entirely (neither a candidate source nor counted as non-Go)."""
    go_files, test_files, non_go_files = [], [], []
    for _status, path in files:
        if not path.endswith(".go"):
            non_go_files.append(path)
        elif is_vendor_path(path):
            continue
        elif path.endswith("_test.go"):
            test_files.append(path)
        else:
            go_files.append(path)
    return go_files, test_files, non_go_files


def _file_evidence(path: str, repo_dir: Path, old_ref: str, new_ref: str, binary, runner,
                   helper_timeout: float, helper_runner=None) -> tuple[list[dict], list[dict]]:
    """(hunks, candidates) for one changed Go file, with file-local hunk/candidate ids
    ("h1".. / "c1"..) that the caller renumbers globally across the whole commit."""
    old_text = git_fetch.file_content_at(repo_dir, old_ref, path, runner)
    new_text = git_fetch.file_content_at(repo_dir, new_ref, path, runner)
    raw_hunks = diffparse.parse_hunks(git_fetch.unified_diff(repo_dir, old_ref, new_ref, path, runner))
    hunks = []
    for i, h in enumerate(raw_hunks, start=1):
        hunks.append({"hunk_id": f"h{i}", "file": path, "old_start": h["old_start"], "old_lines": h["old_lines"],
                      "new_start": h["new_start"], "new_lines": h["new_lines"], "text": h["text"]})

    ofuncs = _funcs_for_file(path, old_text, binary, helper_runner, helper_timeout) if old_text is not None else []
    nfuncs = _funcs_for_file(path, new_text, binary, helper_runner, helper_timeout) if new_text is not None else []
    old_ranges = {fn["symbol"]: (fn["start"], fn["end"]) for fn in ofuncs}
    new_ranges = {fn["symbol"]: (fn["start"], fn["end"]) for fn in nfuncs}

    old_touch: dict[str, set] = {}
    new_touch: dict[str, set] = {}
    for h, raw in zip(hunks, raw_hunks):
        ot, nt = diffparse.old_range(raw), diffparse.new_range(raw)
        for fn in ofuncs:
            if diffparse.overlaps_function(ot, raw["old_start"], fn["start"], fn["end"]):
                old_touch.setdefault(fn["symbol"], set()).add(h["hunk_id"])
        for fn in nfuncs:
            if diffparse.overlaps_function(nt, raw["new_start"], fn["start"], fn["end"]):
                new_touch.setdefault(fn["symbol"], set()).add(h["hunk_id"])

    package_dir = Path(path).parent.as_posix()
    package_dir = "" if package_dir == "." else package_dir
    candidates = []
    for i, symbol in enumerate(sorted(set(old_touch) | set(new_touch)), start=1):
        in_old, in_new = symbol in old_touch, symbol in new_touch
        side = "BOTH" if in_old and in_new else ("OLD" if in_old else "NEW")
        hunk_ids = sorted(old_touch.get(symbol, set()) | new_touch.get(symbol, set()), key=lambda h: int(h[1:]))
        candidates.append({
            "candidate_id": f"c{i}", "package_dir": package_dir, "symbol": symbol, "side": side,
            "old_range": {"file": path, **dict(zip(("start", "end"), old_ranges[symbol]))} if in_old else None,
            "new_range": {"file": path, **dict(zip(("start", "end"), new_ranges[symbol]))} if in_new else None,
            "hunk_ids": hunk_ids,
        })
    return hunks, candidates


def commit_evidence(repo_dir: Path, parent_sha: str, sha: str, binary, runner=subprocess.run,
                    helper_timeout: float = DEFAULT_TIMEOUT_S, helper_runner=None) -> dict[str, Any]:
    """hunks/candidates (globally numbered within this one commit) plus file counts, for
    the diff between `parent_sha` and `sha`."""
    files = git_fetch.changed_files(repo_dir, parent_sha, sha, runner)
    go_files, test_files, non_go_files = _classify_changed_files(files)
    all_hunks: list[dict] = []
    all_candidates: list[dict] = []
    for path in sorted(go_files):
        hunks, candidates = _file_evidence(path, repo_dir, parent_sha, sha, binary, runner, helper_timeout,
                                           helper_runner)
        id_map = {}
        for h in hunks:
            new_id = f"h{len(all_hunks) + 1}"
            id_map[h["hunk_id"]] = new_id
            h["hunk_id"] = new_id
            all_hunks.append(h)
        for c in candidates:
            c["candidate_id"] = f"c{len(all_candidates) + 1}"
            c["hunk_ids"] = [id_map[h] for h in c["hunk_ids"]]
            all_candidates.append(c)
    return {"hunks": all_hunks, "candidates": all_candidates, "non_go_files": non_go_files,
           "test_files_changed": len(test_files)}


def build_fix_evidence(case_id: str, fix_commits: list[dict[str, str]], binary=None,
                       cache_root: Path | None = None, runner=subprocess.run,
                       helper_timeout: float = DEFAULT_TIMEOUT_S, remote_url: str | None = None,
                       helper_runner=None) -> dict[str, Any]:
    """FixEvidence (schemas/fix_evidence.schema.json) for every fix commit of one case.
    `fix_commits` is VulnCase.fix_commits ({host, owner, repo, sha} dicts). `remote_url`
    overrides every commit's GitHub URL; tests use it to point at one local repository so
    nothing here needs the network (real use always has one real GitHub URL per commit).
    `runner` is the git runner; `helper_runner` is the separate, unrelated Python-to-Go-
    helper Runner (defaults to a real subprocess call, as methods.helper.run_helper does)."""
    commits: list[dict] = []
    unfetchable: list[dict] = []
    per_commit: list[dict] = []
    for fc in fix_commits:
        host, owner, repo, sha = fc["host"], fc["owner"], fc["repo"], fc["sha"]
        try:
            repo_dir = git_fetch.fetch_commit(host, owner, repo, sha, cache_root=cache_root, runner=runner,
                                              remote_url=remote_url)
            parent = git_fetch.parent_sha(repo_dir, sha, runner)
            if parent is None:
                raise git_fetch.GitFetchError("NO_PARENT", f"{sha} is a root commit (no parent to diff against)")
            evidence = commit_evidence(repo_dir, parent, sha, binary, runner, helper_timeout, helper_runner)
        except (git_fetch.GitFetchError, HelperError) as exc:
            code = getattr(exc, "code", "UNKNOWN")
            unfetchable.append({"host": host, "owner": owner, "repo": repo, "sha": sha,
                                "error": f"{code}: {exc}"})
            continue
        commits.append({"sha": sha, "parent_sha": parent})
        per_commit.append(evidence)

    all_hunks: list[dict] = []
    all_candidates: list[dict] = []
    non_go_files: list[str] = []
    test_files_changed = 0
    for evidence in per_commit:
        id_map = {}
        for h in evidence["hunks"]:
            new_id = f"h{len(all_hunks) + 1}"
            id_map[h["hunk_id"]] = new_id
            h["hunk_id"] = new_id
            all_hunks.append(h)
        for c in evidence["candidates"]:
            c["candidate_id"] = f"c{len(all_candidates) + 1}"
            c["hunk_ids"] = [id_map[h] for h in c["hunk_ids"]]
            all_candidates.append(c)
        non_go_files.extend(evidence["non_go_files"])
        test_files_changed += evidence["test_files_changed"]

    if not commits:
        status = STATUS_UNAVAILABLE
    elif not all_candidates:
        status = STATUS_EMPTY
    else:
        status = STATUS_AVAILABLE
    estimated_tokens = sum(len(h["text"]) for h in all_hunks) // 4
    return {
        "schema_version": SCHEMA_VERSION, "case_id": case_id, "status": status,
        "commits": commits, "unfetchable_commits": unfetchable,
        "candidates": all_candidates, "hunks": all_hunks,
        "non_go_files_changed": sorted(set(non_go_files)), "test_files_changed": test_files_changed,
        "estimated_tokens": estimated_tokens,
    }
