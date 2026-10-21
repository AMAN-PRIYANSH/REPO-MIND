import subprocess

from vulntrace.env import EXIT_MISSING_PREREQUISITE, EXIT_OK, go_env, run_doctor


def _cp(stdout="", rc=0, stderr=""):
    return subprocess.CompletedProcess([], rc, stdout, stderr)


def fake_runner(cmd, **kw):
    if cmd[:2] == ["go", "version"]:
        return _cp("go version go1.24.7 linux/amd64\n")
    if cmd[:2] == ["go", "env"]:
        return _cp("linux\namd64\n")
    if cmd[:3] == ["go", "tool", "nm"]:
        return _cp(stderr="usage: go tool nm [options] file...\n", rc=1)
    raise AssertionError(cmd)


def test_doctor_all_present():
    rep = run_doctor(which=lambda n: f"/usr/bin/{n}", runner=fake_runner)
    assert rep.exit_code == EXIT_OK
    assert any("go version go1.24.7" in line for line in rep.lines)
    assert "go tool nm: runs" in rep.lines


def test_doctor_simulated_missing_go():
    def which(name):
        return None if name == "go" else f"/usr/bin/{name}"

    def runner(*a, **k):
        raise AssertionError("must not run go when it is missing")

    rep = run_doctor(which=which, runner=runner)
    assert rep.exit_code == EXIT_MISSING_PREREQUISITE == 3
    assert "go: not found" in rep.lines
    assert "go" in rep.missing


def test_doctor_docker_missing_is_informational():
    def which(name):
        return None if name == "docker" else f"/usr/bin/{name}"

    rep = run_doctor(which=which, runner=fake_runner)
    assert rep.exit_code == EXIT_OK
    assert any(line.startswith("docker: not found") for line in rep.lines)


def test_doctor_old_python_fails():
    rep = run_doctor(which=lambda n: "/x", runner=fake_runner, python_version=(3, 9, 0))
    assert rep.exit_code == EXIT_MISSING_PREREQUISITE


def test_doctor_nm_not_running_fails():
    def runner(cmd, **kw):
        if cmd[:3] == ["go", "tool", "nm"]:
            return _cp(stderr="go: no such tool", rc=2)
        return fake_runner(cmd, **kw)

    rep = run_doctor(which=lambda n: "/x", runner=runner)
    assert rep.exit_code == EXIT_MISSING_PREREQUISITE
    assert "go tool nm" in rep.missing


def test_go_env_is_offline_and_local(monkeypatch):
    monkeypatch.setenv("GOFLAGS", "-mod=mod")
    monkeypatch.setenv("GOPROXY", "https://proxy.golang.org")
    monkeypatch.setenv("GOTOOLCHAIN", "auto")
    env = go_env()
    assert env["GOPROXY"] == "off"
    assert env["GOTOOLCHAIN"] == "local"
    assert env["CGO_ENABLED"] == "0"
    assert "GOFLAGS" not in env
