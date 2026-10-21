"""Build and invoke the Go helper `vt-helper` (contract in INTERFACES_AND_CONTRACTS.md, section 2).

The binary is built into a cache directory outside the repository, keyed by a hash of the
helper sources and the Go version, and reused while the source is unchanged. Builds run
offline (`GOPROXY=off`); downloading the helper's own dependencies is a separate, explicit
step (`python -m vulntrace helper fetch`).
"""

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vulntrace.env import go_env
from vulntrace.paths import REPO_ROOT

HELPER_DIR = REPO_ROOT / "helper"
CONTRACT_VERSION = "1.0"
DEFAULT_TIMEOUT_S = 300.0

# Python-side error codes (the helper's own codes are passed through unchanged).
E_TIMEOUT = "TIMEOUT"
E_HELPER_MISSING = "HELPER_MISSING"
E_BAD_RESPONSE = "BAD_RESPONSE"
E_CONTRACT_MISMATCH = "CONTRACT_MISMATCH"

# Runner: (argv, timeout_s) -> (returncode, stdout, stderr); raises subprocess.TimeoutExpired.
Runner = Callable[[list[str], float], tuple[int, str, str]]


class HelperError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def binary_name(goos: str | None = None) -> str:
    goos = goos or ("windows" if os.name == "nt" else "")
    return "vt-helper.exe" if goos == "windows" else "vt-helper"


def source_hash(helper_dir: Path = HELPER_DIR) -> str:
    """Hash of everything that affects the binary: go.mod, go.sum and non-test Go files."""
    h = hashlib.sha256()
    files = sorted(p for p in Path(helper_dir).iterdir()
                   if p.name in ("go.mod", "go.sum") or (p.suffix == ".go" and not p.name.endswith("_test.go")))
    for p in files:
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def cache_root() -> Path:
    if os.environ.get("VULNTRACE_CACHE"):
        return Path(os.environ["VULNTRACE_CACHE"])
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "vulntrace"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "vulntrace"


def _go_version(runner=subprocess.run) -> str:
    p = runner(["go", "version"], capture_output=True, text=True, env=go_env(), timeout=60)
    if p.returncode != 0:
        raise HelperError(E_HELPER_MISSING, "`go version` failed: " + (p.stderr or p.stdout).strip())
    return p.stdout.strip()


def helper_binary_path(helper_dir: Path = HELPER_DIR, go_version: str = "") -> Path:
    key = hashlib.sha256((source_hash(helper_dir) + "\0" + go_version).encode()).hexdigest()[:20]
    return cache_root() / "helper" / key / binary_name()


def ensure_helper(helper_dir: Path = HELPER_DIR, runner=subprocess.run, which=shutil.which) -> Path:
    """Return the path of a built helper, building it if the cached one is missing."""
    if which("go") is None:
        raise HelperError(E_HELPER_MISSING, "go toolchain not found; cannot build vt-helper")
    if not (Path(helper_dir) / "go.mod").is_file():
        raise HelperError(E_HELPER_MISSING, f"helper sources not found in {helper_dir}")
    try:
        target = helper_binary_path(helper_dir, _go_version(runner))
    except (OSError, subprocess.SubprocessError) as exc:
        raise HelperError(E_HELPER_MISSING, f"cannot run go: {exc}") from exc
    if REPO_ROOT in target.resolve().parents:
        raise HelperError(E_HELPER_MISSING, f"refusing to build the helper inside the repository: {target}")
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp{os.getpid()}")
    try:
        b = runner(["go", "build", "-trimpath", "-o", str(tmp), "."], capture_output=True, text=True,
                   env=go_env(), cwd=helper_dir, timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HelperError(E_HELPER_MISSING, f"helper build did not run: {exc}") from exc
    if b.returncode != 0 or not tmp.is_file():
        msg = (b.stderr or b.stdout).strip()[:2000]
        raise HelperError(E_HELPER_MISSING, "helper build failed (GOPROXY=off; if modules are missing, "
                          "run `python -m vulntrace helper fetch` once, which needs network): " + msg)
    os.replace(tmp, target)
    return target


def fetch_helper_modules(helper_dir: Path = HELPER_DIR, runner=subprocess.run) -> subprocess.CompletedProcess:
    """Explicit, user-requested download of the helper's own Go dependencies (uses the network)."""
    env = go_env()
    if "GOPROXY" in os.environ:
        env["GOPROXY"] = os.environ["GOPROXY"]  # the user's own proxy setting
    else:
        env.pop("GOPROXY")
    return runner(["go", "mod", "download"], capture_output=True, text=True, env=env, cwd=helper_dir, timeout=600)


def default_runner(argv: list[str], timeout: float) -> tuple[int, str, str]:
    """Run the helper in its own process group and kill the whole group on timeout."""
    kwargs: dict[str, Any] = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True, "env": go_env()}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(argv, **kwargs)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.communicate()
        raise
    return proc.returncode, out, err


def run_helper(mode: str, request: dict[str, Any], binary: Path | None = None,
               timeout: float = DEFAULT_TIMEOUT_S, runner: Runner | None = None) -> dict[str, Any]:
    """Run one helper request and return the parsed, schema-valid response (ok may be false).

    Raises HelperError with TIMEOUT, HELPER_MISSING, BAD_RESPONSE or CONTRACT_MISMATCH.
    """
    from vulntrace.schemas import validation_errors

    errors = validation_errors("helper_request", request)
    if errors:
        raise ValueError("invalid helper request: " + "; ".join(errors))
    runner = runner or default_runner
    binary = binary or ensure_helper()
    with tempfile.TemporaryDirectory(prefix="vt_helper_req_") as tmp:
        req_path = Path(tmp) / "request.json"
        req_path.write_text(json.dumps(request), encoding="utf-8")
        try:
            rc, out, err = runner([str(binary), mode, "--request", str(req_path)], timeout)
        except subprocess.TimeoutExpired as exc:
            raise HelperError(E_TIMEOUT, f"helper {mode} exceeded {timeout:g} s and was killed") from exc
        except OSError as exc:
            raise HelperError(E_HELPER_MISSING, f"cannot run {binary}: {exc}") from exc
    if err:
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    return parse_response(out, mode, rc, err)


def parse_response(stdout: str, mode: str, returncode: int = 0, stderr: str = "") -> dict[str, Any]:
    from vulntrace.schemas import validation_errors

    try:
        resp = json.loads(stdout)
    except json.JSONDecodeError as exc:
        tail = stderr.strip()[-500:]
        raise HelperError(E_BAD_RESPONSE, f"helper stdout is not one JSON object (exit {returncode}): {exc}; "
                          f"stderr: {tail}") from exc
    if not isinstance(resp, dict):
        raise HelperError(E_BAD_RESPONSE, "helper response is not a JSON object")
    version = str(resp.get("contract_version", ""))
    if version.split(".")[0] != CONTRACT_VERSION.split(".")[0]:
        raise HelperError(E_CONTRACT_MISMATCH, f"helper contract_version {version!r}, expected {CONTRACT_VERSION}")
    errors = validation_errors("helper_response", resp)
    if errors:
        raise HelperError(E_BAD_RESPONSE, "helper response violates schema: " + "; ".join(errors[:5]))
    if resp["mode"] != mode:
        raise HelperError(E_BAD_RESPONSE, f"response mode {resp['mode']!r} for a {mode!r} request")
    return resp
