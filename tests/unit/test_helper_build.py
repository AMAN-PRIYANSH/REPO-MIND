import subprocess
from pathlib import Path

import pytest

import vulntrace.methods.helper as h
from vulntrace.paths import REPO_ROOT


def make_helper_dir(tmp_path: Path) -> Path:
    d = tmp_path / "helper"
    d.mkdir()
    (d / "go.mod").write_text("module vulntrace/helper\n")
    (d / "go.sum").write_text("")
    (d / "main.go").write_text("package main\n")
    (d / "main_test.go").write_text("package main\n")
    return d


def fake_go(calls, build_rc=0):
    def runner(cmd, **kw):
        calls.append(cmd)
        assert kw["env"]["GOPROXY"] == "off" and kw["env"]["GOTOOLCHAIN"] == "local" and kw["env"]["CGO_ENABLED"] == "0"
        if cmd[1] == "version":
            return subprocess.CompletedProcess(cmd, 0, "go version go1.24.7 linux/amd64\n", "")
        if cmd[1] == "build":
            if build_rc == 0:
                Path(cmd[cmd.index("-o") + 1]).write_bytes(b"bin")
            return subprocess.CompletedProcess(cmd, build_rc, "", "missing module golang.org/x/tools" if build_rc else "")
        raise AssertionError(cmd)
    return runner


def test_source_hash_ignores_test_files_and_tracks_sources(tmp_path):
    d = make_helper_dir(tmp_path)
    before = h.source_hash(d)
    (d / "main_test.go").write_text("package main\n// changed\n")
    assert h.source_hash(d) == before
    (d / "main.go").write_text("package main\n// changed\n")
    assert h.source_hash(d) != before


def test_build_once_then_reuse_outside_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("VULNTRACE_CACHE", str(tmp_path / "cache"))
    d = make_helper_dir(tmp_path)
    calls = []
    first = h.ensure_helper(d, runner=fake_go(calls), which=lambda _: "/usr/bin/go")
    second = h.ensure_helper(d, runner=fake_go(calls), which=lambda _: "/usr/bin/go")
    assert first == second and first.is_file()
    assert [c[1] for c in calls].count("build") == 1
    assert REPO_ROOT not in first.resolve().parents
    (d / "main.go").write_text("package main\n// v2\n")
    third = h.ensure_helper(d, runner=fake_go(calls), which=lambda _: "/usr/bin/go")
    assert third != first and [c[1] for c in calls].count("build") == 2


def test_cache_inside_repository_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("VULNTRACE_CACHE", str(REPO_ROOT / "results" / "cache"))
    with pytest.raises(h.HelperError) as exc:
        h.ensure_helper(make_helper_dir(tmp_path), runner=fake_go([]), which=lambda _: "/usr/bin/go")
    assert exc.value.code == "HELPER_MISSING"


def test_build_failure_and_missing_go_are_helper_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("VULNTRACE_CACHE", str(tmp_path / "cache"))
    d = make_helper_dir(tmp_path)
    with pytest.raises(h.HelperError) as exc:
        h.ensure_helper(d, runner=fake_go([], build_rc=1), which=lambda _: "/usr/bin/go")
    assert exc.value.code == "HELPER_MISSING" and "helper fetch" in exc.value.message
    with pytest.raises(h.HelperError) as exc:
        h.ensure_helper(d, runner=fake_go([]), which=lambda _: None)
    assert exc.value.code == "HELPER_MISSING"


def test_windows_binary_name():
    assert h.binary_name("windows") == "vt-helper.exe"
    assert h.binary_name("linux") == "vt-helper"


def test_fetch_is_the_only_step_that_may_use_the_proxy(tmp_path, monkeypatch):
    monkeypatch.delenv("GOPROXY", raising=False)
    seen = {}

    def runner(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]
        return subprocess.CompletedProcess(cmd, 0, "", "")
    h.fetch_helper_modules(tmp_path, runner=runner)
    assert seen["cmd"] == ["go", "mod", "download"] and seen["env"].get("GOPROXY") != "off"
    monkeypatch.setenv("GOPROXY", "https://example.invalid")
    h.fetch_helper_modules(tmp_path, runner=runner)
    assert seen["env"]["GOPROXY"] == "https://example.invalid"
