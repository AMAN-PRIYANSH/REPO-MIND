"""golang/vulndb snapshot: pin config, cache location, fetch (CP3 deliverable 1).

The snapshot (``data/reports/*.yaml`` only) is fetched into a cache directory
outside this repository and is never committed; only the pinned commit,
counts and computed results are (see ``vulndb.json`` and the CP3 report for
the licence finding). Fetching is a deliberate, explicit, network-using step
(``python -m vulntrace dataset fetch``), mirroring ``helper fetch``.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from vulntrace.paths import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "vulndb.json"
DEFAULT_TIMEOUT_S = 600.0


class VulndbError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pinned_commit(config: dict[str, Any] | None = None) -> str:
    return (config or load_config())["commit"]


def repo_url(config: dict[str, Any] | None = None) -> str:
    return (config or load_config())["repo_url"]


def default_cache_dir() -> Path:
    if os.environ.get("VULNTRACE_CACHE"):
        return Path(os.environ["VULNTRACE_CACHE"]) / "vulndb-src"
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "vulntrace" / "vulndb-src"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "vulntrace" / "vulndb-src"


def reports_dir(cache_dir: Path | None = None) -> Path:
    return (cache_dir or default_cache_dir()) / "data" / "reports"


def _run(runner, args: list[str], cwd: Path, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return runner(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def current_head(cache_dir: Path, runner=subprocess.run) -> str | None:
    if not (cache_dir / ".git").is_dir():
        return None
    p = _run(runner, ["git", "rev-parse", "HEAD"], cwd=cache_dir)
    return p.stdout.strip() if p.returncode == 0 else None


def is_up_to_date(cache_dir: Path | None = None, config: dict[str, Any] | None = None, runner=subprocess.run) -> bool:
    cache_dir = cache_dir or default_cache_dir()
    return current_head(cache_dir, runner) == pinned_commit(config)


def ensure_vulndb_snapshot(cache_dir: Path | None = None, config: dict[str, Any] | None = None,
                           runner=subprocess.run, timeout: float = DEFAULT_TIMEOUT_S) -> Path:
    """Return the cache directory holding ``data/reports/`` at the pinned commit, fetching
    it (network) if it is not already there. Raises VulndbError on any failure; never
    silently falls back to a different commit."""
    config = config or load_config()
    cache_dir = cache_dir or default_cache_dir()
    sha = pinned_commit(config)
    if current_head(cache_dir, runner) == sha:
        if not reports_dir(cache_dir).is_dir():
            raise VulndbError("EMPTY_SNAPSHOT", f"{cache_dir} is at the pinned commit but has no data/reports/")
        return cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not (cache_dir / ".git").is_dir():
        init = _run(runner, ["git", "init", "-q"], cwd=cache_dir)
        if init.returncode != 0:
            raise VulndbError("GIT_FAILED", "git init: " + (init.stderr or init.stdout).strip())
        remote = _run(runner, ["git", "remote", "add", "origin", repo_url(config)], cwd=cache_dir)
        if remote.returncode != 0:
            raise VulndbError("GIT_FAILED", "git remote add: " + (remote.stderr or remote.stdout).strip())
    fetch = _run(runner, ["git", "fetch", "--depth", "1", "origin", sha], cwd=cache_dir, timeout=timeout)
    if fetch.returncode != 0:
        raise VulndbError("FETCH_FAILED", f"git fetch of pinned commit {sha}: " + (fetch.stderr or fetch.stdout).strip())
    for args in (["git", "sparse-checkout", "init", "--cone"], ["git", "sparse-checkout", "set", "data/reports"]):
        p = _run(runner, args, cwd=cache_dir)
        if p.returncode != 0:
            raise VulndbError("GIT_FAILED", " ".join(args) + ": " + (p.stderr or p.stdout).strip())
    checkout = _run(runner, ["git", "checkout", "-q", "FETCH_HEAD"], cwd=cache_dir)
    if checkout.returncode != 0:
        raise VulndbError("GIT_FAILED", "git checkout: " + (checkout.stderr or checkout.stdout).strip())
    head = current_head(cache_dir, runner)
    if head != sha:
        raise VulndbError("PIN_MISMATCH", f"checked out {head!r}, expected the pinned commit {sha!r}")
    if not reports_dir(cache_dir).is_dir():
        raise VulndbError("EMPTY_SNAPSHOT", f"{cache_dir} has no data/reports/ after checkout")
    return cache_dir


def iter_report_paths(cache_dir: Path | None = None) -> list[Path]:
    """Every report YAML file, sorted (so dataset builds are deterministic)."""
    return sorted(reports_dir(cache_dir).glob("GO-*.yaml"))
