"""Bounded git operations against third-party repositories (CP3 deliverables 3 and 4).

Every fetch here is bounded to a specific commit plus a small, explicit depth -
never a full clone - and the repository is cached under a cache directory
outside this project, keyed by host/owner/repo, and reused across cases. The
helper (vt-helper) itself never touches the network (interfaces contract,
section 2); all network use lives here, in Python, as an explicit step.
"""

import os
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_S = 120.0
DEFAULT_FETCH_DEPTH = 2  # the commit plus its parent


class GitFetchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def default_cache_root() -> Path:
    if os.environ.get("VULNTRACE_CACHE"):
        return Path(os.environ["VULNTRACE_CACHE"]) / "repos"
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "vulntrace" / "repos"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "vulntrace" / "repos"


def repo_cache_dir(host: str, owner: str, repo: str, cache_root: Path | None = None) -> Path:
    return (cache_root or default_cache_root()) / host / owner / repo


def repo_url(host: str, owner: str, repo: str) -> str:
    return f"https://{host}/{owner}/{repo}"


def _run(runner, args: list[str], cwd: Path, timeout: float = DEFAULT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return runner(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _ensure_repo_initialised(repo_dir: Path, host: str, owner: str, repo: str, runner,
                             remote_url: str | None = None) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").is_dir():
        return
    init = _run(runner, ["git", "init", "-q"], repo_dir)
    if init.returncode != 0:
        raise GitFetchError("GIT_FAILED", "git init: " + (init.stderr or init.stdout).strip())
    remote = _run(runner, ["git", "remote", "add", "origin", remote_url or repo_url(host, owner, repo)], repo_dir)
    if remote.returncode != 0:
        raise GitFetchError("GIT_FAILED", "git remote add: " + (remote.stderr or remote.stdout).strip())


def object_exists(repo_dir: Path, sha: str, runner) -> bool:
    p = _run(runner, ["git", "cat-file", "-e", sha + "^{commit}"], repo_dir)
    return p.returncode == 0


def fetch_commit(host: str, owner: str, repo: str, sha: str, depth: int = DEFAULT_FETCH_DEPTH,
                 cache_root: Path | None = None, runner=subprocess.run,
                 timeout: float = DEFAULT_TIMEOUT_S, remote_url: str | None = None) -> Path:
    """Ensure `sha` (and, at the default depth, its parent) is present in the local cache
    clone of host/owner/repo. Returns the clone's directory.

    `remote_url` overrides the GitHub URL built from host/owner/repo; tests use it to point
    at a local repository so nothing here needs the network.

    Raises GitFetchError, tagged with a code, on any failure - a commit that cannot be
    fetched is never silently skipped; the caller is expected to count it.
    """
    repo_dir = repo_cache_dir(host, owner, repo, cache_root)
    _ensure_repo_initialised(repo_dir, host, owner, repo, runner, remote_url)
    if object_exists(repo_dir, sha, runner):
        return repo_dir
    fetch = _run(runner, ["git", "fetch", f"--depth={depth}", "origin", sha], repo_dir, timeout=timeout)
    if fetch.returncode != 0:
        raise GitFetchError("FETCH_FAILED", f"git fetch {sha}: " + (fetch.stderr or fetch.stdout).strip())
    if not object_exists(repo_dir, sha, runner):
        raise GitFetchError("FETCH_FAILED", f"commit {sha} not present in {owner}/{repo} after fetch")
    return repo_dir


def parent_sha(repo_dir: Path, sha: str, runner=subprocess.run) -> str | None:
    """The first parent of `sha`, or None if it is a root commit (no parent)."""
    p = _run(runner, ["git", "rev-parse", f"{sha}^1"], repo_dir)
    return p.stdout.strip() if p.returncode == 0 else None


def file_content_at(repo_dir: Path, ref: str, path: str, runner=subprocess.run) -> str | None:
    """Text of `path` at `ref`, or None if it does not exist there. Non-UTF-8 bytes are
    replaced (never raises): a file this project cannot decode is not evidence it can use,
    but a decoding failure must not abort the whole commit."""
    p = _run(runner, ["git", "show", f"{ref}:{path}"], repo_dir)
    return p.stdout if p.returncode == 0 else None


def changed_files(repo_dir: Path, old_ref: str, new_ref: str, runner=subprocess.run) -> list[tuple[str, str]]:
    """[(status, path)] for every file that differs between the two refs. `status` is git's
    single-letter code (A/M/D; renames are disabled, so a rename appears as a D and an A -
    a documented simplification, see the CP3 report)."""
    p = _run(runner, ["git", "diff", "--no-renames", "--name-status", old_ref, new_ref], repo_dir)
    if p.returncode != 0:
        raise GitFetchError("DIFF_FAILED", (p.stderr or p.stdout).strip())
    out = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        out.append((status, path))
    return out


def unified_diff(repo_dir: Path, old_ref: str, new_ref: str, path: str, runner=subprocess.run,
                 context: int = 3) -> str:
    p = _run(runner, ["git", "diff", "--no-renames", f"-U{context}", old_ref, new_ref, "--", path], repo_dir)
    if p.returncode != 0:
        raise GitFetchError("DIFF_FAILED", (p.stderr or p.stdout).strip())
    return p.stdout


def resolve_tag(repo_dir: Path, tag: str, runner=subprocess.run) -> str | None:
    """The commit SHA a tag or ref points to, or None if it does not exist locally."""
    p = _run(runner, ["git", "rev-parse", f"{tag}^{{commit}}"], repo_dir)
    return p.stdout.strip() if p.returncode == 0 else None


def fetch_ref(host: str, owner: str, repo: str, ref: str, depth: int | None = None,
              cache_root: Path | None = None, runner=subprocess.run,
              timeout: float = DEFAULT_TIMEOUT_S, remote_url: str | None = None) -> tuple[Path, str | None]:
    """Fetch a tag, branch or commit `ref` (not necessarily a full SHA) into the cache clone.
    Returns (repo_dir, resolved_sha_or_None). Does not raise on a ref that does not exist
    (the caller decides what that means, e.g. TAG_NOT_FOUND); does raise GitFetchError on a
    transport failure. `remote_url` is as in `fetch_commit`."""
    repo_dir = repo_cache_dir(host, owner, repo, cache_root)
    _ensure_repo_initialised(repo_dir, host, owner, repo, runner, remote_url)
    args = ["git", "fetch", "origin", ref]
    if depth is not None:
        args.insert(2, f"--depth={depth}")
    fetch = _run(runner, args, repo_dir, timeout=timeout)
    if fetch.returncode != 0:
        return repo_dir, None
    return repo_dir, resolve_tag(repo_dir, "FETCH_HEAD", runner)
