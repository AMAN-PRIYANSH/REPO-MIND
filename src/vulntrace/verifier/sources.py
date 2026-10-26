"""Reading the files a verdict cites, at the analysed version.

Module-relative files are read from git at the recorded commit when the app is a clean git work
tree at that commit (`git show <commit>:<prefix>/<file>`); otherwise from the analysed tree on
disk (an extracted tree is the content of the commit it was extracted from; a dirty work tree is
what was analysed, and the verdict says so). `$GOROOT/...` files come from the local Go
installation and absolute paths (module cache) from disk; both are versioned by the toolchain
and go.sum, which the verdict records.
"""

import subprocess
from pathlib import Path

from vulntrace.env import go_env


class FileSource:
    def __init__(self, module_dir: Path, commit: str | None = None, git_prefix: str | None = None,
                 use_git: bool = False, goroot: str | None = None, runner=subprocess.run):
        self.module_dir = Path(module_dir)
        self.commit, self.git_prefix, self.use_git = commit, git_prefix, use_git and bool(commit)
        self._goroot = goroot
        self.runner = runner
        self._cache: dict[str, str | None] = {}

    @property
    def description(self) -> str:
        if self.use_git:
            return f"git show {self.commit}"
        return "analysed tree on disk"

    def goroot(self) -> str | None:
        if self._goroot is None:
            try:
                p = self.runner(["go", "env", "GOROOT"], capture_output=True, text=True, env=go_env(), timeout=60)
                self._goroot = p.stdout.strip() if p.returncode == 0 else ""
            except (OSError, subprocess.SubprocessError):
                self._goroot = ""
        return self._goroot or None

    def disk_path(self, file: str) -> Path | None:
        """Where `file` (a CallPath file form) lives on disk, or None."""
        if file.startswith("$GOROOT/"):
            root = self.goroot()
            return Path(root) / file[len("$GOROOT/"):] if root else None
        p = Path(file)
        return p if p.is_absolute() else self.module_dir / file

    def read(self, file: str) -> str | None:
        if file in self._cache:
            return self._cache[file]
        text = None
        if not file.startswith("$GOROOT/") and not Path(file).is_absolute() and self.use_git:
            spec = f"{self.commit}:{(self.git_prefix + '/' if self.git_prefix else '')}{file}"
            try:
                p = self.runner(["git", "show", spec], cwd=self.module_dir, capture_output=True, text=True, timeout=60)
                text = p.stdout if p.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                text = None
        else:
            path = self.disk_path(file)
            if path is not None:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = None
        self._cache[file] = text
        return text
