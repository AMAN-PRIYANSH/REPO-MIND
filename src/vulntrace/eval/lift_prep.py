"""Source checkouts and dependencies for the lifting evaluation (CP5b deliverable 4).

Loading a real module into the Go helper needs its source and its dependencies. This is the
explicit, network-using Python step the contract asks for (the helper itself never touches the
network): the vulnerable-side tree is read out of the cached git clone with `git archive`
(no checkout filters, hooks or scripts run), and `go mod tidy -e` fills the module cache with
the dependencies. Nothing from the analysed code is executed: no `go generate`, no tests, no
built binaries. Builds use `GOTOOLCHAIN=local` and `CGO_ENABLED=0`. A module that cannot be
prepared gets a status and the first error line; it is counted, never dropped.
"""

import io
import os
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from vulntrace.dataset import git_fetch

TIDY_TIMEOUT_S = 900.0
MAX_ARCHIVE_BYTES = 400 * 1024 * 1024

_MODULE_RE = re.compile(r"^\s*module\s+(\S+)", re.MULTILINE)

# statuses of prepare_case
READY, NO_SOURCE, NO_MODULE, PREP_FAILED = "READY", "NO_SOURCE", "NO_MODULE", "PREP_FAILED"


def prep_env(gomodcache: Path) -> dict[str, str]:
    """Environment for `go mod tidy`: local toolchain, no cgo, public module proxy, own module cache."""
    env = dict(os.environ)
    env.update(GOTOOLCHAIN="local", CGO_ENABLED="0", GOFLAGS="-mod=mod", GOMODCACHE=str(gomodcache),
               GOPROXY="https://proxy.golang.org", GOSUMDB="sum.golang.org", GOWORK="off")
    return env


def helper_env(gomodcache: Path) -> dict[str, str]:
    """The helper runs offline against the same module cache."""
    env = dict(os.environ)
    env.update(GOMODCACHE=str(gomodcache), GOWORK="off")
    return env


def first_line(text: str | None, limit: int = 300) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:limit]
    return ""


def extract_tree(repo_dir: Path, sha: str, dest: Path, runner=subprocess.run) -> str | None:
    """Unpack the tree of commit `sha` into `dest` (created). Returns None, or the first error line.
    `git archive` writes a tar of blobs only; members are filtered (no absolute paths, no links
    leaving the tree, no devices) before they are written."""
    p = runner(["git", "archive", "--format=tar", sha], cwd=repo_dir, capture_output=True, timeout=300)
    if p.returncode != 0:
        return "git archive: " + first_line(p.stderr.decode("utf-8", "replace") if isinstance(p.stderr, bytes) else p.stderr)
    if len(p.stdout) > MAX_ARCHIVE_BYTES:
        return f"git archive: tree larger than {MAX_ARCHIVE_BYTES // 1024 // 1024} MB"
    dest.mkdir(parents=True, exist_ok=True)

    def safe(member, path):
        """The `data` filter, but an unsafe member (absolute or escaping link, path outside the tree) is
        left out instead of aborting the whole unpack: one stray symlink in a test directory must not
        cost the case."""
        try:
            return tarfile.data_filter(member, path)
        except tarfile.FilterError:
            return None

    try:
        with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
            tf.extractall(dest, filter=safe)
    except (tarfile.TarError, OSError) as exc:
        return f"extract: {first_line(str(exc))}"
    return None


def find_module_root(tree: Path, module_path: str) -> Path | None:
    """The directory (inside `tree`) whose go.mod declares `module_path`. Vendored and testdata
    go.mod files are ignored; the shallowest match wins."""
    best: tuple[int, Path] | None = None
    for gomod in tree.rglob("go.mod"):
        rel = gomod.relative_to(tree).parts
        if any(part in ("vendor", "testdata", "node_modules") or part.startswith(".") for part in rel[:-1]):
            continue
        try:
            text = gomod.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _MODULE_RE.search(text)
        if m and m.group(1).strip('"') == module_path and (best is None or len(rel) < best[0]):
            best = (len(rel), gomod.parent)
    return best[1] if best else None


_VERSION_SEGMENT = re.compile(r"^v[0-9]+$")


def synthesize_go_mod(tree: Path, module_path: str, repo_prefix: str) -> Path | None:
    """For a tree that predates Go modules: write `go.mod` declaring the vulndb module path, in the
    directory the path implies inside the repository (`host/owner/repo[/subdir][/vN]`). Returns the
    module directory, or None if the path does not belong to this repository (for example a
    `gopkg.in/...` import path) or the directory does not exist. This only creates a text file; the
    result is flagged `synthesized_go_mod` and reported separately from modules that had a go.mod."""
    if not (module_path == repo_prefix or module_path.startswith(repo_prefix + "/")):
        return None
    parts = [p for p in module_path[len(repo_prefix):].split("/") if p]
    if parts and _VERSION_SEGMENT.match(parts[-1]):
        parts = parts[:-1]
    directory = tree.joinpath(*parts)
    try:
        directory.resolve().relative_to(tree.resolve())
    except ValueError:
        return None
    if not directory.is_dir():
        return None
    (directory / "go.mod").write_text(f"module {module_path}\n\ngo 1.16\n", encoding="utf-8")
    return directory


def drop_vendor(module_dir: Path) -> bool:
    """Set a vendored tree aside (rename `vendor` to `vendor.unused`) so modules come from the module cache.
    Used when the tree's own vendor directory cannot match its go.mod: a go.mod we synthesised, or an
    'inconsistent vendoring' load error. The analysed dependencies are then the versions go.mod names."""
    v = module_dir / "vendor"
    if v.is_dir():
        v.rename(module_dir / "vendor.unused")
        return True
    return False


def tidy(module_dir: Path, gomodcache: Path, runner=subprocess.run, timeout: float = TIDY_TIMEOUT_S) -> str | None:
    """`go mod tidy -e` in the module directory (downloads dependencies; executes no analysed code).
    Returns None on success, otherwise the first error line (a partial tidy under -e is still success:
    the helper's own load reports what is really missing)."""
    gomodcache.mkdir(parents=True, exist_ok=True)
    try:
        p = runner(["go", "mod", "tidy", "-e"], cwd=module_dir, capture_output=True, text=True,
                   env=prep_env(gomodcache), timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"go mod tidy timed out after {timeout:g}s"
    except OSError as exc:
        return f"go mod tidy could not run: {exc}"
    if p.returncode != 0 and (module_dir / "go.mod").is_file() is False:
        return first_line(p.stderr or p.stdout)
    # With -e most failures only print errors but exit 0; a non-zero exit with an unusable go.mod is fatal.
    if p.returncode != 0:
        err = first_line(p.stderr or p.stdout)
        if "requires go >=" in (p.stderr or "") or "toolchain" in (p.stderr or "").lower():
            return err
    return None


def prepare_case(repo_dir: Path, parent_sha: str, module_path: str, work_dir: Path, gomodcache: Path,
                 runner=subprocess.run, repo_prefix: str | None = None) -> dict[str, Any]:
    """Unpack the vulnerable-side tree and prepare the module. Returns
    {status, module_dir, module_rel, reason}; module_rel is the module root relative to the repository."""
    tree = work_dir / "tree"
    if not tree.exists():
        err = extract_tree(repo_dir, parent_sha, tree, runner)
        if err:
            return {"status": NO_SOURCE, "module_dir": None, "module_rel": None, "reason": err}
    root = find_module_root(tree, module_path)
    synthesized = False
    if root is None and repo_prefix:
        root = synthesize_go_mod(tree, module_path, repo_prefix)
        synthesized = root is not None
    if root is None:
        return {"status": NO_MODULE, "module_dir": None, "module_rel": None, "synthesized_go_mod": False,
                "reason": f"no go.mod declaring module {module_path} in the vulnerable-side tree"}
    # A vendored tree is used as it is: `go mod tidy` would change go.mod and make vendor/modules.txt inconsistent.
    # A go.mod we invented cannot match any vendor directory, so there the vendor directory is set aside.
    vendor_dropped = drop_vendor(root) if synthesized else False
    vendored = (root / "vendor" / "modules.txt").is_file()
    err = None if vendored else tidy(root, gomodcache, runner)
    rel = root.relative_to(tree).as_posix()
    base = {"module_dir": str(root), "module_rel": "" if rel == "." else rel, "synthesized_go_mod": synthesized,
            "vendored": vendored, "vendor_dropped": vendor_dropped}
    if err:
        return {"status": PREP_FAILED, "reason": err, **base}
    return {"status": READY, "reason": None, **base}
