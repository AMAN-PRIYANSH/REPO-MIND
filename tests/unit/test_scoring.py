import os
import subprocess
from pathlib import Path

import pytest

from vulntrace.eval.fixture_score import (
    AGREE, ERROR, FALSE_NOT_REACHABLE, FALSE_REACHABLE, outcome, predict, strip_timing,
)
from vulntrace.methods.linker import run_linker_method


def test_outcome_table():
    assert outcome("REACHABLE", "REACHABLE") == AGREE
    assert outcome("NOT_REACHABLE", "NOT_REACHABLE") == AGREE
    assert outcome("REACHABLE", "NOT_REACHABLE") == FALSE_NOT_REACHABLE
    assert outcome("NOT_REACHABLE", "REACHABLE") == FALSE_REACHABLE
    assert outcome("REACHABLE", "ERROR") == ERROR


def test_predict_case_level():
    assert predict([{"result": "ABSENT"}, {"result": "PRESENT"}]) == "REACHABLE"
    assert predict([{"result": "ABSENT"}, {"result": "ERROR"}]) == "ERROR"
    assert predict([{"result": "ABSENT"}]) == "NOT_REACHABLE"


def test_strip_timing():
    assert strip_timing({"a": [{"duration_ms": 3, "b": 1}], "duration_ms": 9}) == {"a": [{"b": 1}]}


def make_runner(goos="linux", nm_text="", build_rc=0, created=None):
    def runner(cmd, **kw):
        assert kw["env"]["GOPROXY"] == "off" and kw["env"]["GOTOOLCHAIN"] == "local"
        assert "GOFLAGS" not in kw["env"]
        if cmd[1] == "version":
            return subprocess.CompletedProcess(cmd, 0, "go version go1.24.7 linux/amd64\n", "")
        if cmd[1] == "env":
            return subprocess.CompletedProcess(cmd, 0, f"{goos}\namd64\n", "")
        if cmd[1] == "build":
            out = cmd[cmd.index("-o") + 1]
            if build_rc == 0:
                Path(out).write_bytes(b"x")
                if created is not None:
                    created.append(out)
            return subprocess.CompletedProcess(cmd, build_rc, "", "boom" if build_rc else "")
        if cmd[1] == "tool":
            return subprocess.CompletedProcess(cmd, 0, nm_text, "")
        raise AssertionError(cmd)
    return runner


T = [{"package": "p/vulnlib", "symbol": "Parse"}]


def test_present_and_absent_with_fake_go():
    r = run_linker_method(Path("."), "p/cmd/a", T, runner=make_runner(nm_text="  1 T p/vulnlib.Parse\n"))
    assert r[0]["result"] == "PRESENT"
    assert r[0]["details"]["matched_binary_symbols"] == ["p/vulnlib.Parse"]
    assert r[0]["details"]["build_flags"] == ["-gcflags=all=-l"]
    r = run_linker_method(Path("."), "p/cmd/a", T, runner=make_runner(nm_text="  1 T p/vulnlib.Safe\n"))
    assert r[0]["result"] == "ABSENT"


def test_build_failure_gives_error():
    r = run_linker_method(Path("."), "p/cmd/a", T, runner=make_runner(build_rc=1))
    assert r[0]["result"] == "ERROR" and r[0]["error"]["code"] == "BUILD_FAILED"


def test_generic_symbol_is_error_without_building():
    def runner(*a, **k):
        raise AssertionError("must not build for unsupported symbols")

    r = run_linker_method(Path("."), "p/cmd/a", [{"package": "p", "symbol": "Map[T]"}], runner=runner)
    assert r[0]["result"] == "ERROR" and r[0]["error"]["code"] == "UNSUPPORTED_SYMBOL_FORM"


@pytest.mark.parametrize("goos,suffix", [("linux", ""), ("windows", ".exe")])
def test_temporary_binary_deleted(goos, suffix):
    created = []
    run_linker_method(Path("."), "p/cmd/a", T, runner=make_runner(goos=goos, created=created))
    assert len(created) == 1 and created[0].endswith(suffix) and (suffix or not created[0].endswith(".exe"))
    assert not os.path.exists(created[0])


def test_temporary_binary_deleted_when_nm_fails():
    created = []
    base = make_runner(created=created)

    def runner(cmd, **kw):
        if cmd[1] == "tool":
            return subprocess.CompletedProcess(cmd, 1, "", "nm broke")
        return base(cmd, **kw)

    r = run_linker_method(Path("."), "p/cmd/a", T, runner=runner)
    assert r[0]["error"]["code"] == "NM_FAILED"
    assert not os.path.exists(created[0])


def test_go_missing_gives_error():
    def runner(*a, **k):
        raise FileNotFoundError("go")

    r = run_linker_method(Path("."), "p/cmd/a", T, runner=runner)
    assert r[0]["error"]["code"] == "GO_NOT_FOUND"
