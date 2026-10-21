"""Run environment recorded in every score report, so results documents can be generated from the file alone."""

import platform
import shutil
import subprocess
from typing import Any

from vulntrace.paths import REPO_ROOT


def _out(cmd: list[str]) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def run_info(argv: list[str]) -> dict[str, Any]:
    commit = _out(["git", "rev-parse", "--short", "HEAD"])
    dirty = _out(["git", "status", "--porcelain"])
    return {
        "command": "python -m vulntrace " + " ".join(argv),
        "os": platform.platform(),
        "python": platform.python_version(),
        "go": _out(["go", "version"]),
        "repo_commit": commit,
        "repo_dirty": bool(dirty) if dirty is not None else None,
    }
