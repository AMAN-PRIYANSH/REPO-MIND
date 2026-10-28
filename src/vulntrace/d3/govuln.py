"""Optional reference comparison with govulncheck (CP7b deliverable 3). NOT truth.

govulncheck (golang.org/x/vuln, built from the Go module proxy) runs in source mode on the same
application tree, main packages and module cache as the triage run, offline (`GOPROXY=off`), with
a vulnerability database made from the **same pinned vulndb snapshot** (its `data/osv/*.json`, a
flat directory of `<ID>.json` files, which govulncheck indexes itself). Source mode type-checks
and builds a call graph; nothing of the application is executed.

govulncheck answers with findings at three levels: symbol (a vulnerable symbol is called),
package (imported, no vulnerable symbol called) and module (required, package not imported). For
one advisory: `REACHABLE` if any finding is at symbol level, `NOT_REACHABLE` if findings exist
only at package or module level, `NOT_AFFECTED` if govulncheck reports nothing for it, `ERROR`
if govulncheck failed. Its symbols are the advisory's exported symbol list, ours are the fix's
changed functions (Mode 1), so the two answer related but different questions; disagreements are
listed, never resolved by assumption.
"""

import io
import json
import os
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from vulntrace.dataset import vulndb

GOVULNCHECK_MODULE = "golang.org/x/vuln"
GOVULNCHECK_VERSION = "v1.9.0"     # released 2026-10-11, at least two weeks before it was first used
RUN_TIMEOUT_S = 1800.0

REACHABLE, NOT_REACHABLE, NOT_AFFECTED, ERROR = "REACHABLE", "NOT_REACHABLE", "NOT_AFFECTED", "ERROR"
LEVEL_SYMBOL, LEVEL_PACKAGE, LEVEL_MODULE, LEVEL_NONE = "SYMBOL", "PACKAGE", "MODULE", "NONE"


def tool_env(gomodcache: Path, gobin: Path) -> dict[str, str]:
    """Building the tool itself (its own dependencies, from the proxy)."""
    env = dict(os.environ)
    env.update(GOTOOLCHAIN="local", CGO_ENABLED="0", GOBIN=str(gobin), GOMODCACHE=str(gomodcache),
               GOPROXY="https://proxy.golang.org", GOSUMDB="sum.golang.org", GOFLAGS="", GOWORK="off")
    return env


def run_env(gomodcache: Path) -> dict[str, str]:
    """Analysing an application: offline, read-only go.mod, no cgo, local toolchain."""
    env = dict(os.environ)
    env.update(GOTOOLCHAIN="local", CGO_ENABLED="0", GOMODCACHE=str(gomodcache), GOPROXY="off", GOSUMDB="off",
               GOFLAGS="-mod=readonly", GOWORK="off")
    return env


def ensure_govulncheck(gobin: Path, gomodcache: Path, runner=subprocess.run) -> tuple[Path | None, str | None]:
    exe = gobin / "govulncheck"
    if exe.is_file():
        return exe, None
    gobin.mkdir(parents=True, exist_ok=True)
    p = runner(["go", "install", f"{GOVULNCHECK_MODULE}/cmd/govulncheck@{GOVULNCHECK_VERSION}"],
               capture_output=True, text=True, env=tool_env(gomodcache, gobin), timeout=900)
    if p.returncode != 0 or not exe.is_file():
        return None, (p.stderr or p.stdout).strip().splitlines()[-1:] or ["go install failed"]
    return exe, None


def ensure_db(db_dir: Path, vulndb_cache: Path | None = None, runner=subprocess.run) -> tuple[Path | None, str | None]:
    """A flat directory of the pinned snapshot's OSV files (`git archive` of data/osv)."""
    marker = db_dir / ".vulndb_commit"
    sha = vulndb.pinned_commit()
    if marker.is_file() and marker.read_text().strip() == sha:
        return db_dir, None
    src = vulndb_cache or vulndb.default_cache_dir()
    p = runner(["git", "archive", "--format=tar", sha, "data/osv"], cwd=src, capture_output=True, timeout=600)
    if p.returncode != 0:
        return None, "git archive data/osv: " + (p.stderr.decode("utf-8", "replace") if isinstance(p.stderr, bytes)
                                                 else str(p.stderr)).strip()[:300]
    db_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
        for m in tf.getmembers():
            name = Path(m.name).name
            if m.isfile() and name.startswith("GO-") and name.endswith(".json"):
                (db_dir / name).write_bytes(tf.extractfile(m).read())
                n += 1
    marker.write_text(sha + "\n")
    return (db_dir, None) if n else (None, "no OSV files in data/osv")


def parse_stream(text: str) -> list[dict[str, Any]]:
    """govulncheck -format json prints a stream of JSON objects (not one array)."""
    out, dec, i = [], json.JSONDecoder(), 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        obj, i = dec.raw_decode(text, i)
        out.append(obj)
    return out


def run_govulncheck(exe: Path, db_dir: Path, module_dir: Path, mains: list[str], gomodcache: Path,
                    runner=subprocess.run, timeout: float = RUN_TIMEOUT_S) -> dict[str, Any]:
    """{"ok", "error", "messages", "go_version", "scanner"}; the main packages are the roots."""
    cmd = [str(exe), "-db", db_dir.resolve().as_uri(), "-format", "json", "-mode", "source", "-scan", "symbol",
           "-C", str(module_dir), *mains]
    try:
        p = runner(cmd, capture_output=True, text=True, env=run_env(gomodcache), timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout:g}s", "messages": []}
    try:
        msgs = parse_stream(p.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"unparseable output: {exc}", "messages": []}
    cfg = next((m["config"] for m in msgs if "config" in m), {})
    # exit 3 means "vulnerabilities found"; 0 none; anything else is a failure
    ok = p.returncode in (0, 3) and bool(cfg)
    err = None if ok else ((p.stderr or "").strip().splitlines() or [f"exit {p.returncode}"])[-1][:300]
    return {"ok": ok, "error": err, "messages": msgs, "go_version": cfg.get("go_version"),
            "scanner": f"{cfg.get('scanner_name')}@{cfg.get('scanner_version')}", "db": cfg.get("db"),
            "exit_code": p.returncode}


def _level(finding: dict[str, Any]) -> str:
    trace = finding.get("trace") or []
    if not trace:
        return LEVEL_NONE
    if trace[0].get("function"):
        return LEVEL_SYMBOL
    if trace[0].get("package"):
        return LEVEL_PACKAGE
    return LEVEL_MODULE


_RANK = {LEVEL_NONE: 0, LEVEL_MODULE: 1, LEVEL_PACKAGE: 2, LEVEL_SYMBOL: 3}


def frame_text(fr: dict[str, Any]) -> str:
    fn = fr.get("function") or ""
    if fr.get("receiver"):
        fn = fr["receiver"].lstrip("*") + "." + fn
    name = f"{fr.get('package') or fr.get('module')}.{fn}" if fn else (fr.get("package") or fr.get("module") or "?")
    pos = fr.get("position") or {}
    return name + (f" ({pos.get('filename')}:{pos.get('line')})" if pos.get("filename") else "")


def advisory_result(run: dict[str, Any], advisory_id: str) -> dict[str, Any]:
    """govulncheck's answer for one advisory (see the module docstring for the mapping)."""
    if not run.get("ok"):
        return {"verdict": ERROR, "level": None, "error": run.get("error"), "trace": None, "symbols": []}
    fs = [m["finding"] for m in run["messages"] if "finding" in m and m["finding"].get("osv") == advisory_id]
    if not fs:
        return {"verdict": NOT_AFFECTED, "level": LEVEL_NONE, "error": None, "trace": None, "symbols": []}
    best = max(fs, key=lambda f: _RANK[_level(f)])
    level = _level(best)
    syms = sorted({frame_text({k: v for k, v in f["trace"][0].items() if k != "position"})
                   for f in fs if _level(f) == LEVEL_SYMBOL})
    return {"verdict": REACHABLE if level == LEVEL_SYMBOL else NOT_REACHABLE, "level": level, "error": None,
            "fixed_version": best.get("fixed_version"),
            "trace": [frame_text(fr) for fr in best.get("trace") or []] if level == LEVEL_SYMBOL else None,
            "symbols": syms}


def agreement(ours: str | None, theirs: str) -> str:
    """AGREE / DISAGREE / NOT_COMPARABLE (either side abstained, errored or did not run). A
    govulncheck NOT_AFFECTED (no finding at all although selection checked the version is in the
    range) is not read as NOT_REACHABLE: it is a discrepancy of its own, listed, not compared."""
    if ours not in (REACHABLE, NOT_REACHABLE):
        return "NOT_COMPARABLE"
    if theirs not in (REACHABLE, NOT_REACHABLE):
        return "NOT_COMPARABLE"
    return "AGREE" if ours == theirs else "DISAGREE"
