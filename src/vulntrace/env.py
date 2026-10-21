"""`doctor`: report the toolchain. Never installs or downloads anything."""

import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

EXIT_OK = 0
EXIT_MISSING_PREREQUISITE = 3

MIN_PYTHON = (3, 11)


def go_env() -> dict[str, str]:
    """Environment for every `go` invocation made by this project."""
    env = dict(os.environ)
    env["GOTOOLCHAIN"] = "local"
    env["CGO_ENABLED"] = "0"
    env["GOPROXY"] = "off"
    env.pop("GOFLAGS", None)
    return env


Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class DoctorReport:
    lines: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return EXIT_MISSING_PREREQUISITE if self.missing else EXIT_OK


def _run(runner: Runner, cmd: list[str]) -> subprocess.CompletedProcess:
    return runner(cmd, capture_output=True, text=True, env=go_env(), timeout=60)


def run_doctor(
    which: Callable[[str], str | None] = shutil.which,
    runner: Runner = subprocess.run,
    python_version: tuple[int, int, int] | None = None,
) -> DoctorReport:
    rep = DoctorReport()
    pv = python_version or sys.version_info[:3]
    pv_text = ".".join(str(x) for x in pv)
    if tuple(pv[:2]) >= MIN_PYTHON:
        rep.lines.append(f"python: {pv_text}")
    else:
        rep.lines.append(f"python: {pv_text} (need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
        rep.missing.append("python>=3.11")
    rep.lines.append(f"platform: {platform.system()} {platform.machine()}")

    if which("go") is None:
        rep.lines.append("go: not found")
        rep.lines.append("go env GOOS GOARCH: unavailable")
        rep.lines.append("go tool nm: unavailable")
        rep.missing.append("go")
    else:
        try:
            ver = _run(runner, ["go", "version"])
            rep.lines.append(f"go: {ver.stdout.strip() or ver.stderr.strip() or 'unknown'}")
            if ver.returncode != 0:
                rep.missing.append("go")
            e = _run(runner, ["go", "env", "GOOS", "GOARCH"])
            goos_goarch = e.stdout.split()
            rep.lines.append(f"go env GOOS GOARCH: {' '.join(goos_goarch) or 'unavailable'}")
            nm = _run(runner, ["go", "tool", "nm", "-h"])
            nm_ok = "usage: go tool nm" in (nm.stdout + nm.stderr)
            rep.lines.append(f"go tool nm: {'runs' if nm_ok else 'does not run'}")
            if not nm_ok:
                rep.missing.append("go tool nm")
        except (OSError, subprocess.SubprocessError) as exc:
            rep.lines.append(f"go: found but failed to run ({exc})")
            rep.missing.append("go")

    docker = which("docker")
    rep.lines.append(f"docker: {'present' if docker else 'not found'} (informational in CP1)")
    rep.lines.append(f"git: {'present' if which('git') else 'not found'}")
    if rep.missing:
        rep.lines.append("missing prerequisites: " + ", ".join(rep.missing))
    else:
        rep.lines.append("all CP1 prerequisites present")
    return rep
