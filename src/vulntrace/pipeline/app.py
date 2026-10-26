"""Facts about the application being triaged: its module path, its git commit, and its main
packages. Only `go list` and read-only git commands run here; nothing from the app is built or
executed (CLAUDE.md section 8). Every `go` command uses `vulntrace.env.go_env()`
(GOTOOLCHAIN=local, CGO_ENABLED=0, GOPROXY=off)."""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vulntrace.env import go_env

GO_LIST_TIMEOUT_S = 300.0
DEFAULT_MAX_MAINS = 10

_MODULE_RE = re.compile(r"^\s*module\s+(\S+)", re.MULTILINE)


@dataclass
class AppInfo:
    path: str                      # as given, forward slashes
    module_dir: Path
    module: str | None
    commit: str | None
    commit_source: str             # GIT_HEAD, EVIDENCE, USER, NONE
    dirty: bool | None
    git_prefix: str | None         # the app directory relative to its git work tree root ("" at the root)
    mains: list[str] = field(default_factory=list)            # analysed main packages (import paths)
    mains_skipped: list[str] = field(default_factory=list)    # found but over the limit
    list_error: str | None = None  # `go list` could not list the module at all
    package_errors: list[str] = field(default_factory=list)   # first errors of packages that did not list cleanly

    def target_app(self) -> dict[str, Any]:
        return {"path": self.path, "module": self.module, "commit": self.commit,
                "commit_source": self.commit_source, "dirty": self.dirty}


def read_module_path(module_dir: Path) -> str | None:
    try:
        text = (Path(module_dir) / "go.mod").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _MODULE_RE.search(text)
    return m.group(1).strip('"') if m else None


def _git(args: list[str], cwd: Path, runner=subprocess.run) -> str | None:
    try:
        p = runner(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def git_state(module_dir: Path, runner=subprocess.run) -> tuple[str | None, bool | None, str | None]:
    """(HEAD commit, dirty, prefix of the directory inside the work tree), or Nones outside git.
    `dirty` covers only the app directory (tracked changes and untracked files)."""
    head = _git(["rev-parse", "HEAD"], module_dir, runner)
    if head is None:
        return None, None, None
    prefix = _git(["rev-parse", "--show-prefix"], module_dir, runner)
    status = _git(["status", "--porcelain", "--", "."], module_dir, runner)
    return head, (bool(status) if status is not None else None), (prefix or "").rstrip("/")


def list_packages(module_dir: Path, runner=subprocess.run, timeout: float = GO_LIST_TIMEOUT_S,
                  tags: list[str] | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """`go list -e -json ./...` in the module: (packages, fatal error line or None)."""
    cmd = ["go", "list", "-e", "-json=ImportPath,Name,Error,DepsErrors,Dir"]
    if tags:
        cmd.append("-tags=" + ",".join(tags))
    cmd.append("./...")
    try:
        p = runner(cmd, cwd=module_dir, capture_output=True, text=True, env=go_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        return [], f"go list timed out after {timeout:g}s"
    except OSError as exc:
        return [], f"go list could not run: {exc}"
    pkgs = []
    dec = json.JSONDecoder()
    text, i = p.stdout, 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        try:
            obj, i = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            return pkgs, "go list printed malformed JSON"
        pkgs.append(obj)
    if p.returncode != 0 and not pkgs:
        return [], _first_line(p.stderr or p.stdout) or f"go list exited {p.returncode}"
    return pkgs, None


def _first_line(text: str | None, limit: int = 300) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


def find_mains(pkgs: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(main package import paths that listed without errors, first error lines of the others)."""
    mains, errors = [], []
    for p in pkgs:
        err = (p.get("Error") or {}).get("Err")
        if err:
            errors.append(f"{p.get('ImportPath', '?')}: {_first_line(err)}")
            continue
        if p.get("Name") == "main":
            mains.append(p["ImportPath"])
    return sorted(mains), errors


def inspect_app(app: Path, *, mains: list[str] | None = None, max_mains: int = DEFAULT_MAX_MAINS,
                commit: str | None = None, runner=subprocess.run, go_runner=subprocess.run,
                tags: list[str] | None = None) -> AppInfo:
    """Everything the pipeline needs to know about the app before analysis. `mains` restricts
    the analysis to the given main packages (relative `./cmd/x` or import paths); otherwise every
    main package of the module is found, and only the first `max_mains` (sorted) are analysed;
    the rest are recorded as skipped (coverage incomplete). A `commit` given by the caller (for
    example the commit a tree was extracted from) replaces the git HEAD."""
    module_dir = Path(app).resolve()
    info = AppInfo(path=Path(app).as_posix(), module_dir=module_dir, module=read_module_path(module_dir),
                   commit=None, commit_source="NONE", dirty=None, git_prefix=None)
    head, dirty, prefix = git_state(module_dir, runner)
    if commit:
        info.commit, info.commit_source, info.dirty = commit, "EVIDENCE", None
    elif head:
        info.commit, info.commit_source, info.dirty = head, "GIT_HEAD", dirty
    info.git_prefix = prefix if head else None
    if info.module is None:
        info.list_error = "no go.mod with a module line in the app directory"
        return info
    pkgs, err = list_packages(module_dir, go_runner, tags=tags)
    if err:
        info.list_error = err
        return info
    found, info.package_errors = find_mains(pkgs)
    if mains:
        wanted = [_to_import_path(m, info.module) for m in mains]
        info.mains = [m for m in wanted if m in found]
        missing = [m for m in wanted if m not in found]
        info.package_errors += [f"{m}: requested main package not found or does not list cleanly" for m in missing]
    else:
        info.mains, info.mains_skipped = found[:max_mains], found[max_mains:]
    return info


def _to_import_path(main: str, module: str) -> str:
    m = main.replace("\\", "/").strip()
    if m in (".", "./"):
        return module
    if m.startswith("./"):
        return module + "/" + m[2:].strip("/")
    return m.strip("/")
