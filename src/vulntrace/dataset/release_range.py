"""Mode 2 evidence: ReleaseRange extraction between two module versions (CP3 deliverable 4).

From `vulnerable_at` to the smallest `fixed` version above it (feasibility trial 5; the
version pair itself is already computed per module by the report reader, deliverable 2).
Tag naming handles sub-module prefixes and the "+incompatible" suffix; pseudo-versions
resolve through their embedded commit hash. Commit history is fetched with a bound; a range
that exceeds it is marked TRUNCATED rather than silently cut (candidates are still reported:
they come from a single two-tree diff, not from walking history).
"""

import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from vulntrace.dataset import git_fetch
from vulntrace.dataset.fix_evidence import _classify_changed_files, _funcs_for_file
from vulntrace.dataset.govers import pseudo_version_parts
from vulntrace.methods.helper import DEFAULT_TIMEOUT_S

SCHEMA_VERSION = "1.0"
STATUS_AVAILABLE = "AVAILABLE"
STATUS_TAG_NOT_FOUND = "TAG_NOT_FOUND"
STATUS_PSEUDO_VERSION_UNRESOLVED = "PSEUDO_VERSION_UNRESOLVED"
STATUS_EMPTY = "EMPTY"
STATUS_TRUNCATED = "TRUNCATED"

DEFAULT_COMMIT_CAP = 500

_MAJOR_SUFFIX = re.compile(r"^(.*)/v(\d+)$")


def strip_incompatible(version: str) -> str:
    return version[: -len("+incompatible")] if version.endswith("+incompatible") else version


def split_major_suffix(module_path: str) -> tuple[str, int | None]:
    """("github.com/x/y", 3) for "github.com/x/y/v3"; (path, None) if there is no /vN
    suffix (true for major versions 0 and 1, which are not written in the path)."""
    m = _MAJOR_SUFFIX.match(module_path.rstrip("/"))
    if m and int(m.group(2)) >= 2:
        return m.group(1), int(m.group(2))
    return module_path.rstrip("/"), None


def module_subdir(module_path: str, fix_owner: str, fix_repo: str) -> str:
    """Best-effort repo-relative subdirectory for `module_path`, given the repo this case's
    fix commit lives in (vulndb's `module` field does not say where the repository root is;
    this project does not resolve vanity import paths, so a module path that is not directly
    under github.com/<fix_owner>/<fix_repo> is assumed to be the repo root - a documented
    limitation, see the CP3 report)."""
    base, _ = split_major_suffix(module_path)
    prefix = f"github.com/{fix_owner}/{fix_repo}"
    if base == prefix:
        return ""
    if base.startswith(prefix + "/"):
        return base[len(prefix) + 1 :]
    return ""


def candidate_tags(module_path: str, version: str, fix_owner: str, fix_repo: str) -> list[str]:
    """Candidate git tag names for `version` of `module_path`, most likely first: the
    "branch convention" (tag at the repo root, the common case for major version 2+) before
    the "subdirectory convention" (a `vN/` prefix, used when the module actually lives in a
    `vN` subdirectory) - trying a short list and keeping whichever resolves is simpler and
    more robust than inspecting go.mod to tell the two conventions apart."""
    v = strip_incompatible(version)
    subdir = module_subdir(module_path, fix_owner, fix_repo)
    _, major = split_major_suffix(module_path)
    if subdir:
        return [f"{subdir}/v{v}"]
    tags = [f"v{v}"]
    if major is not None:
        tags.append(f"v{major}/v{v}")
    return tags


class ResolveResult:
    def __init__(self, status: str, ref: str | None, commit: str | None):
        self.status, self.ref, self.commit = status, ref, commit


def _shallow_since_date(timestamp: str) -> str:
    """"YYYY-MM-DD", one day before a pseudo-version's embedded "YYYYMMDDHHMMSS" timestamp
    (a safety margin against any clock/timezone slack between committer time and the
    timestamp vulndb recorded)."""
    dt = datetime.strptime(timestamp, "%Y%m%d%H%M%S") - timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def _resolve_pseudo_version(host: str, owner: str, repo: str, version: str, cache_root: Path | None,
                            runner, remote_url: str | None) -> "ResolveResult":
    """A pseudo-version's abbreviated commit hash cannot be fetched directly (git's wire
    protocol needs a full 40-character SHA to fetch an unadvertised object, not an
    abbreviation - verified: see the CP3 report). Instead, fetch history back to the
    timestamp embedded alongside the hash (bounded by date, not by a possibly-huge commit
    count) and resolve the abbreviation locally."""
    parts = pseudo_version_parts(version)
    if parts is None:
        return ResolveResult(STATUS_PSEUDO_VERSION_UNRESOLVED, None, None)
    timestamp, short_sha = parts
    try:
        repo_dir = git_fetch.fetch_since(host, owner, repo, _shallow_since_date(timestamp),
                                         cache_root=cache_root, runner=runner, remote_url=remote_url)
    except (git_fetch.GitFetchError, ValueError):
        return ResolveResult(STATUS_PSEUDO_VERSION_UNRESOLVED, None, None)
    full_sha = git_fetch.resolve_abbreviated(repo_dir, short_sha, runner)
    if full_sha is None:
        return ResolveResult(STATUS_PSEUDO_VERSION_UNRESOLVED, None, None)
    return ResolveResult(STATUS_AVAILABLE, full_sha, full_sha)


def resolve_version(host: str, owner: str, repo: str, module_path: str, version: str,
                    cache_root: Path | None, runner=subprocess.run, remote_url: str | None = None) -> ResolveResult:
    """Resolve one module version to a commit: a pseudo-version resolves through its
    embedded commit hash; anything else resolves through a git tag (trying the candidate
    forms `candidate_tags` gives, in order)."""
    if pseudo_version_parts(version) is not None:
        return _resolve_pseudo_version(host, owner, repo, version, cache_root, runner, remote_url)
    for tag in candidate_tags(module_path, version, owner, repo):
        _repo_dir, sha = git_fetch.fetch_ref(host, owner, repo, tag, depth=1, cache_root=cache_root, runner=runner,
                                            remote_url=remote_url)
        if sha is not None:
            return ResolveResult(STATUS_AVAILABLE, tag, sha)
    return ResolveResult(STATUS_TAG_NOT_FOUND, None, None)


def _diff_candidates(repo_dir: Path, from_sha: str, to_sha: str, runner,
                     helper_binary, helper_timeout: float) -> dict[str, Any]:
    """Every changed non-test, non-vendor Go function between the two refs - a single
    two-tree diff, independent of how many commits separate them."""
    files = git_fetch.changed_files(repo_dir, from_sha, to_sha, runner)
    go_files, test_files, non_go_files = _classify_changed_files(files)
    candidates = []
    file_candidate_ids: dict[str, list[str]] = {}
    for path in sorted(go_files):
        old_text = git_fetch.file_content_at(repo_dir, from_sha, path, runner)
        new_text = git_fetch.file_content_at(repo_dir, to_sha, path, runner)
        ofuncs = _funcs_for_file(path, old_text, helper_binary, None, helper_timeout) if old_text is not None else []
        nfuncs = _funcs_for_file(path, new_text, helper_binary, None, helper_timeout) if new_text is not None else []
        old_by_sym = {fn["symbol"]: fn for fn in ofuncs}
        new_by_sym = {fn["symbol"]: fn for fn in nfuncs}
        # A symbol present on both sides counts as changed only if its *text* differs -
        # same idea as "did the function's body change", computed directly from the source
        # text spanned by its line range rather than via diff hunks (Mode 2 has no hunks;
        # it only needs the candidate list, not line-level evidence).
        changed_syms = []
        for sym in sorted(set(old_by_sym) | set(new_by_sym)):
            in_old, in_new = sym in old_by_sym, sym in new_by_sym
            if in_old and in_new:
                o, n = old_by_sym[sym], new_by_sym[sym]
                old_body = "\n".join((old_text or "").splitlines()[o["start"] - 1 : o["end"]])
                new_body = "\n".join((new_text or "").splitlines()[n["start"] - 1 : n["end"]])
                if old_body != new_body:
                    changed_syms.append(sym)
            else:
                changed_syms.append(sym)
        package_dir = Path(path).parent.as_posix()
        package_dir = "" if package_dir == "." else package_dir
        ids_here = []
        for sym in changed_syms:
            in_old, in_new = sym in old_by_sym, sym in new_by_sym
            side = "BOTH" if in_old and in_new else ("OLD" if in_old else "NEW")
            cid = f"r{len(candidates) + 1}"
            candidates.append({
                "candidate_id": cid, "package_dir": package_dir, "symbol": sym, "side": side,
                "old_range": {"file": path, "start": old_by_sym[sym]["start"], "end": old_by_sym[sym]["end"]}
                if in_old else None,
                "new_range": {"file": path, "start": new_by_sym[sym]["start"], "end": new_by_sym[sym]["end"]}
                if in_new else None,
            })
            ids_here.append(cid)
        if ids_here:
            file_candidate_ids[path] = ids_here
    return {"candidates": candidates, "non_go_files": non_go_files, "test_files_changed": len(test_files),
           "file_candidate_ids": file_candidate_ids}


def _is_ancestor(repo_dir: Path, ancestor: str, descendant: str, runner) -> bool:
    p = runner(["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=repo_dir,
              capture_output=True, text=True, timeout=30)
    return p.returncode == 0


def _touches_candidates(repo_dir: Path, sha: str, runner, file_candidate_ids: dict[str, list[str]]) -> list[str]:
    nf = runner(["git", "diff", "--no-renames", "--name-only", f"{sha}^", sha], cwd=repo_dir,
               capture_output=True, text=True, timeout=60)
    touched_files = set(nf.stdout.split()) if nf.returncode == 0 else set()
    return sorted({cid for f, ids in file_candidate_ids.items() if f in touched_files for cid in ids},
                 key=lambda c: int(c[1:]))


def _walk_commits(host: str, owner: str, repo: str, repo_dir: Path, from_sha: str, to_sha: str, runner,
                  file_candidate_ids: dict[str, list[str]], commit_cap: int, cache_root: Path | None,
                  remote_url: str | None) -> tuple[list[dict], bool]:
    """([{sha, subject, body, touches_candidates}], truncated). `body` is included because
    the B-ID baseline (CP3 deliverable 6) searches commit subjects AND bodies for the
    advisory's CVE/GHSA/GO identifier.

    `touches_candidates` is file-level (a commit "touches" every candidate in a file it
    changed at all) - a documented simplification that avoids re-running the helper per
    intermediate commit, which the scale of some ranges (feasibility trial 5: up to 2,558
    changed functions) makes costly.

    Deepens the clone's history from `to_sha` to `commit_cap + 1` commits first: `from_sha`
    and `to_sha` were each resolved with their own independent shallow fetch, so without
    this there may be no connected history between them at all yet to walk. If `from_sha`
    still is not an ancestor of `to_sha` within that bound, the range exceeds the cap (or
    the two refs are not connected by a simple linear history); `commits` then falls back to
    the most recent `commit_cap` commits reachable from `to_sha`, and the range is truncated.
    """
    try:
        git_fetch.deepen(host, owner, repo, to_sha, commit_cap + 1, cache_root=cache_root, runner=runner,
                         remote_url=remote_url)
    except git_fetch.GitFetchError:
        pass  # best effort; connectivity is re-checked below regardless
    # %x1e separates commits, %x1f separates fields within one commit (subject/body text
    # essentially never contains either control character).
    log_format = "--format=%H%x1f%s%x1f%b%x1e"
    if _is_ancestor(repo_dir, from_sha, to_sha, runner):
        p = runner(["git", "log", log_format, f"{from_sha}..{to_sha}"], cwd=repo_dir,
                  capture_output=True, text=True, timeout=120)
        records = [r for r in p.stdout.split("\x1e") if r.strip()] if p.returncode == 0 else []
        truncated = p.returncode != 0 or len(records) > commit_cap
    else:
        p = runner(["git", "log", f"--max-count={commit_cap}", log_format, to_sha], cwd=repo_dir,
                  capture_output=True, text=True, timeout=120)
        records = [r for r in p.stdout.split("\x1e") if r.strip()] if p.returncode == 0 else []
        truncated = True
    out = []
    for record in records[:commit_cap]:
        sha, _, rest = record.lstrip("\n").partition("\x1f")
        subject, _, body = rest.partition("\x1f")
        out.append({"sha": sha, "subject": subject, "body": body.strip("\n"),
                   "touches_candidates": _touches_candidates(repo_dir, sha, runner, file_candidate_ids)})
    return out, truncated


def build_release_range(case_id: str, module: str, vulnerable_at: str, fixed_in: str,
                        host: str, owner: str, repo: str, binary=None, cache_root: Path | None = None,
                        runner=subprocess.run, helper_timeout: float = DEFAULT_TIMEOUT_S,
                        commit_cap: int = DEFAULT_COMMIT_CAP, remote_url: str | None = None) -> dict[str, Any]:
    """ReleaseRange (schemas/release_range.schema.json) from `vulnerable_at` to `fixed_in`
    of `module`, in the repository the case's (host, owner, repo) fix commit lives in."""
    from_res = resolve_version(host, owner, repo, module, vulnerable_at, cache_root, runner, remote_url)
    to_res = resolve_version(host, owner, repo, module, fixed_in, cache_root, runner, remote_url)
    base = {
        "schema_version": SCHEMA_VERSION, "case_id": case_id, "module": module,
        "from": {"version": vulnerable_at, "ref": from_res.ref, "commit": from_res.commit},
        "to": {"version": fixed_in, "ref": to_res.ref, "commit": to_res.commit},
        "candidates": [], "commits": [], "non_go_files_changed": [], "test_files_changed": 0,
    }
    if from_res.status != STATUS_AVAILABLE:
        return {**base, "status": from_res.status}
    if to_res.status != STATUS_AVAILABLE:
        return {**base, "status": to_res.status}

    repo_dir = git_fetch.repo_cache_dir(host, owner, repo, cache_root)
    diff = _diff_candidates(repo_dir, from_res.commit, to_res.commit, runner, binary, helper_timeout)
    commits, truncated = _walk_commits(host, owner, repo, repo_dir, from_res.commit, to_res.commit, runner,
                                       diff["file_candidate_ids"], commit_cap, cache_root, remote_url)
    status = STATUS_TRUNCATED if truncated else (STATUS_EMPTY if not diff["candidates"] else STATUS_AVAILABLE)
    return {
        **base, "status": status, "candidates": diff["candidates"],
        "commits": [{"sha": c["sha"], "subject": c["subject"], "body": c["body"],
                    "touches_candidates": c["touches_candidates"]}
                   for c in commits],
        "non_go_files_changed": sorted(set(diff["non_go_files"])), "test_files_changed": diff["test_files_changed"],
    }
